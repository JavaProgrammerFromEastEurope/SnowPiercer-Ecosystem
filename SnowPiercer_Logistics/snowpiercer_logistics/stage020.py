"""LOG-CORE-020: fail-closed mandatory entrypoint and bounded crash evidence.

Experimental: no production certification. Previous library entrypoints remain intact.
"""
import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from .secure import AdmissionError
from .stage019 import TransactionAdmissionService
from .stage018 import classify_recovery

@dataclass(frozen=True)
class ProductionIdentityPolicy:
    service_uid: int
    witness_uid: int
    authority_uid: int
    client_uid: int

    def validate(self):
        values=(self.service_uid,self.witness_uid,self.authority_uid,self.client_uid)
        if any(type(x) is not int or x <= 0 for x in values) or len(set(values)) != 4:
            raise AdmissionError('four distinct non-root UIDs required')
        if os.geteuid()!=self.service_uid:
            raise AdmissionError('actual service UID mismatch')
        if not hasattr(socket,'SO_PEERCRED'):
            raise AdmissionError('kernel peer credentials unavailable')


def verify_endpoint(path, expected_uid):
    """Fail closed on symlinks, wrong owner and non-sockets.

    Does not close parent-directory TOCTOU or validate a live peer process.
    """
    p=Path(path)
    st=p.lstat()
    if not stat.S_ISSOCK(st.st_mode) or st.st_uid != expected_uid or st.st_mode & 0o002:
        raise AdmissionError('unsafe production endpoint')
    return (st.st_dev,st.st_ino)


class MandatoryProductionLogisticsService(TransactionAdmissionService):
    """Opt-in guarded entrypoint; untrusted deployments remain disabled."""
    def __init__(self, root, uid_roles, witness_socket, permit_socket, *,
                 identity_policy, certified=False, timeout=2.0, recovery_scope='logistics-recovery'):
        identity_policy.validate()
        if certified is not False:
            raise AdmissionError('caller-supplied certification forbidden')
        self.identity_policy=identity_policy
        super().__init__(root,uid_roles,witness_socket,permit_socket,
                         timeout=timeout,recovery_scope=recovery_scope)

    def _assert_endpoints(self):
        super()._assert_endpoints()
        if verify_endpoint(self.witness_socket,self.identity_policy.witness_uid) == verify_endpoint(self.permit_socket,self.identity_policy.authority_uid):
            raise AdmissionError('endpoint inode collision')

    def start(self):
        # The available integration evidence is insufficient to authorize a
        # production listener. Do not publish an IPC socket and then reject.
        raise AdmissionError('LOG-CORE-020 NO-GO: production E2E proof incomplete')


def crash_state_matrix(anchor):
    """Deterministic fault-state classifier; not a SIGKILL injection test."""
    if not isinstance(anchor,dict) or set(anchor) != {'events','head_hash'}:
        raise AdmissionError('invalid anchor')
    advanced={'events':anchor['events']+1,'head_hash':'b'*64 if anchor['head_hash']!='b'*64 else 'c'*64}
    phase={'before':anchor,'key':'crash-probe','uid':12004}
    cases={
        'before_sqlite':(anchor,anchor,anchor,phase),
        'after_sqlite':(advanced,anchor,anchor,phase),
        'after_witness':(advanced,anchor,advanced,phase),
        'after_checkpoint':(advanced,advanced,advanced,phase),
        'rollback_without_phase':(anchor,advanced,advanced,None),
        'stable':(anchor,anchor,anchor,None),
    }
    return {name:classify_recovery(*state).state for name,state in cases.items()}


def production_admission(*args,**kwargs):
    raise AdmissionError('LOG-CORE-020 BLOCKED: mandatory cross-UID E2E and exhaustive crash evidence absent')
