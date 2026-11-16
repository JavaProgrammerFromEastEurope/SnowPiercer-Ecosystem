"""ISLAND-GEO-022: observed OS security gate, not self-reported assurances.

Mere owner/mode/UID matching is NOT MAC confinement against same-UID code.
Without a hardware-backed monotonic root + independent review of loaded MAC
rules + independently managed lifecycle, STRICT production must fail closed.
"""
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path

from .anchored_admission import AdmissionDenied


def _read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return ''


def _char_device(path):
    try:
        return stat.S_ISCHR(Path(path).stat().st_mode)
    except OSError:
        return False


@dataclass(frozen=True)
class HostSecurityEvidence:
    linux: bool
    rootless_service: bool
    kernel_lsm_enforcing: bool
    current_lsm_label: str
    independent_service_manager: bool
    tpm_device_present: bool
    verified_hardware_monotonic_root: bool
    verified_same_uid_mac_fence: bool
    verified_service_manager_policy: bool
    reasons: tuple

    @property
    def production_go(self):
        return not self.reasons


def observe_host_security():
    """Queries host state only. No user-provided booleans can grant GO."""
    linux = platform.system() == 'Linux'
    selinux = _read('/sys/fs/selinux/enforce') == '1'
    apparmor = _read('/sys/module/apparmor/parameters/enabled').lower() in ('y','yes','1')
    label = _read('/proc/self/attr/current')
    lsm_enforcing = selinux or (apparmor and label.endswith('(enforce)'))
    manager = _read('/proc/1/comm') == 'systemd' and Path('/run/systemd/system').is_dir()
    tpm = _char_device('/dev/tpmrm0') or _char_device('/dev/tpm0')
    # A TPM device or LSM mode is NOT a monotonic root attestation or a proof
    # that rules forbid same-UID legacy bypass. No accepted provider exists yet.
    root_verified = False
    mac_verified = False
    lifecycle_verified = False
    checks = (
        ('non-Linux kernel', linux),
        ('privileged service UID', os.geteuid() != 0),
        ('enforcing kernel LSM not observable', lsm_enforcing),
        ('systemd PID1 service manager not observable', manager),
        ('TPM device not observable', tpm),
        ('independent hardware monotonic root attestation not verified', root_verified),
        ('broker same-UID legacy MAC policy not independently verified', mac_verified),
        ('independent service lifecycle and policy not independently verified', lifecycle_verified),
    )
    return HostSecurityEvidence(linux,os.geteuid()!=0,lsm_enforcing,label,manager,tpm,
                                root_verified,mac_verified,lifecycle_verified,
                                tuple(reason for reason, yes in checks if not yes))


def require_production_security():
    evidence = observe_host_security()
    if not evidence.production_go:
        raise AdmissionDenied('production admission BLOCKED/NO-GO: ' + '; '.join(evidence.reasons))
    return evidence


def require_separated_roles(client_uid, service_uid, broker_uid, witness_uid, permit_uid, root_uid):
    uids = (client_uid, service_uid, broker_uid, witness_uid, permit_uid, root_uid)
    if any(type(v) is not int or v <= 0 for v in uids) or len(set(uids)) != 6:
        raise AdmissionDenied('six distinct unprivileged trust roles mandatory')
    return uids


class StrictProductionBrokerMixin:
    """Applied BEFORE database mutation, permit consume or IPC bind.

    Fail-closed by construction until all independently attested OS controls
    have been integrated and certified. Lab broker is separately named.
    """
    def preflight(self):
        require_production_security()
        return super().preflight()
