"""Accounting and quota regression tests; synthetic logs, no account/network calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import codex_usage as c


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = c.connect(self.root / 'test.db')
        self.log = self.root / 'session.jsonl'
        self.ts = '2026-09-20T12:00:00Z'

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def append(self, typ, payload):
        with self.log.open('a') as f:
            f.write(json.dumps({'timestamp': self.ts, 'type': typ, 'payload': payload}) + '\n')

    def meta(self, session='s1'):
        self.append('session_meta', {'id': session, 'cwd': '/projects/demo'})
        self.append('turn_context', {'model': 'test-model', 'cwd': '/projects/demo'})

    def usage(self, n=100):
        return dict(input_tokens=n, cached_input_tokens=n // 2, output_tokens=10,
                    reasoning_output_tokens=5, total_tokens=n + 10)

    def ingest(self, log=None):
        with self.db:
            c.ingest_file(self.db, log or self.log)

    def total(self):
        return self.db.execute('SELECT SUM(input+output) FROM codex_counted').fetchone()[0]

    def test_response_dedupe_replay_forks_and_subsets(self):
        self.meta()
        for _ in range(2):
            self.append('token_usage_record', {'response_id': 'r1', 'usage': self.usage()})
        self.append('event_msg', {'type': 'token_count', 'info': {'total_token_usage': self.usage()}})
        self.ingest()
        self.ingest()
        copied = self.root / 'fork.jsonl'
        copied.write_text(self.log.read_text())
        self.ingest(copied)
        self.assertEqual(self.total(), 110)
        payload = c.build_payload(self.db, c.timestamp(self.ts) + 1)
        self.assertEqual(payload['today']['tokens'], 110)
        self.assertEqual(payload['today']['cache_hit_pct'], 50)
        self.assertEqual(payload['projects'][0]['project'], '/projects/demo')

    def test_partial_line_and_append(self):
        self.meta()
        line = json.dumps({'timestamp': self.ts, 'type': 'token_usage_record',
                           'payload': {'response_id': 'r1', 'usage': self.usage()}})
        with self.log.open('a') as f:
            f.write(line[:40])
        self.ingest()
        self.assertIsNone(self.total())
        with self.log.open('a') as f:
            f.write(line[40:] + '\n')
        self.ingest()
        self.assertEqual(self.total(), 110)

    def test_legacy_delta_and_counter_reset(self):
        self.meta()
        for n in (100, 100, 200, 50, 100):
            self.append('event_msg', {'type': 'token_count', 'info': {
                'total_token_usage': dict(input_tokens=n, cached_input_tokens=0,
                                         output_tokens=0, reasoning_output_tokens=0)}})
        self.ingest()
        # Repeated cumulative values must not be counted; decreasing counters
        # establish a baseline. The post-reset 100 must still count its 50 delta.
        self.assertEqual(self.total(), 250)

    def test_timezone_daily_boundary(self):
        self.meta()
        self.ts = '2026-09-20T06:59:00Z'  # Yesterday Pacific.
        self.append('token_usage_record', {'response_id': 'r1', 'usage': self.usage()})
        self.ts = '2026-09-20T07:01:00Z'
        self.append('token_usage_record', {'response_id': 'r2', 'usage': self.usage(200)})
        self.ingest()
        payload = c.build_payload(self.db, c.timestamp(self.ts) + 1)
        self.assertEqual(payload['today']['tokens'], 210)
        self.assertEqual(payload['daily'][-2]['tokens'], 110)

    def test_quota_dynamic_windows_and_reset_pacing(self):
        now = c.timestamp(self.ts)
        for ts, pct, reset in [(now-7200, 90, now-3600), (now-3600, 10, now+86400), (now, 12, now+86400)]:
            c.quota_insert(self.db, ts, {'limitId': 'codex', 'primary': {
                'usedPercent': pct, 'windowDurationMins': 10080, 'resetsAt': reset}, 'secondary': None}, 'app-server')
        w = c.build_payload(self.db, now)['windows']
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]['minutes'], 10080)
        self.assertEqual(w[0]['projected_pct'], 60)
        self.assertEqual(w[0]['budget_per_day'], 87)
        stale = c.build_payload(self.db, now+86401)['windows'][0]
        self.assertTrue(stale['expired'])
        self.assertEqual(stale['used_pct'], 12)  # Never fabricate a reset-to-zero.
        self.assertIsNone(stale['projected_pct'])

    def test_cache_staleness_without_collector(self):
        now = c.timestamp(self.ts)
        c.quota_insert(self.db, now, {'primary': {'used_percent': 39, 'window_minutes': 10080,
                                                'resets_at': now+100}}, 'transcript')
        cache = self.root / 'cache.json'
        cache.write_text(json.dumps(c.build_payload(self.db, now)))
        with patch.object(c.time, 'time', return_value=now+2000):
            payload = c.cached_payload(cache)
        self.assertTrue(payload['collector_stale'])
        self.assertTrue(payload['windows'][0]['stale'])
        self.assertTrue(payload['windows'][0]['expired'])
        self.assertIsNone(c.cached_payload(self.root / 'missing.json'))

    def test_failed_live_poll_preserves_local_quota(self):
        self.meta()
        self.append('event_msg', {'type': 'token_count', 'rate_limits': {
            'primary': {'used_percent': 39, 'window_minutes': 10080, 'resets_at': c.timestamp(self.ts)+86400}}})
        home = self.root / 'home'
        sessions = home / 'sessions/2026/09/20'
        sessions.mkdir(parents=True)
        (sessions / 's.jsonl').write_text(self.log.read_text())
        with patch.object(c, 'fetch_quota', side_effect=TimeoutError('test timeout')):
            c.collect('fake-codex', home=home, db_path=self.root/'other.db', cache_path=self.root/'cache.json')
        payload = json.loads((self.root/'cache.json').read_text())
        self.assertEqual(payload['windows'][0]['used_pct'], 39)
        self.assertEqual(payload['windows'][0]['source'], 'transcript')


if __name__ == '__main__':
    unittest.main()
