"""AI-CORE-021 bounded integration probe; emits one JSON object, no actuation."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import tempfile

from ai_cognition import (ReplayStore, TrustedAdmission, signed_envelope,
    TrainOSRecommendationBridge, ProposalRejected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correlation-id', required=True)
    args = parser.parse_args()
    if not 1 <= len(args.correlation_id) <= 256:
        parser.error('correlation-id must contain 1 to 256 characters')
    now = 2000000000  # deterministic fixture clock, not operational telemetry
    clock = [now]
    source_key, proposal_key = secrets.token_bytes(32), secrets.token_bytes(32)
    observation = {'event_id': 'probe-' + hashlib.sha256(args.correlation_id.encode()).hexdigest(),
                   'source': 'trainos', 'severity': 'warning',
                   'description': 'Read-only TrainOS integration conformance fixture'}
    context = {'context_id': 'trainos-integration-fixture', 'revision': 1,
               'observed_at': now, 'state_sha256': hashlib.sha256(b'fixture-state').hexdigest()}
    with tempfile.TemporaryDirectory() as directory:
        store = ReplayStore(str(Path(directory) / 'probe.sqlite'))
        try:
            gate = TrustedAdmission({'trainos': source_key}, store, clock=lambda: clock[0])
            bridge = TrainOSRecommendationBridge(gate, proposal_key, clock=lambda: clock[0])
            proposal = bridge.issue(signed_envelope(observation, now,
                secrets.token_hex(16), source_key), context)
            verified = bridge.verify_for_review(proposal, context)
            positive = verified.actionable is False and verified.operator_review_required is True
            try:
                bridge.verify_for_review(proposal, {**context, 'revision': 2})
                changed_context_refused = False
            except ProposalRejected as exc:
                changed_context_refused = str(exc) == 'CONTEXT_CHANGED'
            try:
                bridge.verify_for_review({**proposal, 'actionable': True}, context)
                tamper_refused = False
            except ProposalRejected as exc:
                tamper_refused = str(exc) == 'PROPOSAL_AUTHENTICATION_FAILED'
            clock[0] = proposal['expires_at']
            try:
                bridge.verify_for_review(proposal, context)
                expiry_refused = False
            except ProposalRejected as exc:
                expiry_refused = str(exc) == 'PROPOSAL_EXPIRED'
            clock[0] = now + 1
            try:
                bridge.verify_for_review(proposal, context)
                rollback_refused = False
            except ProposalRejected as exc:
                rollback_refused = str(exc) == 'CLOCK_MOVED_BACKWARDS'
        finally:
            store.close()
    checks = [{'name': 'authenticated_context_bound_review_only_proposal', 'passed': positive},
              {'name': 'changed_trainos_revision_rejected', 'passed': changed_context_refused},
              {'name': 'authority_escalation_tamper_rejected', 'passed': tamper_refused},
              {'name': 'expired_proposal_clock_rollback_revival_rejected',
               'passed': expiry_refused and rollback_refused}]
    passed = all(check['passed'] for check in checks)
    print(json.dumps({'schema': 'snowpiercer.integration-probe.v1', 'moduleId': 'SP-AI',
        'stageId': 'AI-CORE-021', 'correlationId': args.correlation_id,
        'status': 'ok' if passed else 'failed', 'checks': checks,
        'operationalReady': False}, separators=(',', ':')))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
