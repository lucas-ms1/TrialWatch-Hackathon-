"""Append-only invented evidence and dependency checks; no legal validation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reviewdesk.rights import RUBRIC_VERSION, render_rights_markdown
from reviewdesk.draft_contract import schema_for
from reviewdesk.server import APIError, ReviewServer, ReviewStore

ROOT = Path(__file__).resolve().parents[1]
CID = 'rights_demo_1'


class EvidenceAdditionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='trialwatch-evidence-additions-test-')
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        seed = json.loads((ROOT / 'reviewdesk/rights.synthetic.v2.json').read_text(encoding='utf-8'))
        self.candidate = deepcopy(next(c for c in seed['candidates'] if c['id'] == CID))
        self.candidate['related_candidate_ids'] = []
        self.candidate['rights_metadata']['related_cases'] = []
        self.candidate['rights_metadata']['pattern_hypotheses'] = []
        self.prepared = deepcopy(seed['rights_prepared_mappings'][CID])
        seed['candidates'], seed['rights_prepared_mappings'] = [], {}
        self.seed = self.directory / 'empty.synthetic.json'
        self.seed.write_text(json.dumps(seed), encoding='utf-8')
        self.store = ReviewStore(self.seed, self.directory / 'state')
        self.draft_payload = json.loads((ROOT / 'examples/ai-draft.synthetic.json').read_text(encoding='utf-8'))['import_payload']
        supplied = json.loads(self.draft_payload['model_input_json'])
        self.texts = {s['id']: '\n\n'.join([c['excerpt'] for c in self.candidate['claims'] if c['source_id'] == s['id']] +
                     [p['quote'] for p in supplied['factual_passages'] if p['source_id'] == s['id']] +
                     ['Additional wholly fictional passage for append-only tests.']) for s in self.candidate['sources']}
        self.store.rights.intake({'schema_version':'rights-intake/2','candidate':self.candidate,
                                 'source_texts':self.texts,'prepared_mappings':None})

    def addition(self, claim_id='new_quote', **changes):
        claim = {'id':claim_id,'source_id':'a_report','text':'Additional invented observation.',
                 'excerpt':'Additional wholly fictional passage for append-only tests.',
                 'locator':'Invented retained paragraph','event_date':None,'date_note':'Fictional; date unknown.',
                 'attribution':'Original synthetic fixture; no real judicial finding.'}
        result = {'expected_revision':0,'author':'Fictional preparation label','origin':'synthetic_prepared','claims':[claim]}
        result.update(changes)
        return result

    def assessment(self, **changes):
        result = {'expected_revision':0,'expected_evidence_revision':0,'rubric_version':RUBRIC_VERSION,
                  'analyst':'Fictional UI analyst','preparation':'synthetic_prepared','dimensions':deepcopy(self.prepared)}
        result.update(changes)
        return result

    def originals(self):
        with self.store.connection() as c:
            return c.execute('SELECT * FROM intakes').fetchall(), c.execute('SELECT * FROM rights_source_texts').fetchall()

    def test_append_preserves_original_rows_inputs_and_reopens_exact_quotes(self):
        originals, payload = self.originals(), self.addition()
        before = deepcopy(payload)
        record = self.store.rights.add_evidence(CID, payload)
        self.assertEqual(payload, before)
        self.assertEqual(record['revision'], 1)
        self.assertEqual(record['evidence_revision'], 1)
        self.assertEqual(self.originals(), originals)
        self.assertEqual(self.candidate['claims'], self.store.state()['candidates'][0]['claims'][:-1])
        reopened = ReviewStore(self.seed, self.directory / 'state')
        self.assertEqual(reopened.state()['candidates'][0]['claims'][-1], before['claims'][0])
        profile = reopened.rights.state()['case_profiles'][CID]
        self.assertEqual(profile['evidence_additions'], [record])
        self.assertEqual(profile['review_status'], 'unassessed')
        self.assertEqual(reopened.state()['history'], {})
        self.assertEqual(reopened.rights.state()['review_history'], {})
        self.assertEqual(profile['evidence_revision'], 1)

    def test_wrong_own_source_ids_quote_fields_and_origins_reject_atomically(self):
        bad = []
        p = self.addition(); p['claims'][0]['id'] = 'a_notice'; bad.append(p)
        p = self.addition(); p['claims'].append(deepcopy(p['claims'][0])); bad.append(p)
        p = self.addition(); p['claims'][0]['source_id'] = 'unknown'; bad.append(p)
        p = self.addition(); p['claims'][0]['excerpt'] = self.candidate['claims'][2]['excerpt']; bad.append(p)
        p = self.addition(); p['claims'][0]['excerpt'] = 'Invented but absent text'; bad.append(p)
        p = self.addition(); p['claims'][0]['score'] = 0; bad.append(p)
        p = self.addition(); p['claims'][0]['attribution_kind'] = 'approved'; bad.append(p)
        bad.extend([self.addition(origin='human_approved'), self.addition(claims=[]), self.addition(claims=[None])])
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.rights.add_evidence(CID, payload)
        self.assertEqual(self.store.rights.state()['evidence_addition_history'], {})
        self.assertEqual(len(self.store.state()['candidates'][0]['claims']), len(self.candidate['claims']))

    def test_unified_revision_concurrency_and_human_review_scope_stay_separate(self):
        review = self.store.review(CID, {'expected_revision':0,'reviewer':'Fictional review simulation',
            'decision':'include','reason':'Only original a_notice; no legal validation.','duplicate_of':None,
            'corrections':[],'included_claim_ids':['a_notice']})
        self.store.rights.save(CID, self.assessment(expected_evidence_revision=1))
        self.store.rights.review(CID, {'expected_assessment_revision':1,'expected_review_revision':0,
            'expected_evidence_revision':1,'reviewer':'Fictional legal review simulation','reason':'Software scope test only.',
            'decision':'approve','dimension_ids':['notice_charges'],'claim_ids':['a_notice','a_minutes','a_reply']})
        exported_before = self.store.rights.export(CID)
        def save(pid):
            try:
                return self.store.rights.add_evidence(CID, self.addition(pid, expected_revision=1))
            except APIError as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ['parallel_a','parallel_b']))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(sum(isinstance(r, APIError) and r.status == 409 for r in results), 1)
        state = self.store.rights.state(); profile = state['case_profiles'][CID]
        self.assertEqual(profile['evidence_revision'], 2)
        self.assertTrue(profile['stale_evidence'])
        self.assertEqual(profile['current_evidence_review'], review)
        self.assertEqual(profile['current_evidence_review']['included_claim_ids'], ['a_notice'])
        self.assertEqual(self.store.export(CID)['claims'][0]['id'], 'a_notice')
        self.assertEqual(len(self.store.export(CID)['claims']), 1)
        self.assertEqual(self.store.rights.export(CID)['assessment_history'], exported_before['assessment_history'])
        self.assertEqual(self.store.rights.export(CID)['rights_review_history'], exported_before['rights_review_history'])
        with self.assertRaises(APIError):
            self.store.rights.save(CID, self.assessment(expected_revision=1, expected_evidence_revision=1))
        fresh = self.store.rights.save(CID, self.assessment(expected_revision=1, expected_evidence_revision=2))
        self.assertEqual(fresh['evidence_revision'], 2)
        self.assertEqual(len(fresh['evidence_snapshot']['claims']), len(self.candidate['claims']) + 1)
        self.assertEqual(self.store.rights.export(CID)['case_profile']['review_status'], 'pending_human_review')
        exported = self.store.rights.export(CID)
        self.assertEqual(len(exported['evidence_addition_history']), 1)
        markdown = render_rights_markdown(exported)
        self.assertIn('Evidence addition revision 1', markdown)
        self.assertIn('Fictional preparation label', markdown)
        self.assertIn('no human inspection', markdown)

    def test_additions_stale_proposals_and_ai_without_rewriting_old_outputs(self):
        draft = self.store.ai_drafts.import_draft(CID, deepcopy(self.draft_payload))
        self.store.rights.save(CID, self.assessment())
        fixture = json.loads((ROOT / 'examples/intervention.synthetic.json').read_text(encoding='utf-8'))
        self.store.interventions.context(CID, deepcopy(fixture['context']))
        proposal = self.store.interventions.propose(CID, deepcopy(fixture['proposal']))
        self.store.rights.add_evidence(CID, self.addition())
        stale = self.store.ai_drafts.state(CID)['latest']
        self.assertTrue(stale['stale'])
        self.assertEqual(stale['raw_hashes'], draft['raw_hashes'])
        self.assertEqual(stale['raw_draft_json'], draft['raw_draft_json'])
        self.assertEqual(stale['draft'], draft['draft'])
        self.assertEqual(stale['dependencies'], draft['dependencies'])
        changed = self.store.interventions.export(proposal['id'])['recommendation']
        self.assertTrue(changed['stale'])
        self.assertEqual(changed['rights_snapshots'], proposal['rights_snapshots'])
        self.assertEqual(changed['context_snapshot'], proposal['context_snapshot'])
        self.assertTrue(any('evidence' in r.lower() for r in changed['stale_reasons']))

    def test_fresh_pending_worksheet_after_addition_uses_unified_revision(self):
        self.store.rights.add_evidence(CID, self.addition())
        payload = deepcopy(self.draft_payload)
        draft = json.loads(payload['draft_json'])
        draft['limitations'].append('Additional invented retained observation requires separate review.')
        supplied = json.loads(payload['model_input_json'])
        locator = {'pdf_page':1,'printed_page':None,'paragraph_or_heading':'Invented additional retained paragraph'}
        quote = self.addition()['claims'][0]['excerpt']
        supplied['factual_passages'].append({'passage_id':'AP05','source_id':'a_report','quote':quote,
            'locator':locator,'surrounding_context_note':'Entirely invented additional source text.',
            'date_roles':{},'uncertainty':'Fictional observation; date unknown.'})
        supplied['identifier_links'].append({'proposition_id':'new_quote','support_passage_ids':['AP05']})
        draft['chronology'].append({'event':'Additional invented observation.','date':None,'date_role':'unknown',
            'proposition_ids':['new_quote'],'passage_ids':['AP05'],'limits':'No real legal finding.'})
        draft['citations'].append({'passage_id':'AP05','source_id':'a_report','quote':quote,
                                  'locator':json.dumps(locator),'attribution':'Original fictional fixture.'})
        draft['human_checkpoint']['source_review_ids'].extend(['new_quote','AP05'])
        payload['model_input_json'] = json.dumps(supplied)
        payload['schema_json'] = json.dumps(schema_for(CID, supplied))
        payload['draft_json'] = json.dumps(draft)
        current = self.store.ai_drafts.import_draft(CID, payload)
        self.assertFalse(current['stale'])
        result = self.store.ai_drafts.worksheet(CID, {'expected_draft_revision':1,'author':'Fictional preparation',
                                                  'selected_option_id':'verify_records'})
        assessment = self.store.rights.export(CID)['case_profile']['assessment']
        self.assertEqual(assessment['evidence_revision'], 1)
        self.assertTrue(all(d['status'] == 'not_assessed' for d in assessment['dimensions']))
        self.assertEqual(result['recommendation']['dependencies']['cases'][CID]['evidence_revision'], 1)
        self.assertEqual(self.store.rights.state()['review_history'], {})

    def test_http_explicit_addition_route_and_seed_without_captures_reject(self):
        server = ReviewServer(self.store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(thread.join, 3); self.addCleanup(server.shutdown)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            connection.request('POST','/api/rights/evidence-additions/'+CID, json.dumps(self.addition()),
                               headers={'Content-Type':'application/json'})
            response = connection.getresponse(); record = json.loads(response.read())
            self.assertEqual(response.status, 201)
            self.assertEqual(record['origin'], 'synthetic_prepared')
            self.assertEqual(record['evidence_revision'], 1)
        finally:
            connection.close()
        legacy = ReviewStore(ROOT / 'reviewdesk/rights.synthetic.v2.json', self.directory / 'separate-seed-state')
        with self.assertRaises(APIError) as exc:
            legacy.rights.add_evidence(CID, self.addition())
        self.assertEqual(exc.exception.code, 'source_text_required')


if __name__ == '__main__':
    unittest.main()
