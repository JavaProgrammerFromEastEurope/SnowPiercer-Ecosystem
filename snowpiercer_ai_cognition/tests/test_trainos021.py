"""AI-CORE-021 proposal provenance, bounded context and no-actuation contracts."""
import dataclasses
import concurrent.futures
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from ai_cognition import (ReplayStore, TrustedAdmission, signed_envelope,
    TrainOSRecommendationBridge, ProposalRejected, assess)
from ai_cognition.admission import AdmissionRejected
from ai_cognition.lifecycle import RecoveryRequired

NOW = 2000000000
SOURCE_KEY = b'S' * 32
PROPOSAL_KEY = b'P' * 32
OBS = {'event_id': 'event021', 'source': 'trainos', 'severity': 'critical',
       'description': 'TrainOS review observation'}


class TrainOS021Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = ReplayStore(str(Path(temp.name) / 'replay.sqlite'))
        self.addCleanup(self.store.close)
        self.clock = NOW
        self.gate = TrustedAdmission({'trainos': SOURCE_KEY}, self.store, clock=lambda: self.clock)
        self.bridge = TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, clock=lambda: self.clock)
        self.context = {'context_id': 'trainos-operational-state', 'revision': 7,
                        'observed_at': NOW, 'state_sha256': 'a' * 64}

    def envelope(self, **changes):
        return signed_envelope({**OBS, **changes}, NOW, 'nonce-021-0000001', SOURCE_KEY)

    def issue(self):
        return self.bridge.issue(self.envelope(), self.context)

    def sign_body(self, proposal):
        body = {k: v for k, v in proposal.items() if k != 'mac'}
        raw = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        return dict(body, mac=hmac.new(PROPOSAL_KEY, raw, hashlib.sha256).hexdigest())

    def test_authenticated_proposal_is_context_bound_and_non_actionable(self):
        proposal = self.issue()
        result = self.bridge.verify_for_review(proposal, self.context)
        self.assertEqual(result.decision.value, 'ESCALATE')
        self.assertEqual(result.evidence_sha256, assess(OBS).evidence_sha256)
        self.assertEqual(result.context_revision, 7)
        self.assertEqual(result.context_sha256, 'a' * 64)
        self.assertEqual(result.expires_at, NOW + 30)
        self.assertFalse(result.actionable)
        self.assertTrue(result.operator_review_required)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.actionable = True

    def test_untrusted_assessment_callback_cannot_issue(self):
        for gateway in [assess, object(), lambda payload: assess(OBS)]:
            with self.assertRaisesRegex(TypeError, 'TRUSTED_ADMISSION_REQUIRED'):
                TrainOSRecommendationBridge(gateway, PROPOSAL_KEY)

    def test_bad_configuration_fails_closed(self):
        for key in [b'short', 'a' * 32, None]:
            with self.assertRaises(ValueError):
                TrainOSRecommendationBridge(self.gate, key)
        for key, value in [('proposal_ttl', True), ('proposal_ttl', 0),
                           ('proposal_ttl', 301), ('max_context_age', -1),
                           ('max_context_age', False), ('max_context_age', 3601)]:
            with self.assertRaises(ValueError):
                TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, **{key: value})

    def test_stale_context_refused_before_replay_reservation(self):
        stale = {**self.context, 'observed_at': NOW - 120}
        with self.assertRaisesRegex(ProposalRejected, 'STALE_CONTEXT'):
            self.bridge.issue(self.envelope(), stale)
        self.assertEqual(self.store._db.execute('SELECT COUNT(*) FROM seen').fetchone()[0], 0)
        self.assertEqual(self.issue()['event_id'], OBS['event_id'])

    def test_future_context_rejected(self):
        with self.assertRaisesRegex(ProposalRejected, 'FUTURE_CONTEXT'):
            self.bridge.issue(self.envelope(), {**self.context, 'observed_at': NOW + 1})

    def test_invalid_context_shape_and_types_rejected(self):
        contexts = [None, {}, {**self.context, 'command': 'stop'},
            {**self.context, 'revision': True}, {**self.context, 'revision': -1},
            {**self.context, 'observed_at': True}, {**self.context, 'state_sha256': 'G' * 64},
            {**self.context, 'context_id': 'not a context id'}]
        for context in contexts:
            with self.subTest(context=context), self.assertRaisesRegex(ProposalRejected, 'INVALID_CONTEXT'):
                self.bridge.issue(self.envelope(), context)

    def test_input_authentication_and_replay_remain_mandatory(self):
        forged = {**self.envelope(), 'mac': '0' * 64}
        with self.assertRaisesRegex(AdmissionRejected, 'AUTHENTICATION_FAILED'):
            self.bridge.issue(forged, self.context)
        self.issue()
        with self.assertRaisesRegex(AdmissionRejected, 'REPLAY_DETECTED'):
            self.issue()

    def test_changed_context_identity_revision_digest_or_timestamp_rejected(self):
        proposal = self.issue()
        for field, value in [('context_id', 'other-context'), ('revision', 8),
                              ('state_sha256', 'b' * 64), ('observed_at', NOW - 1)]:
            with self.subTest(field=field), self.assertRaisesRegex(ProposalRejected, 'CONTEXT_CHANGED'):
                self.bridge.verify_for_review(proposal, {**self.context, field: value})

    def test_tampered_proposal_authentication_fails(self):
        proposal = self.issue()
        for key, value in [('event_id', 'different-event'), ('actionable', True),
                           ('expires_at', NOW + 100), ('operator_review_required', False),
                           ('context', {**self.context, 'revision': 8})]:
            with self.subTest(field=key), self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_AUTHENTICATION_FAILED'):
                self.bridge.verify_for_review({**proposal, key: value}, self.context)

    def test_valid_hmac_does_not_allow_command_authority_or_extended_ttl(self):
        proposal = self.issue()
        for changes in [{'actionable': True}, {'actionable': 0},
                        {'operator_review_required': False}, {'expires_at': NOW + 31},
                        {'target': 'Rail'}, {'schema': 'unsupported'},
                        {'decision': ['ESCALATE']}, {'reason_code': 'AUTO_EXECUTE'}]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ProposalRejected, 'INVALID_PROPOSAL'):
                self.bridge.verify_for_review(self.sign_body({**proposal, **changes}), self.context)

    def test_expiry_boundary_is_exclusive(self):
        proposal = self.issue()
        self.clock = NOW + 29
        self.assertFalse(self.bridge.verify_for_review(proposal, self.context).actionable)
        self.clock = NOW + 30
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_EXPIRED'):
            self.bridge.verify_for_review(proposal, self.context)

    def test_context_age_caps_proposal_lifetime(self):
        context = {**self.context, 'observed_at': NOW - 115}
        proposal = self.bridge.issue(self.envelope(), context)
        self.assertEqual(proposal['expires_at'], NOW + 5)
        self.clock += 5
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_EXPIRED'):
            self.bridge.verify_for_review(proposal, context)

    def test_future_proposal_is_refused_after_clock_rollback(self):
        proposal = self.issue()
        self.clock = NOW - 1
        with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
            self.bridge.verify_for_review(proposal, self.context)
        # A newly constructed verifier has no earlier wall-clock sample, but
        # must still reject a proposal whose issued_at is in its future.
        fresh = TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, clock=lambda: self.clock)
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_FROM_FUTURE'):
            fresh.verify_for_review(proposal, self.context)

    def test_expired_proposal_cannot_revive_after_clock_rollback(self):
        proposal = self.issue()
        self.clock = proposal['expires_at']
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_EXPIRED'):
            self.bridge.verify_for_review(proposal, self.context)
        self.clock = proposal['issued_at'] + 1
        with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
            self.bridge.verify_for_review(proposal, self.context)
        self.clock = proposal['expires_at']
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_EXPIRED'):
            self.bridge.verify_for_review(proposal, self.context)

    def test_stale_issue_attempt_advances_barrier_for_subsequent_review(self):
        proposal = self.issue()
        self.clock = NOW + 120
        with self.assertRaisesRegex(ProposalRejected, 'STALE_CONTEXT'):
            self.bridge.issue(self.envelope(event_id='later-event'), self.context)
        self.clock = NOW + 1
        with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
            self.bridge.verify_for_review(proposal, self.context)

    def test_malformed_and_bad_auth_review_attempts_advance_barrier(self):
        proposal = self.issue()
        for invalid in [None, {**proposal, 'mac': '0' * 64}]:
            # Separate bridge fences isolate the independent invalid-call cases.
            bridge = TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, clock=lambda: self.clock)
            self.clock = NOW + 40
            with self.subTest(invalid=invalid), self.assertRaises(ProposalRejected):
                bridge.verify_for_review(invalid, self.context)
            self.clock = NOW + 1
            with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
                bridge.verify_for_review(proposal, self.context)

    def test_invalid_context_issue_attempt_advances_barrier(self):
        proposal = self.issue()
        self.clock = NOW + 40
        with self.assertRaisesRegex(ProposalRejected, 'INVALID_CONTEXT'):
            self.bridge.issue(self.envelope(event_id='invalid-context'), {})
        self.clock = NOW + 1
        with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
            self.bridge.verify_for_review(proposal, self.context)

    def test_fractional_clock_rollback_is_not_hidden_by_integer_wire_time(self):
        self.clock = NOW + 0.9
        proposal = self.issue()
        self.clock = NOW + 0.8
        with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
            self.bridge.verify_for_review(proposal, self.context)

    def test_concurrent_reviews_share_the_same_thread_safe_clock_barrier(self):
        proposal = self.issue()
        self.clock = NOW + 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(
                lambda _: self.bridge.verify_for_review(proposal, self.context), range(64)))
        self.assertTrue(all(result.actionable is False for result in results))
        self.clock = NOW + 0.5
        with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
            self.bridge.verify_for_review(proposal, self.context)

    def test_fresh_bridge_explicitly_has_no_persisted_clock_high_watermark(self):
        proposal = self.issue()
        self.clock = proposal['expires_at']
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_EXPIRED'):
            self.bridge.verify_for_review(proposal, self.context)
        self.clock = NOW + 1
        fresh = TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, clock=lambda: self.clock)
        # The documented process-local fence is not an external monotonic clock.
        self.assertFalse(fresh.verify_for_review(proposal, self.context).actionable)

    def test_invalid_or_missing_clock_is_fail_closed(self):
        for value in [True, float('nan'), float('inf'), -1, 'now', 10**1000]:
            bridge = TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, clock=lambda: value)
            with self.subTest(value=str(value)[:30]), self.assertRaisesRegex(ProposalRejected, 'CLOCK_UNAVAILABLE'):
                bridge.issue(self.envelope(), self.context)
        def fail_clock():
            raise OSError('sensitive clock details')
        bridge = TrainOSRecommendationBridge(self.gate, PROPOSAL_KEY, clock=fail_clock)
        with self.assertRaisesRegex(ProposalRejected, '^CLOCK_UNAVAILABLE$'):
            bridge.issue(self.envelope(), self.context)

    def test_changed_output_trust_key_refuses_existing_proposal(self):
        proposal = self.issue()
        other = TrainOSRecommendationBridge(self.gate, b'Q' * 32, clock=lambda: NOW)
        with self.assertRaisesRegex(ProposalRejected, 'PROPOSAL_AUTHENTICATION_FAILED'):
            other.verify_for_review(proposal, self.context)

    def test_malformed_and_oversized_proposals_rejected(self):
        proposal = self.issue()
        for candidate in [None, [], {}, {**proposal, 'mac': 1},
                          {**proposal, 'unexpected': True}]:
            with self.subTest(candidate=candidate), self.assertRaises(ProposalRejected):
                self.bridge.verify_for_review(candidate, self.context)
        with self.assertRaisesRegex(ProposalRejected, 'OVERSIZED_PROPOSAL'):
            self.bridge.verify_for_review({**proposal, 'payload': 'X' * 9000}, self.context)

    def test_context_is_rechecked_after_admission(self):
        original = self.gate.admit
        def delayed(envelope):
            result = original(envelope)
            self.clock = NOW + 120
            return result
        with patch.object(self.gate, 'admit', side_effect=delayed):
            with self.assertRaisesRegex(ProposalRejected, 'STALE_CONTEXT'):
                self.issue()
        self.assertEqual(self.store._db.execute('SELECT COUNT(*) FROM seen').fetchone()[0], 1)

    def test_backward_clock_during_admission_does_not_release_proposal(self):
        original = self.gate.admit
        def delayed(envelope):
            result = original(envelope)
            self.clock = NOW - 1
            return result
        with patch.object(self.gate, 'admit', side_effect=delayed):
            with self.assertRaisesRegex(ProposalRejected, 'CLOCK_MOVED_BACKWARDS'):
                self.issue()

    def test_gateway_cannot_release_actionable_or_mismatched_result(self):
        for result in [dataclasses.replace(assess(OBS), actionable=True),
                       dataclasses.replace(assess(OBS), evidence_sha256='b' * 64)]:
            with self.subTest(result=result), patch.object(self.gate, 'admit', return_value=result):
                with self.assertRaises(ProposalRejected):
                    self.issue()

    def test_repeat_review_is_explicitly_not_actuation_consumption(self):
        proposal = self.issue()
        first = self.bridge.verify_for_review(proposal, self.context)
        self.assertEqual(first, self.bridge.verify_for_review(proposal, self.context))
        self.assertFalse(first.actionable)


class JournaledBridge021Tests(unittest.TestCase):
    def test_latest_journaled_gateway_produces_context_bound_review(self):
        from ai_cognition import (HardenedRotationManager, IndependentAnchor,
                                 AnchoredAdmissionGateway, AuditCheckpoint)
        from ai_cognition.production014 import PhaseJournal, JournaledAdmissionGateway
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ReplayStore(str(root / 'db'))
            try:
                manager = HardenedRotationManager(store, root / 'legacy', {'trainos': SOURCE_KEY},
                    independent_anchor=IndependentAnchor(root / 'independent', b'A' * 32),
                    recovery_secret=b'R' * 32, bootstrap=True)
                manager.provision('trainos')
                anchored = AnchoredAdmissionGateway(manager, b'U' * 32,
                    checkpoint=AuditCheckpoint(root / 'checkpoint', b'C' * 32), bootstrap=True)
                journal = PhaseJournal(root / 'phase', b'J' * 32)
                journal.write('CLEAN', *anchored.verify())
                latest = JournaledAdmissionGateway(anchored, journal, b'O' * 32)
                now = int(time.time())
                bridge = TrainOSRecommendationBridge(latest, PROPOSAL_KEY, clock=lambda: now)
                context = {'context_id': 'live-trainos', 'revision': 1,
                           'observed_at': now, 'state_sha256': 'f' * 64}
                proposal = bridge.issue(signed_envelope(OBS, now, 'nonce-latest-0211', SOURCE_KEY), context)
                self.assertFalse(bridge.verify_for_review(proposal, context).actionable)
                self.assertEqual(latest.verify()[0], 1)
                journal.write('PREPARED', *latest.verify())
                with self.assertRaisesRegex(RecoveryRequired, 'PHASE_RECOVERY_REQUIRED'):
                    bridge.issue(signed_envelope({**OBS, 'event_id': 'second021'}, now,
                                                 'nonce-latest-0212', SOURCE_KEY), context)
            finally:
                store.close()


class PortableExistingContracts021Tests(unittest.TestCase):
    def test_operator_gate_requires_no_privileged_fixture(self):
        from ai_cognition.production016 import cold_recover
        with self.assertRaisesRegex(RecoveryRequired, 'OPERATOR_VERIFICATION_REQUIRED'):
            cold_recover('not-opened', {}, operator_verified=False)

    def test_legacy_cli_fencing_requires_no_privileged_fixture(self):
        for module in ['production012', 'production013']:
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, '-m', 'ai_cognition.' + module, 'unused'],
                                        capture_output=True, text=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('LEGACY_PRODUCTION_ENTRYPOINT_DISABLED', result.stderr)


if __name__ == '__main__':
    unittest.main()
