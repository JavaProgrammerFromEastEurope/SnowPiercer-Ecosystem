import os
import pytest
from energy.trust_boundary import WitnessedEnergyService, WitnessRecord, WitnessUnavailable
from energy.trust import AdmissionDenied
from test_production_v3 import make

class Witness:
    def __init__(self, record): self.record = record
    def read(self): return self.record
    def compare_and_swap(self, old, new):
        if self.record != old or new.revision != old.revision + 1: return False
        self.record = new
        return True

def setup(tmp_path):
    adm, p = make(tmp_path)
    cp = tmp_path/'checkpoint'; cp.mkdir(mode=0o700)
    from energy.permit_anchor import AnchoredDurableEnergyService
    base = AnchoredDurableEnergyService(adm, p/'sock', [os.geteuid()], p/'permits.db', cp)
    seq, digest, _ = adm.gateway.snapshot()
    witness = Witness(WitnessRecord(0, seq, digest, base._fingerprint()))
    return adm,p,cp,witness

def create(adm,p,cp,w):
    return WitnessedEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp,w)

def test_witness_issue_recover_restart(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    s=create(adm,p,cp,w)
    token=s.issue(os.geteuid()).token
    assert w.record.revision==1
    s=create(adm,p,cp,w)
    assert s.recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]
    assert w.record.revision==2
    with pytest.raises(AdmissionDenied):s.recover(os.geteuid(),token)

def test_witness_detects_coordinated_local_rollback(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    s=create(adm,p,cp,w)
    old_db=(p/'permits.db').read_bytes()
    old_anchor=(cp/'permits.anchor').read_bytes()
    s.issue(os.geteuid())
    (p/'permits.db').write_bytes(old_db)
    (cp/'permits.anchor').write_bytes(old_anchor)
    with pytest.raises(AdmissionDenied):create(adm,p,cp,w)

def test_witness_unavailable_denied(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    class Offline:
        def read(self): raise OSError('offline')
        def compare_and_swap(self,a,b): return False
    with pytest.raises(WitnessUnavailable):create(adm,p,cp,Offline())

def test_witness_cas_rejected_denied(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    s=create(adm,p,cp,w)
    w.compare_and_swap=lambda a,b: False
    with pytest.raises(WitnessUnavailable):s.issue(os.geteuid())
    with pytest.raises(AdmissionDenied):create(adm,p,cp,w)

def test_missing_witness_denied(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    with pytest.raises(WitnessUnavailable):create(adm,p,cp,None)
