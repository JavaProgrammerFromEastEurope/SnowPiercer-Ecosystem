"""ISLAND-GEO-020 experimental owner-separated write broker.

Broker owns the ledger; front-end service never opens ledger files. Linux only.
Not a protection against root, broker-UID code execution or witness rollback.
"""
import os
import socket
import sqlite3
from pathlib import Path
from .anchored_admission import AdmissionDenied, _receive, _send
from .crash_protocol import CrashInstrumentedAdmission, POINTS
from .bound_ipc import PinnedBoundAuthorityClient
from .production_admission import peer_uid, secure_directory
from .mandatory_guard import startup_lease, _safe_existing
from .production_guard import inspect_endpoint, assert_endpoint_unchanged


def _identities(client_uid, service_uid, broker_uid, witness_uid):
    values = (client_uid, service_uid, broker_uid, witness_uid)
    if any(type(x) is not int or x <= 0 for x in values) or len(set(values)) != 4:
        raise AdmissionDenied('four distinct nonroot UID roles required')
    return values


class WriteBroker:
    """The broker alone has OS write access to the ledger directory.

    Socket namespace is provisioned separately by root; the broker verifies
    the actual connecting service UID, and pins the witness UID.
    """
    def __init__(self, socket_path, db_path, authority_path, client_uid, service_uid, witness_uid, crash_at=None):
        self.path=Path(socket_path); self.db=Path(db_path); self.authority=Path(authority_path)
        self.client_uid=client_uid; self.service_uid=service_uid; self.witness_uid=witness_uid
        self.crash_at=crash_at
        _identities(client_uid,service_uid,os.geteuid(),witness_uid)
        if crash_at is not None and crash_at not in POINTS: raise AdmissionDenied('invalid crash point')

    def preflight(self):
        secure_directory(self.db.parent,os.geteuid())
        _safe_existing(self.db,os.geteuid())
        _safe_existing(self.db.with_suffix('.lock'),os.geteuid())
        if self.path.exists() or self.path.is_symlink(): raise AdmissionDenied('occupied broker endpoint')
        if self.authority.is_symlink() or not self.authority.is_socket(): raise AdmissionDenied('missing witness endpoint')
        identity=inspect_endpoint(self.authority,owner=self.witness_uid,group=self.authority.stat().st_gid,directory=self.authority.parent)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(3);s.connect(str(self.authority))
            if peer_uid(s)!=self.witness_uid: raise AdmissionDenied('witness peer UID mismatch')
        assert_endpoint_unchanged(self.authority,identity)

    def serve(self, recovery_token, limit=None):
        if not isinstance(recovery_token,str) or not recovery_token: raise AdmissionDenied('mandatory recovery permit')
        with startup_lease(self.db.parent/'.broker-startup.lock'):
            self.preflight()
            authority=PinnedBoundAuthorityClient(str(self.authority),self.witness_uid)
            authority.execute('consume',token=recovery_token)
            admission=CrashInstrumentedAdmission(self.db,authority)
            admission.recover()
            os.chmod(self.db,0o600)
            os.chmod(self.db.with_suffix('.lock'),0o600)
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
                srv.bind(str(self.path));os.chmod(self.path,0o660);srv.listen(16);srv.settimeout(.3)
                count=0
                try:
                    while limit is None or count<limit:
                        try: conn,_=srv.accept()
                        except socket.timeout: continue
                        count+=1
                        with conn:
                            conn.settimeout(3)
                            try:
                                if peer_uid(conn)!=self.service_uid: raise AdmissionDenied('service UID denied')
                                request=_receive(conn)
                                if type(request) is not dict or set(request)!={'operation','payload'} or request['operation']!='admit':
                                    raise AdmissionDenied('invalid broker request')
                                value=request['payload']
                                if type(value) is not str or len(value)>8192: raise AdmissionDenied('invalid payload')
                                payload=bytes.fromhex(value)
                                if len(payload)>4096: raise AdmissionDenied('oversize payload')
                                result=admission.admit(payload,crash_at=self.crash_at)
                                _send(conn,{'ok':True,'result':result})
                            except (AdmissionDenied,ValueError,sqlite3.Error,OSError) as exc:
                                try:_send(conn,{'ok':False,'reason':str(exc)})
                                except OSError:pass
                finally:
                    if self.path.is_socket(): self.path.unlink()


class BrokerClient:
    def __init__(self, path, broker_uid):
        self.path=str(path);self.broker_uid=broker_uid
    def admit(self, payload):
        if type(payload) is not bytes or len(payload)>4096: raise AdmissionDenied('invalid payload')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(3);s.connect(self.path)
            if peer_uid(s)!=self.broker_uid: raise AdmissionDenied('broker UID mismatch')
            _send(s,{'operation':'admit','payload':payload.hex()})
            reply=_receive(s)
            if type(reply) is not dict or reply.get('ok') is not True: raise AdmissionDenied('broker denied request')
            return reply['result']


class AdmissionFacade:
    """Unprivileged facade: no DB path or witness secret, forwards verified client."""
    def __init__(self,socket_path,broker_path,client_uid,broker_uid,witness_uid):
        self.path=Path(socket_path);self.broker_path=Path(broker_path)
        self.client_uid=client_uid;self.broker_uid=broker_uid;self.witness_uid=witness_uid
        _identities(client_uid,os.geteuid(),broker_uid,witness_uid)
    def serve(self,limit=None):
        if self.path.exists() or self.path.is_symlink(): raise AdmissionDenied('occupied service endpoint')
        broker=BrokerClient(self.broker_path,self.broker_uid)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
            srv.bind(str(self.path));os.chmod(self.path,0o660);srv.listen(16);srv.settimeout(.3)
            count=0
            try:
                while limit is None or count<limit:
                    try:conn,_=srv.accept()
                    except socket.timeout:continue
                    count+=1
                    with conn:
                        conn.settimeout(3)
                        try:
                            if peer_uid(conn)!=self.client_uid:raise AdmissionDenied('client UID denied')
                            request=_receive(conn)
                            if type(request) is not dict or set(request)!={'operation','payload'} or request['operation']!='admit':raise AdmissionDenied('invalid IPC request')
                            value=request['payload']
                            if type(value) is not str or len(value)>8192:raise AdmissionDenied('invalid payload')
                            payload=bytes.fromhex(value)
                            result=broker.admit(payload)
                            _send(conn,{'ok':True,'result':result})
                        except (AdmissionDenied,ValueError,OSError) as exc:
                            try:_send(conn,{'ok':False,'reason':str(exc)})
                            except OSError:pass
            finally:
                if self.path.is_socket():self.path.unlink()
