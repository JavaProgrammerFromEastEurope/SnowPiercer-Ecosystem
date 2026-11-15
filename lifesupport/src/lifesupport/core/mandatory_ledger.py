"""LIFE-CORE-019 opt-in mandatory IPC admission and recoverable intent.

Assumes exclusive service-owned writer and independent anchor key. Not power-loss proof.
"""
import hashlib
import hmac
import json
import os
import stat
import tempfile
from pathlib import Path
from .request_ledger import RequestLedgerAnchor, LedgerIntegrityError, ledger_snapshot, _canonical, _rows
from .reconciled_write import ReconciledWriteService, apply_request, _canonical as request_canonical
from .cross_uid import authorize_peer
from .service import ServiceError, _readline


def _atomic(path, payload):
    path=Path(path)
    if path.is_symlink() or (path.exists() and (not path.is_file() or stat.S_IMODE(path.stat().st_mode)&0o077)):
        raise LedgerIntegrityError('unsafe intent path')
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise LedgerIntegrityError('unsafe intent directory')
    fd, name=tempfile.mkstemp(dir=path.parent,prefix='.life-intent-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(_canonical(payload));f.flush();os.fsync(f.fileno())
        os.replace(name,path)
        dfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(name):os.unlink(name)


def _remove(path):
    Path(path).unlink()
    dfd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(dfd)
    finally: os.close(dfd)


class MandatoryLedger:
    def __init__(self, lifecycle, anchor):
        self.lifecycle=lifecycle
        self.anchor=anchor
        self.intent=Path(str(anchor.path)+'.pending')

    def _read_intent(self):
        if self.intent.is_symlink(): raise LedgerIntegrityError('intent symlink')
        st=self.intent.stat()
        if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode)&0o077 or st.st_size>8192:
            raise LedgerIntegrityError('unsafe intent')
        obj=json.loads(self.intent.read_bytes())
        if not isinstance(obj,dict) or set(obj)!={'version','old','request_id','request_hash','uid','mac'} or obj['version']!=1:
            raise LedgerIntegrityError('invalid intent')
        payload={k:v for k,v in obj.items() if k!='mac'}
        expected=hmac.new(self.anchor.key,_canonical(payload),hashlib.sha256).hexdigest()
        if not isinstance(obj['mac'],str) or not hmac.compare_digest(expected,obj['mac']):
            raise LedgerIntegrityError('intent authentication failed')
        if not isinstance(obj['request_id'],str) or not isinstance(obj['request_hash'],str) or type(obj['uid']) is not int:
            raise LedgerIntegrityError('invalid intent fields')
        return obj

    def _verify_journal(self):
        if self.lifecycle.verify_integrity().get('version')!=2:
            raise LedgerIntegrityError('v2 protected journal required')
        self.lifecycle._replay()
        return ledger_snapshot(self.lifecycle.db)

    def recover(self):
        current=self._verify_journal()
        if not self.intent.exists() and not self.intent.is_symlink():
            return self.anchor.verify(self.lifecycle.db)
        intent=self._read_intent()
        trusted=self.anchor._read()
        old=intent['old']
        if trusted!=old and trusted!=current:
            raise LedgerIntegrityError('anchor does not match pending transaction')
        if current==old:
            if trusted!=old: raise LedgerIntegrityError('anchor ahead of database')
            _remove(self.intent)
            return self.anchor.verify(self.lifecycle.db)
        rows=_rows(self.lifecycle.db)
        matching=[r for r in rows if r[0]==intent['request_id']]
        if len(matching)!=1 or matching[0][1]!=intent['request_hash'] or matching[0][2]!=intent['uid']:
            raise LedgerIntegrityError('pending receipt mismatch')
        remaining=[r for r in rows if r[0]!=intent['request_id']]
        prior={'count':len(remaining),'digest':hashlib.sha256(_canonical(remaining)).hexdigest(),
               'max_sequence':max((r[3] for r in remaining),default=0)}
        if prior!=old or current['count']!=old['count']+1 or matching[0][3]<=old['max_sequence']:
            raise LedgerIntegrityError('non-monotonic or unexpected receipt change')
        if trusted==old:
            self.anchor._write(current)
        _remove(self.intent)
        return self.anchor.verify(self.lifecycle.db)

    def apply(self,req,uid,*,fault=None):
        self.recover()
        if not isinstance(req,dict) or req.get('op')!='transition' or not isinstance(req.get('request_id'),str):
            raise ServiceError('invalid request')
        # An existing receipt can be safely replayed without changing the anchor.
        row=self.lifecycle.db.execute('SELECT 1 FROM life_request_receipts WHERE request_id=?',(req['request_id'],)).fetchone() if self.lifecycle.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_request_receipts'").fetchone() else None
        if row:
            return apply_request(self.lifecycle,req,uid)
        from .reconciled_write import FIELDS
        if set(req)!=FIELDS or type(uid) is not int or uid<=0:
            raise ServiceError('invalid request fields')
        digest=hashlib.sha256(request_canonical(req,uid).encode()).hexdigest()
        old=ledger_snapshot(self.lifecycle.db)
        payload={'version':1,'old':old,'request_id':req['request_id'],'request_hash':digest,'uid':uid}
        payload['mac']=hmac.new(self.anchor.key,_canonical(payload),hashlib.sha256).hexdigest()
        if self.intent.exists() or self.intent.is_symlink(): raise LedgerIntegrityError('pending intent occupied')
        _atomic(self.intent,payload)
        if fault: fault('after_intent')
        result=apply_request(self.lifecycle,req,uid,fault=fault)
        if fault: fault('before_anchor')
        self.recover()
        return result


class MandatoryLedgerService(ReconciledWriteService):
    """Opt-in replacement for reconciled IPC. Anchor key provisioned out of band."""
    def __init__(self,registry_path,db_path,socket_path,*,allowed_uids,anchor_path,key):
        super().__init__(registry_path,db_path,socket_path,allowed_uids=allowed_uids)
        self.anchor=RequestLedgerAnchor(anchor_path,key)

    def preflight(self,lifecycle):
        MandatoryLedger(lifecycle,self.anchor).recover()

    def handle(self,conn,lifecycle):
        admission=MandatoryLedger(lifecycle,self.anchor)
        uid=authorize_peer(conn,allowed_uids=self.allowed_uids)
        req=_readline(conn)
        if not isinstance(req,dict): raise ServiceError('invalid request')
        # Every operation including health/receipt is gated by integrity recovery.
        admission.recover()
        if req.get('op')=='transition': return admission.apply(req,uid)
        if req.get('op') in ('health','snapshot','receipt'):
            return self._read_operation(req,lifecycle,uid)
        raise ServiceError('unsupported operation')

    def _read_operation(self,req,lifecycle,uid):
        if req.get('op') in ('health','snapshot'):
            if set(req)!={'op'}: raise ServiceError('invalid fields')
            state=lifecycle._replay()
            return {'ok':True,'status':'ready'} if req['op']=='health' else {'ok':True,'states':state.snapshot()}
        if set(req)!={'op','request_id'} or type(req['request_id']) is not str: raise ServiceError('invalid receipt query')
        if not lifecycle.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_request_receipts'").fetchone(): return {'ok':True,'found':False}
        row=lifecycle.db.execute('SELECT peer_uid,sequence,event_id FROM life_request_receipts WHERE request_id=?',(req['request_id'],)).fetchone()
        if not row or row[0]!=uid: return {'ok':True,'found':False}
        return {'ok':True,'found':True,'sequence':row[1],'event_id':row[2]}


class MandatoryLedgerSupervisor:
    """Use existing dedicated-UID supervisor with mandatory-ledger CLI."""
    def __new__(cls,registry,db,socket_path,*,allowed_uids,anchor_path,key_file):
        from .supervised_cross_uid import CrossUIDSupervisor
        supervisor=CrossUIDSupervisor(registry,db,socket_path,allowed_uids=allowed_uids,
                    cli_module='lifesupport.mandatory_ledger_cli')
        supervisor.extra_args=('--anchor',str(anchor_path),'--key-file',str(key_file))
        return supervisor
