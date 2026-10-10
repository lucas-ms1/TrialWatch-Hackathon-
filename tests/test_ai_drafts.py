"""Pending drafting mechanics; mocked providers do not establish live access."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from reviewdesk.server import APIError, ReviewServer, ReviewStore, markdown_text
from reviewdesk.ai_drafts import render_draft_markdown

ROOT = Path(__file__).resolve().parents[1]
CID = 'rights_demo_1'


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name) / 'state'
        self.store = ReviewStore(ROOT / 'reviewdesk/rights.synthetic.v2.json', self.state_dir)
        self.service = self.store.ai_drafts
        self.payload = json.loads((ROOT / 'examples/ai-draft.synthetic.json').read_text(encoding='utf-8'))['import_payload']

    def saved(self):
        return self.service.import_draft(CID, deepcopy(self.payload))

    def mutated(self, field, mutate):
        payload = deepcopy(self.payload)
        value = json.loads(payload[field])
        mutate(value)
        payload[field] = json.dumps(value)
        return payload

    def test_saved_fixture_reopens_and_exports_source_bridge_without_approval(self):
        record = self.saved()
        reopened = ReviewStore(ROOT / 'reviewdesk/rights.synthetic.v2.json', self.state_dir).ai_drafts
        current = reopened.state(CID)['latest']
        self.assertEqual(record, current)
        self.assertFalse(current['stale'])
        self.assertEqual(current['origin'], 'synthetic_fixture')
        self.assertEqual(len(current['draft']['assessment_mappings']), 20)
        self.assertTrue(all(row['mapping'] is None for row in current['draft']['assessment_mappings']))
        self.assertEqual(current['source_reviews'], [])
        text = render_draft_markdown(reopened.export(record['id']))
        for token in ['AP01', 'a_notice', 'AP03', 'example.invalid', 'proposal_only', 'null', 'raw', 'Exact citations']:
            self.assertTrue(token in text or markdown_text(token) in text, token)
        self.assertEqual(self.store.rights.state()['case_profiles'][CID]['assessment'], None)

    def test_unknown_field_and_malformed_or_nonfinite_json_rejected_visibly(self):
        for raw in ['{"x":1,"x":2}', '{', '{"x":NaN}', '{"x":1e999}']:
            payload = deepcopy(self.payload)
            payload['draft_json'] = raw
            with self.assertRaises(APIError):
                self.service.import_draft(CID, payload)
        payload = self.mutated('draft_json', lambda d: d.update(automatic_score=99))
        with self.assertRaises(APIError):
            self.service.import_draft(CID, payload)
        self.assertEqual(len(self.service.state(CID)['errors']), 5)
        self.assertIsNone(self.service.state(CID)['latest'])

    def test_altered_quote_wrong_source_bridge_and_omitted_competing_account_rejected(self):
        mutations = [lambda d: d['citations'][0].update(quote='Invented uncited material'),
                     lambda d: d['citations'][0].update(source_id='a_reply_source'),
                     lambda d: d['summary'][0].update(passage_ids=['AP02']),
                     lambda d: d['options'][0].update(contrary_passage_ids=[])]
        for mutate in mutations:
            with self.assertRaises(APIError):
                self.service.import_draft(CID, self.mutated('draft_json', mutate))

    def test_scored_mapping_fake_approval_wrong_date_and_schema_weakening_rejected(self):
        for mutate in [lambda d: d['assessment_mappings'][0].update(mapping={'score': 0}),
                       lambda d: d['human_checkpoint'].update(approval='approved'),
                       lambda d: d['chronology'][0].update(date='2023-01-01')]:
            with self.assertRaises(APIError):
                self.service.import_draft(CID, self.mutated('draft_json', mutate))
        payload = self.mutated('schema_json', lambda d: d.update(additionalProperties=True))
        with self.assertRaises(APIError):
            self.service.import_draft(CID, payload)

    def test_duplicate_input_passages_or_wrong_source_reference_rejected(self):
        for mutate in [lambda d: d['factual_passages'].append(deepcopy(d['factual_passages'][0])),
                       lambda d: d['identifier_links'][0].update(support_passage_ids=['AP03']),
                       lambda d: d['source_metadata'][0].update(url='https://example.invalid/unrelated')]:
            with self.assertRaises(APIError):
                self.service.import_draft(CID, self.mutated('model_input_json', mutate))
        with self.assertRaises(APIError) as e:
            self.service.import_draft(CID, self.mutated('model_input_json', lambda d: d.update(factual_passages=[None])))
        self.assertEqual(e.exception.code, 'draft_schema_error')

    def test_manual_fallback_works_without_provider_and_cannot_claim_real_saved_run(self):
        payload = deepcopy(self.payload)
        payload['origin'] = 'manual_draft'
        record = self.service.import_draft(CID, payload)
        self.assertFalse(record['provenance']['completed'])
        self.assertIsNone(record['provenance']['provider'])
        bad = deepcopy(self.payload)
        bad.update(expected_revision=1, origin='saved_model', receipt_json='{}')
        with self.assertRaises(APIError):
            self.service.import_draft(CID, bad)

    def test_revision_conflict_addendum_immutability_and_evidence_staleness(self):
        original = self.saved()
        with self.assertRaises(APIError):
            self.saved()
        latest = self.service.addendum(CID, {'expected_revision': 1, 'author': 'Synthetic preparation label', 'note': 'Keep individual scope clear.'})
        self.assertEqual(latest['raw_hashes'], original['raw_hashes'])
        self.assertEqual(latest['draft'], original['draft'])
        self.assertEqual(len(self.service.state(CID)['history']), 2)
        self.store.review(CID, {'expected_revision': 0, 'reviewer': 'Synthetic simulation', 'decision': 'defer', 'reason': 'Fixture correction simulation, not an actual source review.',
            'duplicate_of': None, 'included_claim_ids': [], 'corrections': [{'claim_id': 'a_notice', 'text': 'Corrected fictional wording.', 'event_date': None,
                'source_id': 'a_report', 'excerpt': 'The fictional defence', 'locator': 'Fictional paragraph'}]})
        self.assertTrue(all(r['stale'] for r in self.service.state(CID)['history']))
        self.assertEqual(self.service.state(CID)['history'][0]['raw_hashes'], original['raw_hashes'])
        with self.assertRaises(APIError):
            self.service.worksheet(CID, {'expected_draft_revision': 2, 'author': 'Synthetic label', 'selected_option_id': 'verify_records'})
        repeated = deepcopy(self.payload)
        repeated['expected_revision'] = 2
        historical = self.service.import_draft(CID, repeated)
        self.assertTrue(historical['stale'])
        self.assertEqual(historical['dependencies'], original['dependencies'])

    def test_source_summary_review_separate_exact_scope_no_rights_review(self):
        self.saved()
        payload = {'expected_review_revision': 0, 'draft_revision': 1, 'reviewer': 'Synthetic reviewer simulation',
            'decision': 'accept_with_qualifications', 'claim_ids': ['a_notice'], 'passage_ids': ['AP01'],
            'reason': 'Simulation only: accept attributed fixture wording, not a legal finding.', 'reported_inspection': True}
        result = self.service.source_review(CID, payload)
        self.assertIn('no legal/right-dimension', result['scope'])
        self.assertEqual(self.service.state(CID)['latest']['review_status'], 'human_review_pending')
        with self.store.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rights_reviews').fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 0)
        bad = deepcopy(payload)
        bad.update(expected_review_revision=1, passage_ids=['AP99'])
        with self.assertRaises(APIError):
            self.service.source_review(CID, bad)

    def test_pending_worksheet_null_legal_scope_reopen_export_and_ai_revision_stale(self):
        draft = self.saved()
        result = self.service.worksheet(CID, {'expected_draft_revision': 1, 'author': 'Synthetic preparation label', 'selected_option_id': 'verify_records'})
        proposal = result['recommendation']
        self.assertEqual(proposal['disposition'], 'prepare_verify')
        self.assertEqual(proposal['dimension_ids'], [])
        self.assertEqual(proposal['reviews'], [])
        self.assertEqual(proposal['dependencies']['ai_draft']['id'], draft['id'])
        self.assertTrue(all(d['status'] == 'not_assessed' and d['score'] is None for d in self.store.rights.export(CID)['case_profile']['assessment']['dimensions']))
        self.assertFalse(self.service.state(CID)['latest']['stale'])
        reopened = ReviewStore(ROOT / 'reviewdesk/rights.synthetic.v2.json', self.state_dir)
        exported = reopened.interventions.export(proposal['id'])['recommendation']
        self.assertEqual(exported['context_snapshot']['claims'][0]['id'], 'AP01')
        self.assertIn('a_notice', exported['context_snapshot']['claims'][0]['text'])
        self.service.addendum(CID, {'expected_revision': 1, 'author': 'Synthetic label', 'note': 'Changed draft qualification.'})
        stale = self.store.interventions.export(proposal['id'])['recommendation']
        self.assertTrue(stale['stale'])
        self.assertTrue(any('AI draft revision' in r for r in stale['stale_reasons']))
        self.assertEqual(stale['context_snapshot'], proposal['context_snapshot'])

    def test_deferral_selection_preserves_alternative_and_all_unknown_factors(self):
        self.saved()
        result = self.service.worksheet(CID, {'expected_draft_revision': 1, 'author': 'Synthetic label', 'selected_option_id': 'defer_public_route'})
        proposal = result['recommendation']
        self.assertEqual(proposal['disposition'], 'defer')
        self.assertEqual(len(proposal['options']), 2)
        original_routes = [o['route'] for o in json.loads(self.payload['draft_json'])['options']]
        for route, option in zip(original_routes, proposal['options']):
            self.assertIn(route, option['objective'])
        self.assertEqual(proposal['factors']['preferences'], 'unknown')
        self.assertEqual(proposal['factors']['harm'], 'unknown')

    def test_missing_cli_disabled_access_and_provider_failure_show_fallback(self):
        self.saved()
        request = {'expected_revision': 1, 'author': 'Synthetic label', 'model': 'gpt-6.1-sol'}
        with self.assertRaises(APIError) as e:
            self.service.live(CID, request)
        self.assertEqual(e.exception.code, 'live_disabled')
        self.service.allow_live = True
        with patch('reviewdesk.ai_drafts.shutil.which', return_value=None), self.assertRaises(APIError) as e:
            self.service.live(CID, request)
        self.assertEqual(e.exception.code, 'provider_unavailable')
        with patch('reviewdesk.ai_drafts.shutil.which', return_value='fake-codex'), patch('reviewdesk.ai_drafts.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='Not logged in')), self.assertRaises(APIError) as e:
            self.service.live(CID, request)
        self.assertEqual(e.exception.code, 'provider_access_missing')
        self.assertFalse(self.service.state(CID)['capability']['live_attempted'])
        self.assertEqual(len(self.service.state(CID)['history']), 1)

    def fake_provider(self, bad_tool=False, bad_output=False):
        def run(args, **kwargs):
            if args[1:] == ['login', 'status']:
                return SimpleNamespace(returncode=0, stdout='Logged in using ChatGPT', stderr='')
            if args[1] == 'exec':
                self.assertEqual(args[args.index('--model') + 1], 'gpt-6.1-sol')
                self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
                self.assertIn('--ignore-user-config', args)
                self.assertIn('--disable', args)
                self.assertNotEqual(Path(kwargs['cwd']), ROOT)
                target = Path(args[args.index('-o') + 1])
                target.write_text('{}' if bad_output else self.payload['draft_json'], encoding='utf-8', newline='')
                events = [{'type': 'turn.completed', 'usage': {'input_tokens': 1, 'output_tokens': 1}}]
                if bad_tool:
                    events.append({'type': 'item.completed', 'item': {'type': 'command_execution'}})
                kwargs['stdout'].write(('\n'.join(json.dumps(e) for e in events)).encode())
                return SimpleNamespace(returncode=0)
            raise AssertionError(args)
        return run

    def test_mocked_live_success_clean_inputs_tool_disabled_one_persisted_attempt(self):
        self.saved()
        self.service.allow_live = True
        request = {'expected_revision': 1, 'author': 'Synthetic test preparation', 'model': 'gpt-6.1-sol'}
        with patch('reviewdesk.ai_drafts.shutil.which', return_value='fake-codex'), patch('reviewdesk.ai_drafts.subprocess.run', side_effect=self.fake_provider()), patch.dict('os.environ', {'OPENAI_API_KEY': 'synthetic-test-value'}):
            record = self.service.live(CID, request)
        self.assertEqual(record['origin'], 'live_model')
        self.assertTrue(record['provenance']['app_runtime_integrated'])
        self.assertEqual(record['provenance']['tool_events'], [])
        self.assertEqual(record['revision'], 2)
        reopened = ReviewStore(ROOT / 'reviewdesk/rights.synthetic.v2.json', self.state_dir)
        reopened.ai_drafts.allow_live = True
        request['expected_revision'] = 2
        with patch('reviewdesk.ai_drafts.shutil.which', return_value='fake-codex'), patch('reviewdesk.ai_drafts.subprocess.run', side_effect=self.fake_provider()), self.assertRaises(APIError) as e:
            reopened.ai_drafts.live(CID, request)
        self.assertEqual(e.exception.code, 'live_attempt_exhausted')

    def test_mocked_tool_event_or_malformed_provider_output_never_saved(self):
        for bad_tool, bad_output in [(True, False), (False, True)]:
            self.setUp()
            self.saved()
            self.service.allow_live = True
            with patch('reviewdesk.ai_drafts.shutil.which', return_value='fake-codex'), patch('reviewdesk.ai_drafts.subprocess.run', side_effect=self.fake_provider(bad_tool, bad_output)), self.assertRaises(APIError):
                self.service.live(CID, {'expected_revision': 1, 'author': 'Synthetic test preparation', 'model': 'gpt-6.1-sol'})
            self.assertEqual(len(self.service.state(CID)['history']), 1)
            self.assertTrue(self.service.state(CID)['capability']['live_attempted'])
            self.assertFalse(self.service.state(CID)['capability']['live_verified'])

    def test_mocked_provider_timeout_retains_attempt_and_old_draft(self):
        import subprocess
        self.saved()
        self.service.allow_live = True
        provider = self.fake_provider()
        def timeout(args, **kwargs):
            if args[1] == 'exec':
                raise subprocess.TimeoutExpired(args, 600)
            return provider(args, **kwargs)
        with patch('reviewdesk.ai_drafts.shutil.which', return_value='fake-codex'), patch('reviewdesk.ai_drafts.subprocess.run', side_effect=timeout), self.assertRaises(APIError) as e:
            self.service.live(CID, {'expected_revision': 1, 'author': 'Synthetic test preparation', 'model': 'gpt-6.1-sol'})
        self.assertEqual(e.exception.code, 'provider_failure')
        self.assertTrue(self.service.state(CID)['capability']['live_attempted'])
        self.assertEqual(len(self.service.state(CID)['history']), 1)
        self.assertTrue(any('bounded timeout' in p.read_text(encoding='utf-8') for p in (self.state_dir / 'ai_runs').glob('*/run-receipt.json')))

    def test_http_import_state_export_worksheet_and_local_security(self):
        server = ReviewServer(self.store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.addCleanup(stop)
        base = 'http://127.0.0.1:' + str(server.server_port)
        def request(path, payload=None, origin=None):
            headers = {'Origin': origin or base}
            data = None if payload is None else json.dumps(payload).encode('utf-8')
            if data is not None:
                headers['Content-Type'] = 'application/json'
            return urlopen(Request(base + path, data=data, headers=headers), timeout=15)
        imported = json.loads(request('/api/ai-drafts/import/' + CID, self.payload).read())
        state = json.loads(request('/api/ai-drafts/state/' + CID).read())
        self.assertEqual(state['latest']['id'], imported['id'])
        self.assertFalse(state['capability']['live_verified'])
        self.assertFalse(state['capability']['live_enabled'])
        exported = request('/api/ai-drafts/export/' + imported['id'] + '?format=json')
        self.assertIn('attachment', exported.headers['Content-Disposition'])
        self.assertEqual(json.loads(exported.read())['draft_record']['raw_hashes'], imported['raw_hashes'])
        md = request('/api/ai-drafts/export/' + imported['id'] + '?format=md').read().decode()
        self.assertIn('AP03', md)
        worksheet = json.loads(request('/api/ai-drafts/worksheet/' + CID, {'expected_draft_revision': 1, 'author': 'Synthetic HTTP preparation', 'selected_option_id': 'verify_records'}).read())
        self.assertEqual(worksheet['recommendation']['review_status'], 'pending_human_review')
        self.assertEqual(worksheet['recommendation']['dimension_ids'], [])
        with self.assertRaises(HTTPError) as e:
            request('/api/ai-drafts/addenda/' + CID, {'expected_revision': 1, 'author': 'Synthetic HTTP preparation', 'note': 'Must not save cross-origin.'}, 'https://example.invalid')
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(HTTPError) as e:
            request('/api/ai-drafts/export/' + imported['id'] + '?format=html')
        self.assertEqual(e.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
