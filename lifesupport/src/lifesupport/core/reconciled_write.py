"""LIFE-CORE-017: opt-in atomic request receipts and supervised write IPC.

Offline logical state only. SQLite COMMIT is the linearization point.
"""
import hashlib
import json
import os
from .production_write import ProductionWriteService, validate_identity
from .cross_uid import authorize_peer
from .service import ServiceError, _readline
from .supervised_cross_uid import CrossUIDSupervisor
from .persistence import fingerprint

FIELDS=frozenset(('op','request_id','component_id','next_state','event_id','reason'))


def _canonical(req, uid):
    return json.dumps({'uid':uid, 'component_id':req['component_id'],
                       'next_state':req['next_state'],'event_id':req['event_id'],
                       'reason':req['reason']},sort_keys=True,separators=(',',':'))


def _receipt_table(lifecycle):
    lifecycle.db.execute('''CREATE TABLE IF NOT EXISTS life_request_receipts (
        request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
        peer_uid INTEGER NOT NULL, sequence INTEGER NOT NULL,
        event_id TEXT NOT NULL)''')


def apply_request(lifecycle, req, uid, *, fault=None):
    """Atomic event + receipt, including replay validation, in one SQLite transaction.

    fault is a test-only injection hook invoked inside the transaction before COMMIT
    or immediately after COMMIT; never exposed via IPC.
    """
    if type(uid) is not int or uid <= 0 or not isinstance(req,dict) or set(req)!=FIELDS or req.get('op')!='transition':
        raise ServiceError('invalid request')
    if any(type(req[k]) is not str or not req[k] or len(req[k])>256 for k in FIELDS-{'op'}):
        raise ServiceError('invalid transition arguments')
    digest=hashlib.sha256(_canonical(req,uid).encode()).hexdigest()
    lifecycle.verify_integrity()
    db=lifecycle.db
    db.execute('BEGIN IMMEDIATE')
    committed=False
    try:
        _receipt_table(lifecycle)
        row=db.execute('SELECT request_hash,peer_uid,sequence,event_id FROM life_request_receipts WHERE request_id=?',(req['request_id'],)).fetchone()
        if row:
            if row[0]!=digest or row[1]!=uid: raise ServiceError('request_id conflict')
            # Check durable journal, not just receipt metadata.
            journal=db.execute('SELECT event_id FROM events WHERE sequence=?',(row[2],)).fetchone()
            if not journal or journal[0]!=row[3]: raise ServiceError('receipt journal mismatch')
            lifecycle._replay()
            db.execute('COMMIT');committed=True
            return {'ok':True,'sequence':row[2],'event_id':row[3],'request_id':req['request_id'],'replayed':True}
        # Same authorization and lease checks as legacy write service; however
        # acquire/release are separate transactions. The event and receipt share one.
        db.execute('COMMIT');committed=True
    except BaseException:
        if db.in_transaction: db.execute('ROLLBACK')
        raise
    token=lifecycle.acquire('reconciled-ipc',ttl_ns=2_000_000_000)
    try:
        lifecycle.verify_integrity()
        db.execute('BEGIN IMMEDIATE')
        committed=False
        try:
            lifecycle._check(token,lifecycle._now())
            _receipt_table(lifecycle)
            row=db.execute('SELECT request_hash,peer_uid,sequence,event_id FROM life_request_receipts WHERE request_id=?',(req['request_id'],)).fetchone()
            if row:
                if row[0]!=digest or row[1]!=uid: raise ServiceError('request_id conflict')
                lifecycle._replay()
                db.execute('COMMIT');committed=True
                return {'ok':True,'sequence':row[2],'event_id':row[3],'request_id':req['request_id'],'replayed':True}
            fresh=lifecycle._replay()
            event=fresh.transition(req['component_id'],req['next_state'],event_id=req['event_id'],reason=req['reason'],actor=f'uid:{uid}')
            lifecycle._admitted=True
            try:
                db.execute('INSERT INTO events(sequence,event_id,payload) VALUES(?,?,?)',
                           (event.sequence,event.event_id,json.dumps(event.as_dict(),sort_keys=True,separators=(',',':'),ensure_ascii=False)))
            finally:
                lifecycle._admitted=False
            db.execute('INSERT INTO life_request_receipts VALUES(?,?,?,?,?)',(req['request_id'],digest,uid,event.sequence,event.event_id))
            lifecycle._check(token,lifecycle._now())
            if fault: fault('before_commit')
            db.execute('COMMIT');committed=True
            lifecycle.lifecycle=fresh
            if fault: fault('after_commit')
            return {'ok':True,'sequence':event.sequence,'event_id':event.event_id,'request_id':req['request_id'],'replayed':False}
        except BaseException:
            if not committed and db.in_transaction: db.execute('ROLLBACK')
            raise
    finally:
        lifecycle._admitted=False
        try: lifecycle.release(token)
        except Exception:
            # If COMMIT succeeded, release failure must not change its outcome.
            if not committed: raise


def process_reconciled(conn,lifecycle,*,allowed_uids):
    uid=authorize_peer(conn,allowed_uids=allowed_uids)
    req=_readline(conn)
    if not isinstance(req,dict): raise ServiceError('invalid request')
    if req.get('op') in ('health','snapshot'):
        if set(req)!={'op'}: raise ServiceError('unexpected fields')
        lifecycle.verify_integrity()
        state=lifecycle._replay()
        return {'ok':True,'status':'ready'} if req['op']=='health' else {'ok':True,'states':state.snapshot()}
    if req.get('op')=='receipt':
        if set(req)!={'op','request_id'} or type(req['request_id']) is not str or not 0<len(req['request_id'])<=256:
            raise ServiceError('invalid receipt query')
        lifecycle.verify_integrity()
        if not lifecycle.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_request_receipts'").fetchone():
            return {'ok':True,'found':False}
        row=lifecycle.db.execute('SELECT peer_uid,sequence,event_id FROM life_request_receipts WHERE request_id=?',(req['request_id'],)).fetchone()
        if not row or row[0]!=uid: return {'ok':True,'found':False}
        lifecycle._replay()
        return {'ok':True,'found':True,'sequence':row[1],'event_id':row[2]}
    return apply_request(lifecycle,req,uid)


class ReconciledWriteService(ProductionWriteService):
    def handle(self,conn,lifecycle):
        return process_reconciled(conn,lifecycle,allowed_uids=self.allowed_uids)


class ProductionWriteSupervisor(CrossUIDSupervisor):
    """Must be started under the pre-provisioned dedicated service UID."""
    def __init__(self,registry,db,socket_path,*,allowed_uids):
        super().__init__(registry,db,socket_path,allowed_uids=allowed_uids,
                         cli_module='lifesupport.reconciled_write_cli')
