"""ISLAND-GEO-013: explicit crash boundaries and recovery classification.
Crash hooks are opt-in test instrumentation, not production authorization.
"""
import os, signal
from .anchored_admission import AdmissionDenied, AnchoredAdmission, digest, chain, _lock

POINTS = ('before_reconcile','after_reconcile','before_phase_begin','after_phase_begin',
          'before_phase_commit','after_phase_commit','before_witness_cas',
          'after_witness_cas','before_local_begin','after_local_begin',
          'before_local_commit','after_local_commit','before_ipc_response')

def killpoint(name, target):
    if target is not None and target not in POINTS:
        raise AdmissionDenied('unknown crash boundary')
    if name == target:
        os.kill(os.getpid(), signal.SIGKILL)

class CrashInstrumentedAdmission(AnchoredAdmission):
    def admit(self, payload, crash_at=None):
        if crash_at is not None and crash_at not in POINTS:
            raise AdmissionDenied('unknown crash boundary')
        ph=digest(payload)
        with _lock(self.lock_path):
            db=self._connect()
            try:
                killpoint('before_reconcile',crash_at)
                local=self._reconcile(db)
                killpoint('after_reconcile',crash_at)
                seq=local['sequence']+1
                head=chain(local['digest'],seq,ph)
                killpoint('before_phase_begin',crash_at)
                db.execute('BEGIN IMMEDIATE')
                try:
                    killpoint('after_phase_begin',crash_at)
                    db.execute('INSERT INTO phase VALUES (1,?,?,?,?)',(seq,local['digest'],head,ph))
                    killpoint('before_phase_commit',crash_at)
                    db.execute('COMMIT')
                except BaseException:
                    if db.in_transaction: db.execute('ROLLBACK')
                    raise
                killpoint('after_phase_commit',crash_at)
                killpoint('before_witness_cas',crash_at)
                self.witness.execute('cas',{'sequence':seq,'previous':local['digest'],'digest':head})
                killpoint('after_witness_cas',crash_at)
                killpoint('before_local_begin',crash_at)
                db.execute('BEGIN IMMEDIATE')
                try:
                    killpoint('after_local_begin',crash_at)
                    db.execute('INSERT INTO accepted VALUES (?,?,?)',(seq,head,ph))
                    db.execute('DELETE FROM phase WHERE id=1')
                    killpoint('before_local_commit',crash_at)
                    db.execute('COMMIT')
                except BaseException:
                    if db.in_transaction: db.execute('ROLLBACK')
                    raise
                killpoint('after_local_commit',crash_at)
                killpoint('before_ipc_response',crash_at)
                return {'admitted':True,'sequence':seq,'digest':head,'engineering_approval':'BLOCKED/NO-GO'}
            finally: db.close()
