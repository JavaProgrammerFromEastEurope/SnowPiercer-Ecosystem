"""Bounded local LOG-CORE-021 integration smoke test, no hardware access."""
import argparse
import json
from pathlib import Path
import tempfile

from snowpiercer_logistics.core import Principal, ConflictError
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage021 import TimedLogisticsLedger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correlation-id', required=True)
    args = parser.parse_args()
    checks = []
    with tempfile.TemporaryDirectory(prefix='logistics-probe-') as directory:
        with TimedLogisticsLedger(Path(directory)/'ledger.sqlite', clock_ms=lambda: 1100) as ledger:
            principal = Principal('integration-probe-host', 'admin')
            command = {'schema_version': 1, 'command_id': args.correlation_id,
                       'issued_at_ms': 1000, 'ttl_ms': 1000, 'expected_events': 0,
                       'action': 'add_location', 'args': {'location_id': 'probe', 'kind': 'software-model'}}
            result = ledger.execute_envelope(principal, command)
            assert result == {'location_id': 'probe'}
            checks.append({'name': 'valid_envelope_commits_local_model', 'passed': True})
            assert ledger.execute_envelope(principal, command) == result
            assert ledger.verify(principal)['events'] == 1
            checks.append({'name': 'exact_replay_has_single_effect', 'passed': True})
            stale = dict(command, command_id=args.correlation_id+'-stale')
            try:
                ledger.execute_envelope(principal, stale)
            except ConflictError:
                checks.append({'name': 'stale_revision_rejected', 'passed': True})
            else:
                raise AssertionError('stale revision admitted')
            expired = dict(command, command_id=args.correlation_id+'-expired',
                           issued_at_ms=0, ttl_ms=1000, expected_events=1)
            try:
                ledger.execute_envelope(principal, expired)
            except AdmissionError:
                checks.append({'name': 'expired_command_rejected', 'passed': True})
            else:
                raise AssertionError('expired command admitted')
            assert ledger.verify(principal)['events'] == 1
            checks.append({'name': 'rejected_commands_have_no_effect', 'passed': True})
    print(json.dumps({'schema': 'snowpiercer.integration-probe.v1',
                      'moduleId': 'SP-LOG', 'stageId': 'LOG-CORE-021',
                      'correlationId': args.correlation_id, 'status': 'ok',
                      'checks': checks, 'operationalReady': False}, sort_keys=True))


if __name__ == '__main__':
    main()
