"""Deterministic conformance checks. Does not assert production or OS isolation."""
import concurrent.futures
from contextlib import contextmanager
import copy
import json
import secrets
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from security.admission import (LocalSimulation, AdmissionUnavailable, ProductionBlocked,
                                RequestRejected, parse_request_json, validate_request)


@contextmanager
def db_connection(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def req(principal='trainos-observer', resource='trainos.telemetry', action='read',
        policy_version='SEC-POLICY-0.1'):
    return {'request_id': str(uuid.uuid4()), 'principal_id': principal,
            'resource': resource, 'action': action, 'policy_version': policy_version,
            'correlation_id': 'SEC-regression'}


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'audit.db'
        self.key = secrets.token_bytes(32)
        self.sim = LocalSimulation(self.path, self.key)

    def admit(self, request=None, broker='trainos-observer'):
        return self.sim.admit(req() if request is None else request, simulated_broker_principal=broker)

    def test_01_exact_read_is_audited_nonexecutable(self):
        result = self.admit()
        self.assertEqual(result['decision'], 'ALLOW')
        self.assertTrue(result['audit_ref'].startswith('security-sim://audit/'))
        self.assertIs(result['executable'], False)
        self.assertIs(result['operationalReady'], False)
        self.assertEqual(result['authority'], 'SIMULATION_ONLY')

    def test_02_absent_policy_match_denied(self):
        result = self.admit(req(resource='trainos.control'))
        self.assertEqual(result['decision'], 'DENY')
        self.assertEqual(result['reason'], 'DEFAULT_DENY')

    def test_03_principal_mismatch_denied(self):
        result = self.admit(broker='security-auditor')
        self.assertEqual(result['reason'], 'IDENTITY_MISMATCH')

    def test_04_explicit_critical_actions_all_denied(self):
        for action in ('issue', 'recover', 'override', 'actuate', 'configure', 'admin'):
            with self.subTest(action=action):
                result = self.admit(req(action=action))
                self.assertEqual(result['reason'], 'PRIVILEGED_ACTION_UNAVAILABLE')

    def test_05_energy_simulation_not_executable(self):
        result = self.admit(req('energy-simulator','energy.scenario','simulate'), 'energy-simulator')
        self.assertEqual(result['decision'], 'ALLOW')
        self.assertIs(result['executable'], False)

    def test_06_auditor_role_limited_to_its_resource(self):
        allowed = self.admit(req('security-auditor','security.audit','read'), 'security-auditor')
        denied = self.admit(req('security-auditor','trainos.telemetry','read'), 'security-auditor')
        self.assertEqual((allowed['decision'], denied['decision']), ('ALLOW','DENY'))

    def test_07_request_replay_is_rejected(self):
        value = req()
        self.admit(value)
        with self.assertRaisesRegex(AdmissionUnavailable, 'REPLAY_DETECTED'):
            self.admit(value)

    def test_08_replay_across_two_instances_is_rejected(self):
        other = LocalSimulation(self.path, self.key)
        value = req()
        self.admit(value)
        with self.assertRaisesRegex(AdmissionUnavailable, 'REPLAY_DETECTED'):
            other.admit(value, simulated_broker_principal='trainos-observer')

    def test_09_new_request_does_not_change_old_audit_record(self):
        first = self.admit()
        self.admit(req(resource='rail.brake', action='actuate'))
        with db_connection(self.path) as connection:
            records = connection.execute('SELECT payload FROM audit_events ORDER BY seq').fetchall()
        self.assertEqual(len(records), 2)
        self.assertEqual(json.loads(records[0][0])['request']['request_id'], first['request_id'])
        self.assertEqual(len(self.sim.audit_tip()), 64)

    def test_10_modified_payload_detected(self):
        self.admit()
        with db_connection(self.path) as connection:
            connection.execute("UPDATE audit_events SET payload=? WHERE seq=1", (b'{}',))
        with self.assertRaisesRegex(AdmissionUnavailable, 'AUDIT_SIGNATURE_INVALID'):
            self.admit()

    def test_11_modified_chain_link_detected(self):
        self.admit()
        self.admit()
        with db_connection(self.path) as connection:
            connection.execute("UPDATE audit_events SET previous=? WHERE seq=2", ('f'*64,))
        with self.assertRaisesRegex(AdmissionUnavailable, 'AUDIT_CHAIN_BROKEN'):
            self.admit()

    def test_12_truncated_chain_detected_by_live_process_tip(self):
        self.admit()
        self.admit()
        with db_connection(self.path) as connection:
            connection.execute('DELETE FROM audit_events WHERE seq=2')
        with self.assertRaisesRegex(AdmissionUnavailable, 'IN_PROCESS_AUDIT_ROLLBACK'):
            self.admit()

    def test_13_new_instance_detects_tampered_body(self):
        self.admit()
        with db_connection(self.path) as connection:
            connection.execute('UPDATE audit_events SET digest=?', ('f'*64,))
        second = LocalSimulation(self.path, self.key)
        with self.assertRaisesRegex(AdmissionUnavailable, 'AUDIT_SIGNATURE_INVALID'):
            second.admit(req(), simulated_broker_principal='trainos-observer')

    def test_14_rotated_key_blocks_existing_audit(self):
        with self.assertRaisesRegex(AdmissionUnavailable, 'AUDIT_KEY_MISMATCH'):
            LocalSimulation(self.path, secrets.token_bytes(32))

    def test_15_missing_database_live_process_fails_closed(self):
        self.admit()
        self.path.unlink()
        with self.assertRaises(AdmissionUnavailable):
            self.admit()

    def test_16_policy_version_pinned(self):
        with self.assertRaisesRegex(RequestRejected, 'POLICY_VERSION_MISMATCH'):
            self.admit(req(policy_version='old-version'))

    def test_17_unknown_policy_disabled(self):
        with self.assertRaises(ValueError):
            LocalSimulation(self.path, self.key, policy_version='SEC-POLICY-0.2')

    def test_18_production_fence_not_affected_by_environment(self):
        with self.assertRaisesRegex(ProductionBlocked, 'NO_GO'):
            LocalSimulation.require_production_admission()

    def test_19_key_length(self):
        for bad in (b'', b'fixed-test-key'):
            with self.assertRaises(ValueError):
                LocalSimulation(self.path, bad)

    def test_20_concurrent_unique_requests_all_logged(self):
        requests = [req() for _ in range(20)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            decisions = list(ex.map(lambda r: self.admit(r), requests))
        self.assertEqual(len({x['audit_ref'] for x in decisions}), 20)
        with db_connection(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM audit_events').fetchone()[0], 20)

    def test_21_concurrent_replay_exactly_one_accepted(self):
        request = req()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(self.admit, request) for _ in range(12)]
            outcomes = []
            for future in futures:
                try:
                    outcomes.append(future.result()['decision'])
                except AdmissionUnavailable:
                    outcomes.append('REPLAY_REJECTED')
        self.assertEqual(outcomes.count('ALLOW'), 1)
        self.assertEqual(outcomes.count('REPLAY_REJECTED'), 11)

    def test_22_read_only_db_fails_closed_via_corruption(self):
        self.admit()
        with db_connection(self.path) as con:
            con.execute('DROP TABLE audit_events')
        with self.assertRaises(AdmissionUnavailable):
            self.admit()

    def test_23_unknown_request_fields_rejected(self):
        value = req()
        value['permit'] = 'granted'
        with self.assertRaisesRegex(RequestRejected, 'INVALID_REQUEST_FIELDS'):
            self.admit(value)

    def test_24_missing_fields_rejected(self):
        value = req()
        del value['resource']
        with self.assertRaisesRegex(RequestRejected, 'INVALID_REQUEST_FIELDS'):
            self.admit(value)

    def test_25_wrong_request_types_rejected(self):
        value = req()
        value['principal_id'] = True
        with self.assertRaisesRegex(RequestRejected, 'INVALID_REQUEST_TYPE'):
            self.admit(value)

    def test_26_non_uuid_or_noncanonical_uuid_rejected(self):
        for bad in ('x', str(uuid.uuid1()), str(uuid.uuid4()).upper()):
            with self.subTest(bad=bad), self.assertRaisesRegex(RequestRejected, 'INVALID_REQUEST_ID'):
                self.admit({**req(), 'request_id': bad})

    def test_27_malformed_resource_rejected(self):
        for bad in ('', '../root', 'a b', 'a' * 129):
            with self.subTest(bad=bad), self.assertRaisesRegex(RequestRejected, 'INVALID_LABEL'):
                self.admit({**req(), 'resource': bad})

    def test_28_unknown_action_rejected(self):
        with self.assertRaisesRegex(RequestRejected, 'UNREGISTERED_ACTION'):
            self.admit(req(action='execute_anything'))

    def test_29_json_duplicate_key_rejected(self):
        raw = json.dumps(req()).encode().replace(b'"resource":', b'"resource":"x","resource":')
        with self.assertRaisesRegex(RequestRejected, 'DUPLICATE_JSON_KEY'):
            parse_request_json(raw)

    def test_30_json_oversize_and_invalid_utf8_rejected(self):
        with self.assertRaisesRegex(RequestRejected, 'INVALID_FRAME_SIZE'):
            parse_request_json(b'x'*4097)
        with self.assertRaisesRegex(RequestRejected, 'INVALID_JSON'):
            parse_request_json(b'\xff')

    def test_31_json_roundtrip_valid(self):
        original = req()
        self.assertEqual(parse_request_json(json.dumps(original).encode()), original)

    def test_32_no_audit_on_malformed_input(self):
        with self.assertRaises(RequestRejected):
            self.admit({})
        with db_connection(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM audit_events').fetchone()[0], 0)

    def test_33_missing_ledger_parent_refused(self):
        with self.assertRaises(ValueError):
            LocalSimulation(Path(self.temp.name) / 'absent' / 'audit.db', self.key)

    def test_34_bad_json_numeric_constant_refused(self):
        raw = json.dumps(req()).encode().replace(b'"resource": "trainos.telemetry"',
                                               b'"resource": NaN')
        with self.assertRaises(RequestRejected):
            parse_request_json(raw)

    def test_35_audit_write_failure_cannot_return_allow(self):
        with db_connection(self.path) as con:
            con.execute("CREATE TRIGGER deny_audit BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT, 'storage-denied'); END")
        with self.assertRaisesRegex(AdmissionUnavailable, 'AUDIT_WRITE_FAILED'):
            self.admit()
        with db_connection(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM audit_events').fetchone()[0], 0)

    def test_36_full_database_rollback_after_restart_is_not_protected(self):
        # Explicit test of missing independent root: no production assurance inferred.
        self.admit()
        self.path.unlink()
        for ext in ('-wal', '-shm'):
            Path(str(self.path) + ext).unlink(missing_ok=True)
        restored = LocalSimulation(self.path, self.key)
        decision = restored.admit(req(), simulated_broker_principal='trainos-observer')
        self.assertEqual(decision['decision'], 'ALLOW')  # known simulation weakness
        with self.assertRaises(ProductionBlocked):
            restored.require_production_admission()


if __name__ == '__main__':
    unittest.main()
