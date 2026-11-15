"""AI-CORE-012: fresh-process anchored service and durable recovery permit fencing.

Production factory is trusted deployment code; no arbitrary client-supplied imports.
"""
import importlib
import os
import sqlite3
import sys
from .isolation import AdmissionIPCServer, recovery_permit
from .lifecycle import RecoveryRequired
from .orchestration import production_admission

class DurableRecoveryAuthorizer:
    """Consume a permit durably BEFORE changing the external checkpoint.

    Crash after consumption but before checkpoint advancement leaves a fenced
    state requiring a DIFFERENT operator-issued permit. No auto-reconciliation.
    """
    def __init__(self, gateway, secret):
        if not isinstance(secret, bytes) or len(secret)<32: raise ValueError('recovery secret')
        self.gateway=gateway; self.secret=secret
        with gateway.store._lock:
            gateway.store._db.execute('CREATE TABLE IF NOT EXISTS production_recovery_permits (id TEXT PRIMARY KEY, seq INTEGER NOT NULL, head TEXT NOT NULL)')

    def reconcile(self, permit):
        import hmac
        if not isinstance(permit,dict) or set(permit)!={'id','seq','head','mac'}:
            raise RecoveryRequired('RECOVERY_PERMIT_INVALID')
        try:
            expected=recovery_permit(self.secret,permit['id'],permit['seq'],permit['head'])
            if not isinstance(permit['mac'],str) or not hmac.compare_digest(expected['mac'],permit['mac']):
                raise ValueError('mac')
        except (ValueError,TypeError,KeyError) as exc:
            raise RecoveryRequired('RECOVERY_PERMIT_INVALID') from exc
        gw=self.gateway
        with gw.manager.lock,gw.store._lock:
            db=gw.store._db
            if gw.checkpoint.read()!=(permit['seq'],permit['head']):
                raise RecoveryRequired('RECOVERY_PERMIT_STALE')
            gw._schema_check(); gw.manager._check()
            # Confirm exactly one unanchored audit record before burning permit.
            seq,head=gw._audit_check()
            if seq!=permit['seq']+1: raise RecoveryRequired('RECONCILIATION_AMBIGUOUS')
            row=db.execute('SELECT previous FROM gateway_audit WHERE seq=?',(seq,)).fetchone()
            if row is None or row[0]!=permit['head']:
                raise RecoveryRequired('RECONCILIATION_CHAIN_MISMATCH')
            try:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO production_recovery_permits VALUES (?,?,?)',
                           (permit['id'],permit['seq'],permit['head']))
                db.execute('COMMIT')
            except sqlite3.IntegrityError as exc:
                db.execute('ROLLBACK')
                raise RecoveryRequired('RECOVERY_PERMIT_REPLAY') from exc
            except BaseException:
                try: db.execute('ROLLBACK')
                except sqlite3.Error: pass
                raise
            # This is intentionally a separate durability domain.
            return gw.reconcile(authorized=True)

class ProductionAdmissionIPCServer(AdmissionIPCServer):
    def __init__(self, gateway, socket_path, *, allowed_uids, recovery_secret, recovery_uids=()):
        # Refuse unanchored gateway in production.
        if not hasattr(gateway,'checkpoint') or not hasattr(gateway,'verify'):
            raise RecoveryRequired('ANCHORED_GATEWAY_REQUIRED')
        gateway.verify()
        super().__init__(gateway,socket_path,allowed_uids=allowed_uids,
                         recovery_secret=recovery_secret,recovery_uids=recovery_uids)
        self.recovery=DurableRecoveryAuthorizer(gateway,recovery_secret)

    def serve(self, *, ready=None):
        # Recheck before binding; fail closed if checkpoint is inconsistent.
        self.gateway.verify()
        return super().serve(ready=ready)

def run_factory(factory_path):
    """Factory must return a fully initialized ProductionAdmissionIPCServer.

    Factory and secrets are trusted local configuration, not IPC request fields.
    """
    if ':' not in factory_path: raise ValueError('factory format module:function')
    module,name=factory_path.split(':',1)
    factory=getattr(importlib.import_module(module),name)
    service=factory()
    if not isinstance(service,ProductionAdmissionIPCServer):
        raise TypeError('production factory must return ProductionAdmissionIPCServer')
    service.serve()

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: python -m ai_cognition.production012 module:function')
    run_factory(sys.argv[1])

if __name__=='__main__':
    raise SystemExit('LEGACY_PRODUCTION_ENTRYPOINT_DISABLED: use production015')
