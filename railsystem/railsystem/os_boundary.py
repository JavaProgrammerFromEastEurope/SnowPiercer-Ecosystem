"""RAIL-TRUST-012: OS identity contract; strict, non-privilege-escalating check.

No installation, user creation, chmod, chown, or systemd startup is performed.
Only deployment-owned paths are checked; no claim about other legacy callers.
"""
from __future__ import annotations
import os
import stat
from pathlib import Path
from .trusted_admission import AdmissionError
from .provider_ipc import UnixAnchorClient, UnixPermitLedgerClient

class DeploymentDenied(AdmissionError):
    pass


def _dir(path, uid, gid, mode):
    if not Path(path).is_absolute():
        raise DeploymentDenied('absolute directories required')
    info = Path(path).lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
            or info.st_gid != gid or stat.S_IMODE(info.st_mode) != mode):
        raise DeploymentDenied('OS directory ownership/mode mismatch')


def validate_production_config(config):
    """Strict four-distinct-UID deployment contract; root is not an application role."""
    if not isinstance(config, dict) or set(config) != {
        'schema_version', 'uids', 'transport_gid', 'state_dir', 'ipc_dir',
        'witness_socket', 'permit_socket', 'recovery_public_key_file', 'permit_file'}:
        raise DeploymentDenied('incomplete deployment contract')
    if config['schema_version'] != 1:
        raise DeploymentDenied('deployment schema mismatch')
    uids = config['uids']
    if not isinstance(uids, dict) or set(uids) != {'client', 'service', 'witness', 'recovery'}:
        raise DeploymentDenied('exactly four OS identities required')
    if any(type(v) is not int or v <= 0 for v in uids.values()) or len(set(uids.values())) != 4:
        raise DeploymentDenied('four distinct non-root UIDs required')
    gid = config['transport_gid']
    if type(gid) is not int or gid <= 0:
        raise DeploymentDenied('dedicated transport GID required')
    if os.geteuid() != uids['service']:
        raise DeploymentDenied('service must run as dedicated OS UID')
    _dir(config['state_dir'], uids['service'], os.getegid(), 0o700)
    _dir(config['ipc_dir'], uids['service'], gid, 0o750)
    for key in ('permit_file', 'recovery_public_key_file'):
        p = Path(config[key])
        if not p.is_absolute():
            raise DeploymentDenied('absolute protected credential path required')
        s = p.lstat()
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != uids['service']
                or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) not in (0o400, 0o600)):
            raise DeploymentDenied('unsafe recovery credential')
    anchor = UnixAnchorClient(config['witness_socket'], expected_uid=uids['witness'], expected_gid=gid)
    permits = UnixPermitLedgerClient(config['permit_socket'], expected_uid=uids['recovery'], expected_gid=gid)
    # Both authenticated endpoints must be responsive before any publication.
    anchor.read()
    if permits.check_ready() is not True:
        raise DeploymentDenied('permit provider unready')
    return anchor, permits
