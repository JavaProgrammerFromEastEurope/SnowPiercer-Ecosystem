"""ISLAND-GEO-017: separated private storage and cross-UID IPC namespace.

Provisioning is privileged and must occur before dropping privileges. This
module checks a layout; it never grants privileges or certifies production use.
"""
import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from .anchored_admission import AdmissionDenied

@dataclass(frozen=True)
class SocketIsolationPolicy:
    client_uid: int
    service_uid: int
    witness_uid: int
    service_gid: int
    witness_gid: int

    def validate(self):
        if any(type(x) is not int or x <= 0 for x in (self.client_uid,self.service_uid,self.witness_uid,self.service_gid,self.witness_gid)):
            raise AdmissionDenied('nonroot identities required')
        if len({self.client_uid,self.service_uid,self.witness_uid}) != 3:
            raise AdmissionDenied('separate client, service and witness UIDs required')
        return self

def _checked(path, *, owner, group=None, directory=False, socket_file=False, max_mode=0o700):
    path=Path(path)
    st=path.lstat()
    expected=stat.S_IFDIR if directory else stat.S_IFSOCK if socket_file else stat.S_IFREG
    if stat.S_IFMT(st.st_mode)!=expected or st.st_uid!=owner or (group is not None and st.st_gid!=group):
        raise AdmissionDenied('file type, owner or group mismatch: '+str(path))
    if st.st_mode & 0o777 & ~max_mode:
        raise AdmissionDenied('excess permissions: '+str(path))
    if not directory and not socket_file and st.st_nlink!=1:
        raise AdmissionDenied('hardlinked private file: '+str(path))
    return (st.st_dev,st.st_ino)

def verify_isolated_layout(policy, *, service_private, witness_private, ipc_directory, service_socket=None, witness_socket=None, witness_db=None, permit_db=None, service_db=None):
    """Reject symlinks, owner/group mismatch and overly permissive paths.

    IPC directory is root-owned 01777 (sticky), preventing cross-UID unlink;
    sockets are service/witness-owned and group-restricted. Caller must arrange
    group membership and prove denied legacy writes with actual UID probes.
    """
    policy.validate()
    result={}
    result['service_private']=_checked(service_private,owner=policy.service_uid,directory=True,max_mode=0o700)
    result['witness_private']=_checked(witness_private,owner=policy.witness_uid,directory=True,max_mode=0o700)
    result['ipc_directory']=_checked(ipc_directory,owner=0,directory=True,max_mode=0o777)
    if Path(ipc_directory).lstat().st_mode & stat.S_ISVTX == 0: raise AdmissionDenied('IPC namespace requires sticky bit')
    if service_socket is not None:
        result['service_socket']=_checked(service_socket,owner=policy.service_uid,group=policy.service_gid,socket_file=True,max_mode=0o660)
    if witness_socket is not None:
        result['witness_socket']=_checked(witness_socket,owner=policy.witness_uid,group=policy.witness_gid,socket_file=True,max_mode=0o660)
    for name,path,uid in [('witness_db',witness_db,policy.witness_uid),('permit_db',permit_db,policy.witness_uid),('service_db',service_db,policy.service_uid)]:
        if path is not None: result[name]=_checked(path,owner=uid,max_mode=0o600)
    return result

def deny_legacy_access(path, forbidden_uid):
    """An actual OS-enforced negative access probe (only valid in child UID).

    Does not claim denial for root, privileged processes or other paths.
    """
    if os.geteuid()!=forbidden_uid or forbidden_uid==0:
        raise AdmissionDenied('probe must execute as forbidden nonroot UID')
    try:
        fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
    except PermissionError:
        return True
    except FileNotFoundError:
        raise AdmissionDenied('missing legacy storage is not an access proof')
    else:
        os.close(fd)
        raise AdmissionDenied('legacy write bypass possible')

class IsolatedAuthorityServer:
    """Authority with root-controlled IPC namespace and witness-private storage."""
    def __init__(self, socket_path, witness_db, permit_db, service_uid, client_uid):
        from .bound_ipc import BoundAuthorityServer
        self.backend=BoundAuthorityServer(socket_path,witness_db,permit_db,service_uid,client_uid)
    def serve(self,limit=None):
        import sqlite3
        from .anchored_admission import _receive,_send
        from .production_admission import peer_uid
        b=self.backend
        _checked(b.path.parent,owner=0,directory=True,max_mode=0o777)
        if not b.path.parent.stat().st_mode & stat.S_ISVTX: raise AdmissionDenied('IPC namespace requires sticky bit')
        _checked(b.witness.path.parent,owner=os.geteuid(),directory=True,max_mode=0o700)
        _checked(b.permits.path.parent,owner=os.geteuid(),directory=True,max_mode=0o700)
        if b.path.exists() or b.path.is_symlink(): raise AdmissionDenied('occupied authority socket')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
            srv.bind(str(b.path));os.chmod(b.path,0o660);srv.listen(16);srv.settimeout(.3)
            count=0
            try:
                while limit is None or count<limit:
                    try: client,_=srv.accept()
                    except socket.timeout: continue
                    count+=1
                    with client:
                        client.settimeout(3)
                        try:
                            uid=peer_uid(client);req=_receive(client)
                            if type(req) is not dict or set(req)-{'operation','record','token'}: raise AdmissionDenied('invalid request')
                            op=req.get('operation')
                            if op in ('read','cas'):
                                if uid!=b.service_uid: raise AdmissionDenied('witness UID denied')
                                result=b.witness.execute(op,req.get('record'))
                            elif op in ('issue','consume'): result=b.permits.execute(uid,op,req.get('token'))
                            else: raise AdmissionDenied('unknown operation')
                            _send(client,{'ok':True,'result':result})
                        except (AdmissionDenied,ValueError,KeyError,OSError,sqlite3.Error) as exc:
                            try:_send(client,{'ok':False,'reason':str(exc)})
                            except OSError:pass
            finally:
                if b.path.is_socket():b.path.unlink()

from .bound_ipc import BoundProductionServer
class IsolatedProductionServer(BoundProductionServer):
    """Production facade whose endpoint is in root-owned nonwritable namespace."""
    def _preflight(self):
        from .production_admission import secure_directory,secure_regular
        uid=os.geteuid()
        if len({uid,self.client_uid,self.witness_uid})!=3 or 0 in {uid,self.client_uid,self.witness_uid}:
            raise AdmissionDenied('three distinct nonroot UIDs required')
        _checked(self.path.parent,owner=0,directory=True,max_mode=0o777)
        if not self.path.parent.stat().st_mode & stat.S_ISVTX: raise AdmissionDenied('IPC namespace requires sticky bit')
        secure_directory(self.db.parent,uid)
        if self.path.exists() or self.path.is_symlink(): raise AdmissionDenied('occupied production socket')
        if self.db.exists(): secure_regular(self.db,uid)
        if self.authority.is_symlink() or not self.authority.is_socket() or self.authority.stat().st_uid!=self.witness_uid:
            raise AdmissionDenied('authority endpoint mismatch')
