import os
import pytest
from energy.witness_protocol import JournaledWitnessEnergyService, PendingWitnessTransaction
from energy.trust import AdmissionDenied
from test_stage014 import setup


def create(adm,p,cp,w):
    return JournaledWitnessEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp,w)


def test_issue_recover_journal_cleanup(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    service=create(adm,p,cp,w)
    token=service.issue(os.geteuid()).token
    assert not (cp/'witness.phase').exists()
    assert create(adm,p,cp,w).recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]
    assert not (cp/'witness.phase').exists()


def test_cas_failure_retains_journal(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    service=create(adm,p,cp,w)
    w.compare_and_swap=lambda a,b: False
    with pytest.raises(AdmissionDenied): service.issue(os.geteuid())
    assert (cp/'witness.phase').exists()
    with pytest.raises(PendingWitnessTransaction): create(adm,p,cp,w)


def test_pending_phase_blocks_startup(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    service=create(adm,p,cp,w)
    service._phase_write(w.record,'issue')
    with pytest.raises(PendingWitnessTransaction): create(adm,p,cp,w)


def test_symlink_phase_denied(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    (cp/'witness.phase').symlink_to(p/'permits.db')
    with pytest.raises(PendingWitnessTransaction): create(adm,p,cp,w)


def test_replay_consumed_denied_with_journal(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    service=create(adm,p,cp,w)
    token=service.issue(os.geteuid()).token
    service.recover(os.geteuid(),token)
    with pytest.raises(AdmissionDenied):service.recover(os.geteuid(),token)
    assert (cp/'witness.phase').exists() # conservative: ambiguous failure quarantined
