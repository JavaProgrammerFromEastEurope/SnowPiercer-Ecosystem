import concurrent.futures
import os
import sqlite3
import tempfile
import unittest

from ai_cognition import assess
from ai_cognition.admission import (TrustedAdmission, ReplayStore, AdmissionRejected,
                                    signed_envelope, MAX_WIRE_BYTES)

KEY = b'K' * 32
OTHER = b'Z' * 32
OBS = {'event_id': 'evt-001', 'source': 'trainos', 'severity': 'critical', 'description': 'alert'}
NOW = 2000000000

def envelope(**changes):
    return signed_envelope({**OBS, **changes}, NOW, 'nonce-0000000001', KEY)

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'replay.sqlite')
        self.store = ReplayStore(self.path)
        self.boundary = TrustedAdmission({'trainos': KEY, 'rail': OTHER}, self.store, clock=lambda: NOW)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_valid_and_read_only(self):
        result = self.boundary.admit(envelope())
        self.assertEqual(result.decision.value, 'ESCALATE')
        self.assertFalse(result.actionable)
        self.assertEqual(result.evidence_sha256, assess(OBS).evidence_sha256)

    def test_exact_replay(self):
        env = envelope()
        self.boundary.admit(env)
        with self.assertRaisesRegex(AdmissionRejected, 'REPLAY_DETECTED'):
            self.boundary.admit(env)

    def test_event_id_replay_with_fresh_nonce(self):
        self.boundary.admit(envelope())
        env = signed_envelope(OBS, NOW, 'nonce-0000000002', KEY)
        with self.assertRaisesRegex(AdmissionRejected, 'REPLAY_DETECTED'):
            self.boundary.admit(env)

    def test_replay_survives_restart(self):
        env = envelope()
        self.boundary.admit(env)
        self.store.close()
        self.store = ReplayStore(self.path)
        self.boundary = TrustedAdmission({'trainos': KEY}, self.store, clock=lambda: NOW)
        with self.assertRaisesRegex(AdmissionRejected, 'REPLAY_DETECTED'):
            self.boundary.admit(env)

    def test_tampering_and_wrong_key(self):
        env = envelope()
        for candidate in [{**env, 'timestamp': NOW - 1},
                          {**env, 'observation': {**OBS, 'severity': 'info'}},
                          signed_envelope(OBS, NOW, 'nonce-0000000001', OTHER)]:
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(AdmissionRejected, 'AUTHENTICATION_FAILED'):
                    self.boundary.admit(candidate)

    def test_source_binding(self):
        forged = signed_envelope({**OBS, 'source': 'rail'}, NOW, 'nonce-0000000001', KEY)
        with self.assertRaisesRegex(AdmissionRejected, 'AUTHENTICATION_FAILED'):
            self.boundary.admit(forged)

    def test_stale_and_future_boundaries(self):
        for timestamp in [NOW - 301, NOW + 31]:
            env = signed_envelope(OBS, timestamp, 'nonce-0000000001', KEY)
            with self.assertRaises(AdmissionRejected):
                self.boundary.admit(env)
        for i, timestamp in enumerate([NOW - 300, NOW + 30]):
            env = signed_envelope({**OBS, 'event_id': 'evt-%d' % i}, timestamp,
                                  'nonce-000000000%d' % (i + 3), KEY)
            self.assertFalse(self.boundary.admit(env).actionable)

    def test_oversize_rejected(self):
        env = envelope()
        env['extra'] = 'x' * MAX_WIRE_BYTES
        with self.assertRaisesRegex(AdmissionRejected, 'OVERSIZED_ENVELOPE'):
            self.boundary.admit(env)

    def test_malformed_envelopes(self):
        env = envelope()
        candidates = [None, [], {}, {**env, 'mac': '0'*64}, {**env, 'mac': 12},
                      {**env, 'timestamp': True}, {**env, 'nonce': 'short'},
                      {**env, 'observation': {'source': 'trainos'}},
                      {**env, 'command': 'stop'}, {**env, 'timestamp': float('nan')}]
        for item in candidates:
            with self.subTest(item=item):
                with self.assertRaises(AdmissionRejected):
                    self.boundary.admit(item)

    def test_concurrent_replay_only_one_admitted(self):
        env = envelope()
        def attempt(_):
            try:
                self.boundary.admit(env)
                return True
            except AdmissionRejected:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(attempt, range(30)))
        self.assertEqual(sum(results), 1)

    def test_storage_failure_closed(self):
        self.store.close()
        with self.assertRaisesRegex(AdmissionRejected, 'REPLAY_STORE_UNAVAILABLE'):
            self.boundary.admit(envelope())
        self.store = ReplayStore(self.path)

    def test_invalid_configuration(self):
        for keys in [{}, {'trainos': b'short'}, {'trainos': 'text'}]:
            with self.assertRaises(ValueError):
                TrustedAdmission(keys, self.store)
        with self.assertRaises(ValueError):
            TrustedAdmission({'trainos': KEY}, self.store, max_age=-1)

    def test_cross_source_independent_replay_namespace(self):
        self.boundary.admit(envelope())
        rail = signed_envelope({**OBS, 'source': 'rail'}, NOW, 'nonce-0000000001', OTHER)
        self.assertFalse(self.boundary.admit(rail).actionable)

    def test_bad_clock_fail_closed(self):
        bad = TrustedAdmission({'trainos': KEY}, self.store, clock=lambda: float('nan'))
        with self.assertRaisesRegex(AdmissionRejected, 'CLOCK_UNAVAILABLE'):
            bad.admit(envelope())

    def test_signing_rejects_invalid(self):
        for key in [b'weak', 'not-bytes']:
            with self.assertRaises(ValueError):
                signed_envelope(OBS, NOW, 'nonce-0000000001', key)
        with self.assertRaises(ValueError):
            signed_envelope(OBS, NOW, 'short', KEY)

if __name__ == '__main__':
    unittest.main()
