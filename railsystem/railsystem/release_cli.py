"""Mandatory production software release CLI. No legacy unsigned option."""
import argparse
import json
from pathlib import Path
from .release_gate import write_report
from .trusted_admission import read_protected_json
from .unified_admission import admit as admit_unified
from .trusted_admission import AdmissionError
from .production_fencing import IndependentAnchorUnavailable

def main():
    parser = argparse.ArgumentParser()
    for name in ('baseline', 'attestation', 'trust', 'state-db'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if not args.state_dir or args.state_db:
            report = {'stage': 'RAIL-TRUST-004', 'status': 'BLOCKED', 'reason': 'anchored state-dir required; legacy state-db prohibited'}
        elif any(x is None for x in (args.baseline, args.attestation, args.trust)):
            report = {'stage': 'RAIL-TRUST-004', 'status': 'BLOCKED', 'reason': 'trusted inputs required'}
        else:
            # RAIL-TRUST-015: the public CLI is a production entrypoint;
            # do not rely solely on a missing provider's default exception.
            from .os_managed_fencing import require_production_isolation
            require_production_isolation()
            report = admit_unified(root,
                baseline=read_protected_json(args.baseline),
                attestation=read_protected_json(args.attestation),
                trust=read_protected_json(args.trust), state_dir=args.state_dir)
    except IndependentAnchorUnavailable:
        report = {'stage': 'RAIL-TRUST-012', 'status': 'BLOCKED', 'reason': 'independent monotonic anchor unavailable'}
    except (OSError, ValueError, TypeError) as exc:
        # DeploymentDenied is an unavailable mandatory prerequisite, not an
        # invalid cryptographic attestation or a reason to report PASS.
        from .os_boundary import DeploymentDenied
        if isinstance(exc, DeploymentDenied):
            report = {'stage': 'RAIL-TRUST-015', 'status': 'BLOCKED', 'reason': 'mandatory OS isolation unavailable'}
        else:
            report = {'stage': 'RAIL-TRUST-004', 'status': 'FAIL', 'reason': str(exc)}
    write_report(report, args.output)
    print('Release gate:', report['status'])
    return {'PASS': 0, 'FAIL': 1, 'BLOCKED': 2}[report['status']]

if __name__ == '__main__':
    raise SystemExit(main())
