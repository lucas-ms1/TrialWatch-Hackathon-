"""Retained document text is passive, scoped to its case and never a review."""
from copy import deepcopy
from http.client import HTTPConnection
import html
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reviewdesk.server import APIError, ReviewServer, ReviewStore

ROOT = Path(__file__).resolve().parents[1]


class RetainedSourceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='trialwatch-retained-source-test-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        seed = json.loads((ROOT / 'reviewdesk/rights.synthetic.v2.json').read_text(encoding='utf-8'))
        self.candidate = deepcopy(seed['candidates'][0])
        self.candidate['related_candidate_ids'] = []
        self.candidate['rights_metadata']['related_cases'] = []
        self.candidate['rights_metadata']['pattern_hypotheses'] = []
        seed['candidates'], seed['rights_prepared_mappings'] = [], {}
        self.seed = self.directory / 'empty.json'
        self.seed.write_text(json.dumps(seed), encoding='utf-8')
        self.store = ReviewStore(self.seed, self.directory / 'state')
        self.texts = {s['id']: '\n\n'.join(c['excerpt'] for c in self.candidate['claims'] if c['source_id'] == s['id'])
                      + '\n\n<script>alert("untrusted document")</script> & <img src="https://example.invalid/track">'
                      for s in self.candidate['sources']}
        self.store.rights.intake({'schema_version':'rights-intake/2', 'candidate':self.candidate,
                                 'source_texts':self.texts, 'prepared_mappings':None})
        self.cid = self.candidate['id']
        self.sid = self.candidate['sources'][0]['id']

    def test_exact_source_text_and_read_only_persistence(self):
        before = (self.directory / 'state/reviewdesk.sqlite3').read_bytes()
        document = self.store.rights.retained_source(self.cid, self.sid)
        self.assertEqual(document['text'], self.texts[self.sid])
        self.assertEqual(document['source'], self.candidate['sources'][0])
        reopened = ReviewStore(self.seed, self.directory / 'state')
        self.assertEqual(reopened.rights.retained_source(self.cid, self.sid), document)
        self.assertEqual(reopened.state()['history'], {})
        self.assertEqual(reopened.rights.state()['review_history'], {})
        self.assertEqual((self.directory / 'state/reviewdesk.sqlite3').read_bytes(), before)

    def test_wrong_case_source_missing_capture_and_filesystem_paths_reject(self):
        for cid, sid in [('absent', self.sid), (self.cid, 'absent'), (self.cid, '../document'), ('../case', self.sid)]:
            with self.subTest(cid=cid, sid=sid), self.assertRaises(APIError):
                self.store.rights.retained_source(cid, sid)
        other = ReviewStore(ROOT / 'reviewdesk/rights.synthetic.v2.json', self.directory / 'other-state')
        with self.assertRaises(APIError) as caught:
            other.rights.retained_source(self.cid, self.sid)
        self.assertEqual(caught.exception.code, 'source_text_required')

    def test_http_passive_html_escape_headers_scoping_and_no_writes(self):
        server = ReviewServer(self.store, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 3)
        self.addCleanup(server.shutdown)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=10)
        self.addCleanup(connection.close)
        connection.request('GET', '/api/rights/source-text/' + self.cid + '/' + self.sid)
        response = connection.getresponse()
        body = response.read().decode('utf-8')
        self.assertEqual(response.status, 200)
        self.assertIn('text/html', response.getheader('Content-Type'))
        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
        self.assertEqual(response.getheader('X-Content-Type-Options'), 'nosniff')
        self.assertIn("frame-ancestors 'none'", response.getheader('Content-Security-Policy'))
        self.assertIn(html.escape(self.texts[self.sid]), body)
        self.assertNotIn('<script>', body)
        self.assertNotIn('<img src=', body)
        self.assertIn('Back to case evidence', body)
        for route in ['/api/rights/source-text/' + self.cid + '/absent',
                      '/api/rights/source-text/' + self.cid,
                      '/api/rights/source-text/' + self.cid + '/%2e%2e%2fsource']:
            connection.request('GET', route)
            rejected = connection.getresponse()
            rejected.read()
            self.assertIn(rejected.status, (400, 404))
        self.assertEqual(self.store.state()['history'], {})
        self.assertEqual(self.store.rights.state()['review_history'], {})


if __name__ == '__main__':
    unittest.main()
