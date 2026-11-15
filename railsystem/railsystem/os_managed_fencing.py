"""RAIL-TRUST-014/015: mandatory production isolation preflight.

No environment variable, mock LSM label, configuration flag or self-signed
quote enables production. A functioning external MAC/LSM policy enforcing
same-UID legacy API denial and an independent anti-rollback root are NOT
available in this laboratory, so all production entrypoints must fail closed.
"""
from __future__ import annotations
import os
from pathlib import Path
from .os_boundary import DeploymentDenied


def _read(path):
    try:
        return Path(path).read_text(encoding='utf8', errors='replace').strip('\x00\n')
    except (OSError, ValueError):
        return None


def assess_os_management(*, pid1_comm='/proc/1/comm', lsm_label='/proc/self/attr/current',
                         lsm_inventory='/sys/kernel/security/lsm',
                         proc_status='/proc/self/status'):
    """Diagnostics only. Caller-provided paths are for tests, NEVER authorization."""
    pid1 = _read(pid1_comm)
    label = _read(lsm_label)
    lsm = _read(lsm_inventory)
    proc = _read(proc_status) or ''
    status = {}
    for line in proc.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            if k in ('NoNewPrivs', 'Seccomp', 'CapEff'):
                status[k] = v.strip()
    blockers = [
        'independently audited monotonic root not connected',
        'no verified MAC/LSM policy denying same-UID legacy writes',
        'no deployed independent service-manager lifecycle evidence',
        'no independently protected durable permit custody',
        'no independently verified end-to-end crash/rollback matrix',
    ]
    return {'pid1': pid1, 'lsm_label': label, 'lsm_inventory': lsm,
            'no_new_privileges': status.get('NoNewPrivs'),
            'seccomp_mode': status.get('Seccomp'),
            'effective_capabilities': status.get('CapEff'),
            'dedicated_systemd_pid1': pid1 == 'systemd',
            'mac_profile_proven': False,
            'independent_monotonic_root_proven': False,
            'same_uid_legacy_fenced': False,
            'independent_service_manager_verified': False,
            'durable_permit_custody_verified': False,
            'status': 'BLOCKED', 'reason': '; '.join(blockers), 'blockers': blockers,
            'scope': 'diagnostic only; no authorization from /proc or self-attestation'}


def require_production_isolation():
    """Mandatory safety gate used by deployed write/recovery/release CLIs."""
    facts = assess_os_management()  # uses canonical kernel paths, never caller overrides
    raise DeploymentDenied('production isolation not attested: ' + facts['reason'])
