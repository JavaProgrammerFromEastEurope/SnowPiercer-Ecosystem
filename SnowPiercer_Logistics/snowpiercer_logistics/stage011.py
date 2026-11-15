"""Stage 011 deployment enforcement primitives (not a production certification).

Checks operate on existing OS objects. No chmod/chown, privilege escalation or
implicit creation is performed. A privileged deployment administrator must set up
separate service identities and mandatory filesystem permissions.
"""
import os
import stat
import socket
from dataclasses import dataclass
from pathlib import Path
from .secure import AdmissionError
from .stage010 import IsolationPolicy, verify_isolated_deployment

@dataclass(frozen=True)
class DeploymentLayout:
    policy: IsolationPolicy
    service_root: str
    witness_root: str
    authority_root: str
    service_socket: str
    witness_socket: str
    authority_socket: str


def _checked_inode(path, expected_uid, kind):
    path = Path(path)
    try:
        info = path.lstat()
    except OSError as exc:
        raise AdmissionError('required deployment object missing') from exc
    if kind == 'directory':
        valid = stat.S_ISDIR(info.st_mode)
    elif kind == 'socket':
        valid = stat.S_ISSOCK(info.st_mode)
    else:
        raise ValueError('unsupported object kind')
    if not valid or info.st_uid != expected_uid or info.st_mode & 0o007:
        raise AdmissionError('unsafe deployment object')
    if kind == 'directory' and info.st_mode & 0o070:
        raise AdmissionError('private directory is group accessible')
    if kind == 'socket' and info.st_mode & 0o002:
        raise AdmissionError('socket is world writable')
    return info


def verify_deployment(layout, *, require_sockets=True):
    """Fail-closed preflight; must be combined with OS-enforced ownership and ACLs.

    This check is not atomic with subsequent opens and cannot defend against
    privileged adversaries, inherited descriptors, or a compromised service UID.
    """
    p = layout.policy
    verify_isolated_deployment(p, service_root=layout.service_root,
                               witness_root=layout.witness_root,
                               authority_root=layout.authority_root)
    if require_sockets:
        for name, uid, root in (
            (layout.service_socket, p.service_uid, layout.service_root),
            (layout.witness_socket, p.witness_uid, layout.witness_root),
            (layout.authority_socket, p.authority_uid, layout.authority_root),
        ):
            if Path(name).parent != Path(root):
                raise AdmissionError('socket outside trusted directory')
            _checked_inode(name, uid, 'socket')
    return True


def verify_legacy_denied(legacy_root, *, service_uid):
    """Verify only that current non-service UID cannot open legacy data.

    Does not claim a global OS production fence. Caller must run under the
    actual unprivileged legacy UID; root and service UID are explicitly refused.
    """
    if os.geteuid() in (0, service_uid):
        raise AdmissionError('legacy access probe requires unprivileged non-service UID')
    path = Path(legacy_root)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except PermissionError:
        return True
    except OSError as exc:
        raise AdmissionError('legacy denial probe inconclusive') from exc
    else:
        os.close(fd)
        raise AdmissionError('legacy access unexpectedly permitted')
