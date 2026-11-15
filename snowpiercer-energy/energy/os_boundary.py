"""ENERGY-CORE-018: OS permission preflight, not a substitute for deployment isolation.

Root and same-UID processes can bypass discretionary access controls. The
legacy library remains importable; only separately provisioned UID/permissions
can make its production data inaccessible.
"""
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from .trust import AdmissionDenied
from .production_boundary import AttestedProductionEnergyService

@dataclass(frozen=True)
class ProductionUIDPolicy:
    service_uid: int
    witness_uid: int
    client_uids: frozenset

    def validate(self):
        if (type(self.service_uid) is not int or type(self.witness_uid) is not int
                or self.service_uid < 1 or self.witness_uid < 1
                or self.service_uid == self.witness_uid
                or not isinstance(self.client_uids, frozenset)
                or not self.client_uids
                or any(type(u) is not int or u < 1 for u in self.client_uids)
                or self.service_uid in self.client_uids
                or self.witness_uid in self.client_uids):
            raise AdmissionDenied('separate non-root service, witness and client UIDs required')
        if os.geteuid() != self.service_uid or os.getuid() != self.service_uid:
            raise AdmissionDenied('service must run with dedicated real and effective UID')


def require_private_tree(paths, uid):
    """Check every ancestor down to the filesystem root for unsafe writable dirs.

    Sticky system directories (e.g. /tmp) are allowed but not sufficient for
    trusted production deployment. All protected leaves must be regular files
    or private directories owned by service UID, without links or group access.
    """
    for raw in paths:
        path = Path(raw).absolute()
        if '..' in Path(raw).parts:
            raise AdmissionDenied('noncanonical path')
        if not path.exists() and not path.is_symlink():
            raise AdmissionDenied('required production path absent')
        st = path.lstat()
        if st.st_uid != uid or st.st_mode & 0o077 or (stat.S_ISREG(st.st_mode) and st.st_nlink != 1):
            raise AdmissionDenied('unsafe production ownership or mode')
        if not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
            raise AdmissionDenied('nonregular production object')
        for parent in path.parents:
            pst = parent.lstat()
            if not stat.S_ISDIR(pst.st_mode):
                raise AdmissionDenied('non-directory ancestor')
            if pst.st_mode & 0o022 and not (pst.st_mode & stat.S_ISVTX):
                raise AdmissionDenied('writable ancestor without sticky bit')


class IsolatedProductionEnergyService(AttestedProductionEnergyService):
    """Opt-in mandatory OS preflight for a separately provisioned service UID.

    Provisioning and independently protected witness are external requirements.
    Does not grant production authority to legacy library entry points.
    """
    def __init__(self, admission, path, allowed_uids, permit_db, checkpoint_dir,
                 witness, verifier, policy):
        if not isinstance(policy, ProductionUIDPolicy):
            raise AdmissionDenied('production UID policy required')
        policy.validate()
        if frozenset(allowed_uids) != policy.client_uids:
            raise AdmissionDenied('IPC allowlist must match client UID policy')
        self._production_policy = policy
        require_private_tree([Path(path).parent, checkpoint_dir,
                              Path(permit_db).parent], policy.service_uid)
        super().__init__(admission, path, allowed_uids, permit_db, checkpoint_dir,
                         witness, verifier)

    def __enter__(self):
        self._production_policy.validate()
        return super().__enter__()
