"""Stage 010 deployment preflight. No claim of production certification.

This module deliberately refuses unsafe layouts instead of silently degrading to
single-UID testing. Filesystem fencing requires an external privileged installer.
"""
import os
import stat
from pathlib import Path
from dataclasses import dataclass
from .secure import AdmissionError
from .stage009 import ClientBoundLogisticsService

@dataclass(frozen=True)
class IsolationPolicy:
    service_uid: int
    witness_uid: int
    authority_uid: int
    client_uids: tuple

    def validate(self):
        identities = (self.service_uid, self.witness_uid, self.authority_uid) + tuple(self.client_uids)
        if not self.client_uids or any(type(uid) is not int or uid < 1 for uid in identities):
            raise AdmissionError('invalid isolation identities')
        if len(set(identities)) != len(identities):
            raise AdmissionError('distinct UIDs required for service, witness, authority and clients')
        return True


def require_private_directory(path, owner_uid):
    """Check existing deployment path; never create/chmod a privileged path."""
    path = Path(path)
    if path.is_symlink():
        raise AdmissionError('symlink deployment directory')
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise AdmissionError('deployment directory missing') from exc
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner_uid or info.st_mode & 0o077:
        raise AdmissionError('unsafe deployment directory')
    return True


def verify_isolated_deployment(policy, *, service_root, witness_root, authority_root):
    """Fail closed on wrong runtime UID or ownership; not a proof of OS sandboxing."""
    policy.validate()
    if os.geteuid() != policy.service_uid:
        raise AdmissionError('service runtime UID mismatch')
    require_private_directory(service_root, policy.service_uid)
    require_private_directory(witness_root, policy.witness_uid)
    require_private_directory(authority_root, policy.authority_uid)
    return True


class IsolatedLogisticsService(ClientBoundLogisticsService):
    """Opt-in production-candidate admission with strict deployment preflight.

    Legacy library interfaces remain available for compatibility; deployment
    isolation MUST be enforced by the host OS and an independently reviewed policy.
    """
    def __init__(self, root, uid_roles, witness_socket, permit_socket, *,
                 isolation_policy, witness_root, authority_root,
                 recovery_scope='logistics-recovery', timeout=2.0):
        verify_isolated_deployment(isolation_policy, service_root=root,
                                   witness_root=witness_root, authority_root=authority_root)
        if set(map(int, uid_roles)) - set(isolation_policy.client_uids):
            raise AdmissionError('role assigned to unapproved client UID')
        super().__init__(root, uid_roles, witness_socket, permit_socket,
                         recovery_scope=recovery_scope, timeout=timeout)
        self.isolation_policy = isolation_policy
        self.witness_root = str(witness_root)
        self.authority_root = str(authority_root)

    def _admit(self):
        verify_isolated_deployment(self.isolation_policy, service_root=self.root,
                                   witness_root=self.witness_root,
                                   authority_root=self.authority_root)
        return super()._admit()
