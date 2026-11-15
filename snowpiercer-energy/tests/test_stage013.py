import os
import shutil
import pytest
from energy.permit_anchor import AnchoredDurableEnergyService
from energy.trust import AdmissionDenied
from test_production_v3 import make

def service(tmp_path):
    adm, p = make(tmp_path)
    cp = tmp_path / 'checkpoint'; cp.mkdir(mode=0o700)
    return adm, p, cp, AnchoredDurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp)

def test_issue_consume_restart(tmp_path):
    adm,p,cp,s=service(tmp_path)
    token=s.issue(os.geteuid()).token
    t=AnchoredDurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp)
    assert t.recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]
    with pytest.raises(AdmissionDenied):t.recover(os.geteuid(),token)

def test_db_rollback_detected(tmp_path):
    adm,p,cp,s=service(tmp_path)
    s.issue(os.geteuid())
    old=(p/'permits.db').read_bytes()
    s.issue(os.geteuid())
    (p/'permits.db').write_bytes(old)
    with pytest.raises(AdmissionDenied):s.issue(os.geteuid())

def test_checkpoint_missing_detected(tmp_path):
    adm,p,cp,s=service(tmp_path)
    s.issue(os.geteuid())
    (cp/'permits.anchor').unlink()
    with pytest.raises((AdmissionDenied,FileNotFoundError)):s.issue(os.geteuid())

def test_checkpoint_symlink_detected(tmp_path):
    adm,p,cp,s=service(tmp_path)
    (cp/'permits.anchor').unlink()
    (cp/'permits.anchor').symlink_to(p/'permits.db')
    with pytest.raises(AdmissionDenied):s.issue(os.geteuid())

def test_wrong_uid_does_not_consume(tmp_path):
    adm,p,cp,s=service(tmp_path)
    token=s.issue(os.geteuid()).token
    with pytest.raises(AdmissionDenied):s.recover(os.geteuid()+1,token)
    assert s.recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]
