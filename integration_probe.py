"""SP-SAFE simulation-only integration probe; zero physical or production authority."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import secrets
import tempfile
import uuid
from security import LocalSimulation, AdmissionUnavailable, ProductionBlocked


def request(principal: str, resource: str, action: str, correlation: str) -> dict:
    return {'request_id': str(uuid.uuid4()), 'principal_id': principal,
            'resource': resource, 'action': action, 'policy_version': 'SEC-POLICY-0.1',
            'correlation_id': correlation}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--correlation-id', required=True)
    correlation = parser.parse_args().correlation_id
    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        sim = LocalSimulation(Path(tmp) / 'audit.db', secrets.token_bytes(32))
        positive = request('trainos-observer', 'trainos.telemetry', 'read', correlation)
        result = sim.admit(positive, simulated_broker_principal='trainos-observer')
        checks.append({'name': 'nonexecutable_simulation_allow_with_audit',
                       'passed': result['decision'] == 'ALLOW' and not result['executable']
                       and result['audit_ref'].startswith('security-sim://audit/')})
        try:
            sim.admit(positive, simulated_broker_principal='trainos-observer')
        except AdmissionUnavailable as exc:
            replay = str(exc) == 'REPLAY_DETECTED'
        else:
            replay = False
        checks.append({'name': 'duplicate_request_rejected', 'passed': replay})
        rejected = sim.admit(request('trainos-observer', 'rail.brake', 'actuate', correlation),
                             simulated_broker_principal='trainos-observer')
        checks.append({'name': 'privileged_actuation_denied_and_audited',
                       'passed': rejected['decision'] == 'DENY' and rejected['audit_ref'] != result['audit_ref']})
        try:
            LocalSimulation.require_production_admission()
        except ProductionBlocked:
            blocked = True
        else:
            blocked = False
        checks.append({'name': 'production_always_fail_closed', 'passed': blocked})
    passed = all(check['passed'] is True for check in checks)
    print(json.dumps({'schema': 'snowpiercer.integration-probe.v1', 'moduleId': 'SP-SAFE',
                      'stageId': 'SECURITY-v0.1.0', 'correlationId': correlation,
                      'status': 'ok' if passed else 'failed', 'checks': checks,
                      'operationalReady': False}, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
