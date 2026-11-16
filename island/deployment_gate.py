"""ISLAND-GEO-011: fail-closed deployment preflight, not an OS security boundary.
Never use this library as a substitute for OS permission provisioning.
"""
import os
import stat
import socket
from pathlib import Path
from dataclasses import dataclass
from .anchored_admission import AdmissionDenied
from .production_fencing import PinnedWitnessClient, verify_peer

@dataclass(frozen=True)
class IdentityPolicy:
    client_uid: int
    service_uid: int
    witness_uid: int
    def __post_init__(self):
        values=(self.client_uid,self.service_uid,self.witness_uid)
        if any(type(x) is not int or x <= 0 for x in values) or len(set(values)) != 3:
            raise AdmissionDenied('three distinct non-root UIDs required')

def private_directory(path, owner):
    p=Path(path)
    s=p.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != owner or s.st_mode & 0o077:
        raise AdmissionDenied('private directory owner/mode mismatch')
    return p

def private_file(path, owner):
    p=Path(path)
    s=p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != owner or s.st_nlink != 1 or s.st_mode & 0o077:
        raise AdmissionDenied('private file owner/mode mismatch')
    return p

def deployment_preflight(policy, local_dir, witness_dir, local_db, witness_db):
    """Read-only checks; no automatic chmod/chown or unsafe repair."""
    if not isinstance(policy,IdentityPolicy) or os.geteuid()!=policy.service_uid:
        raise AdmissionDenied('service identity mismatch')
    private_directory(local_dir,policy.service_uid)
    private_directory(witness_dir,policy.witness_uid)
    private_file(local_db,policy.service_uid)
    private_file(witness_db,policy.witness_uid)
    # A service cannot safely rely on owner-readable witness DB as an independent anchor.
    if os.access(witness_db,os.W_OK):
        raise AdmissionDenied('service can modify witness database')
    return {'status':'PREFLIGHT_ONLY','production_approval':'BLOCKED/NO-GO'}

def verify_witness_peer(socket_path, witness_uid):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        sock.connect(str(socket_path))
        return verify_peer(sock,witness_uid)

def verify_legacy_denied(legacy_db, client_uid):
    """Static owner/mode check; real negative access must be exercised as client UID."""
    s=Path(legacy_db).lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid == client_uid or s.st_mode & 0o077:
        raise AdmissionDenied('legacy database not statically fenced')
    return True
