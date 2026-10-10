import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from reviewdesk.server import ReviewStore
from scripts.load_synthetic_strategy_case import load_case

ROOT=Path(__file__).resolve().parents[1]


class SyntheticStrategyFixtureTests(unittest.TestCase):
    def test_fresh_starter_loads_pending_scopes_and_exact_excerpts(self):
        with TemporaryDirectory() as directory:
            store=ReviewStore(ROOT/'reviewdesk/rights.synthetic.v2.json',directory)
            cid=load_case(store)
            state=store.rights.state();assessment=state['latest'][cid]
            self.assertEqual(len(assessment['dimensions']),20)
            self.assertEqual(state['case_profiles'][cid]['review_status'],'pending_human_review')
            context=store.interventions.state(cid)['context']
            self.assertEqual(context['revision'],1)
            self.assertEqual(len(context['claims']),9)
            with store.connection() as connection:
                for table in ['reviews','rights_reviews','intervention_reviews','intervention_proposals','ai_drafts']:
                    self.assertEqual(connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
                texts=dict(connection.execute('SELECT source_id,source_text FROM rights_source_texts WHERE candidate_id=?',(cid,)))
                candidate=store.candidates(connection)[cid]
            for claim in candidate['claims']:
                self.assertIn(claim['excerpt'],texts[claim['source_id']])
            self.assertEqual(candidate['material_type'],'synthetic')

    def test_repeated_load_does_not_replace_existing_records(self):
        with TemporaryDirectory() as directory:
            store=ReviewStore(ROOT/'reviewdesk/rights.synthetic.v2.json',directory)
            cid=load_case(store)
            before=store.rights.export(cid);before.pop('exported_at',None)
            before=json.dumps(before,sort_keys=True)
            with self.assertRaisesRegex(ValueError,'already exists'):
                load_case(store)
            after=store.rights.export(cid);after.pop('exported_at',None)
            self.assertEqual(json.dumps(after,sort_keys=True),before)


if __name__=='__main__':unittest.main()
