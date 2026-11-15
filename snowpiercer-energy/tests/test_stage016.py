import os
import pytest
from energy.reconciliation import EvidenceReconciledEnergyService, ReconciliationEvidence
from energy.witness_protocol import PendingWitnessTransaction
from energy.trust_boundary import WitnessRecord
from test_stage014 import setup


def make(adm,p,cp,w):
    return EvidenceReconciledEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp,w)


def pending(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    service=make(adm,p,cp,w)
    previous=w.read()
    # Model crash after local commit + successful witness CAS, before phase clear.
    service._phase_write(previous,'issue')
    from energy.permit_anchor import AnchoredDurableEnergyService
    AnchoredDurableEnergyService.issue(service,os.geteuid())
    service._publish(previous)
    evidence=ReconciliationEvidence('issue',previous,w.read(),'test-witness','test-approval')
    return service,w,cp,evidence


def test_verified_completed_phase_reconciles(tmp_path):
    s,w,cp,e=pending(tmp_path)
    assert s.reconcile_completed(e,lambda x: x==e)==w.read()
    assert not (cp/'witness.phase').exists()


def test_rejects_without_external_approval(tmp_path):
    s,w,cp,e=pending(tmp_path)
    with pytest.raises(PendingWitnessTransaction): s.reconcile_completed(e,lambda x:False)
    assert (cp/'witness.phase').exists()


def test_rejects_stale_witness(tmp_path):
    s,w,cp,e=pending(tmp_path)
    w.record=e.previous
    with pytest.raises(PendingWitnessTransaction):s.reconcile_completed(e,lambda x:True)


def test_rejects_forged_previous(tmp_path):
    s,w,cp,e=pending(tmp_path)
    fake=ReconciliationEvidence('issue',WitnessRecord(999,0,'x','y'),e.observed,'w','a')
    with pytest.raises(PendingWitnessTransaction):s.reconcile_completed(fake,lambda x:True)


def test_rejects_local_rollback(tmp_path):
    s,w,cp,e=pending(tmp_path)
    # Witness remains advanced; local permit DB is changed without updating anchor.
    with open(s.permit_db,'ab') as f:f.write(b'\n')
    # Semantic fingerprint intentionally excludes raw SQLite byte changes; test
    # a semantic rollback by changing the consumed flag directly.
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(s.permit_db)) as db, db:
        db.execute('UPDATE permits SET consumed=1')
    with pytest.raises(Exception):
        s.reconcile_completed(e,lambda x:True)
    assert (cp/'witness.phase').exists()
