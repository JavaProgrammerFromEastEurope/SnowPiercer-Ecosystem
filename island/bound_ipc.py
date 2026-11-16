"""ISLAND-GEO-016 experimental bound-permit authority and mandatory startup.

Production safety requires OS provisioned isolated storage and an independent witness.
"""
import os
import socket
import sqlite3
from pathlib import Path
from .anchored_admission import AdmissionDenied, WitnessStore, _receive, _send
from .bound_recovery import BoundPermitAuthority
from .authorized_production import AuthorizedProductionServer, AuthorityClient
from .production_admission import peer_uid, secure_directory
from .production_fencing import PinnedWitnessClient

class BoundAuthorityServer:
    """Authority checks direct kernel peer UID; no caller-supplied UID is trusted."""
    def __init__(self, socket_path, witness_db, permit_db, service_uid, client_uid):
        if len({service_uid,client_uid,os.geteuid()}) != 3 or 0 in {service_uid,client_uid,os.geteuid()}:
            raise AdmissionDenied('three distinct nonroot UID required')
        self.path=Path(socket_path)
        self.witness=WitnessStore(witness_db)
        self.permits=BoundPermitAuthority(permit_db,client_uid,service_uid,self.witness)
        self.service_uid=service_uid
        self.client_uid=client_uid
    def serve(self,limit=None):
        secure_directory(self.path.parent,os.geteuid())
        if self.path.exists() or self.path.is_symlink(): raise AdmissionDenied('occupied authority endpoint')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
            srv.bind(str(self.path)); os.chmod(self.path,0o666); srv.listen(16); srv.settimeout(.3)
            count=0
            try:
                while limit is None or count<limit:
                    try: client,_=srv.accept()
                    except socket.timeout: continue
                    count+=1
                    with client:
                        client.settimeout(3)
                        try:
                            uid=peer_uid(client)
                            req=_receive(client)
                            if type(req) is not dict or set(req)-{'operation','record','token'}:
                                raise AdmissionDenied('invalid request')
                            op=req.get('operation')
                            if op in ('read','cas'):
                                if uid!=self.service_uid: raise AdmissionDenied('witness UID denied')
                                result=self.witness.execute(op,req.get('record'))
                            elif op in ('issue','consume'):
                                result=self.permits.execute(uid,op,req.get('token'))
                            else: raise AdmissionDenied('unknown operation')
                            _send(client,{'ok':True,'result':result})
                        except (AdmissionDenied,ValueError,KeyError,OSError,sqlite3.Error) as exc:
                            try: _send(client,{'ok':False,'reason':str(exc)})
                            except OSError: pass
            finally:
                if self.path.is_socket(): self.path.unlink()

class PinnedBoundAuthorityClient(AuthorityClient):
    """Pins remote UID before sending secrets, including permit tokens."""
    def __init__(self,path,expected_uid):
        super().__init__(path)
        self.expected_uid=expected_uid
    def execute(self,operation,record=None,token=None):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(3); sock.connect(self.path)
            if peer_uid(sock)!=self.expected_uid: raise AdmissionDenied('authority peer UID mismatch')
            _send(sock,{'operation':operation,'record':record,'token':token})
            reply=_receive(sock)
            if type(reply) is not dict or reply.get('ok') is not True:
                raise AdmissionDenied(reply.get('reason','invalid authority response') if type(reply) is dict else 'invalid authority response')
            return reply['result']

class BoundProductionServer(AuthorizedProductionServer):
    """Startup always consumes a witness-head-bound permit before reconciliation."""
    def serve(self,limit=None,recovery_token=None):
        # Inherited service performs preflight, consumes permit, then recovers.
        # Replace AuthorityClient with pinned client by an explicit local override
        # rather than changing previous-stage public library APIs.
        self.authority_client_factory=lambda path: PinnedBoundAuthorityClient(path,self.witness_uid)
        return super().serve(limit=limit,recovery_token=recovery_token)
