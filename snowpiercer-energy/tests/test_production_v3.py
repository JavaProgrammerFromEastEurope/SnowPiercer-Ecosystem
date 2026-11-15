import os
import tempfile
from pathlib import Path
import pytest
from energy.production_v3 import DurableEnergyService
from energy.trust import AdmissionDenied, TrustedEnergyGateway
from energy.admission import UnifiedEnergyAdmission
from energy.persistence import PersistentEnergyLedger

# Construction is checked against actual legacy signatures in existing tests.
def test_module_import():
    assert DurableEnergyService.__name__ == 'DurableEnergyService'
from energy import Asset,AssetKind,EnergyMode,EnergySystem

def make(tmp_path):
    system=EnergySystem({'gen':Asset('gen',AssetKind.SOURCE,100)},EnergyMode.SIMULATION)
    ledger=PersistentEnergyLedger(tmp_path/'ledger.db',system)
    anchor=tmp_path/'anchor';anchor.mkdir(mode=0o700)
    gateway=TrustedEnergyGateway(ledger,anchor)
    locks=tmp_path/'locks';locks.mkdir(mode=0o700)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    adm=UnifiedEnergyAdmission(gateway,locks/'lock')
    return adm,private

def test_durable_replay_restart(tmp_path):
    adm,p=make(tmp_path)
    s=DurableEnergyService(adm,p/'sock', [os.geteuid()],p/'permits.db')
    token=s.issue(os.geteuid()).token
    s2=DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
    assert s2.recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]
    with pytest.raises(AdmissionDenied):s.recover(os.geteuid(),token)

def test_wrong_uid_does_not_consume(tmp_path):
    adm,p=make(tmp_path)
    s=DurableEnergyService(adm,p/'sock',[os.geteuid(),os.geteuid()+1],p/'permits.db')
    token=s.issue(os.geteuid()).token
    with pytest.raises(AdmissionDenied):s.recover(os.geteuid()+1,token)
    assert s.recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]

def test_stale_permit_consumed(tmp_path):
    adm,p=make(tmp_path)
    s=DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
    token=s.issue(os.geteuid()).token
    adm.apply('next',[],duration_h=1)
    with pytest.raises(AdmissionDenied):s.recover(os.geteuid(),token)
    with pytest.raises(AdmissionDenied):s.recover(os.geteuid(),token)

def test_missing_database_fail_closed(tmp_path):
    adm,p=make(tmp_path)
    s=DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
    (p/'permits.db').unlink()
    with pytest.raises(AdmissionDenied):s.issue(os.geteuid())

def test_symlink_database_fail_closed(tmp_path):
    adm,p=make(tmp_path)
    (p/'permits.db').symlink_to(p/'target')
    with pytest.raises(AdmissionDenied):DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
