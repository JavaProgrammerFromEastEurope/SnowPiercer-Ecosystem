"""Deployment policy: deny untrusted topology; no claim of exhaustive protection."""
import os, stat, socket, struct
from pathlib import Path
from .anchored_admission import AdmissionDenied

def require_linux_multiuid(client, service, witness):
    if not hasattr(socket,'SO_PEERCRED') or os.name!='posix': raise AdmissionDenied('Linux SO_PEERCRED required')
    if any(type(x) is not int or x <= 0 for x in (client,service,witness)) or len({client,service,witness})!=3: raise AdmissionDenied('three distinct non-root UIDs required')
    return True

def check_private_tree(path, uid):
    p=Path(path); s=p.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=uid or s.st_mode & 0o077: raise AdmissionDenied('private tree owner or permissions')
    for item in p.iterdir():
        st=item.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or st.st_nlink!=1 or st.st_mode & 0o077: raise AdmissionDenied('private tree unsafe entry')
    return True

def peer_identity(sock, expected):
    if not hasattr(socket,'SO_PEERCRED'): raise AdmissionDenied('unsupported')
    uid=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
    if uid!=expected: raise AdmissionDenied('peer UID mismatch')
    return uid
