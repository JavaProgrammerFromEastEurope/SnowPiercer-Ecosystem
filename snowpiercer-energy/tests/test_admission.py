import os
import multiprocessing as mp
import pytest
from energy import (Asset, AssetKind, EnergyMode, EnergySystem, PersistentEnergyLedger,
                    TrustedEnergyGateway, UnifiedEnergyAdmission, AdmissionDenied, AnchorMismatch)


def make(tmp_path):
    system = EnergySystem({'gen': Asset('gen', AssetKind.SOURCE, 100)}, EnergyMode.SIMULATION)
    ledger = PersistentEnergyLedger(tmp_path/'energy.db', system)
    anchor = tmp_path/'anchor'; anchor.mkdir(mode=0o700, exist_ok=True)
    gateway = TrustedEnergyGateway(ledger, anchor)
    lock = tmp_path/'lock'; lock.mkdir(mode=0o700, exist_ok=True)
    return UnifiedEnergyAdmission(gateway, lock/'unified.lock')


def test_startup_and_apply(tmp_path):
    admission = make(tmp_path)
    assert admission.startup()[0] == 0
    assert admission.apply('a', [], duration_h=1).sequence == 1
    assert admission.startup()[0] == 1


def test_one_shot_permit(tmp_path):
    admission = make(tmp_path)
    permit = admission.issue_recovery_permit(os.geteuid())
    assert admission.cold_recover(permit, os.geteuid())[0] == 0
    with pytest.raises(AdmissionDenied): admission.cold_recover(permit, os.geteuid())


def test_wrong_uid_and_stale_permit(tmp_path):
    admission = make(tmp_path)
    with pytest.raises(AdmissionDenied): admission.issue_recovery_permit(os.geteuid()+1)
    permit = admission.issue_recovery_permit(os.geteuid())
    with pytest.raises(AdmissionDenied): admission.cold_recover(permit, os.geteuid()+1)
    admission.apply('new', [], duration_h=1)
    with pytest.raises(AdmissionDenied): admission.cold_recover(permit, os.geteuid())


def test_rollback_and_anchor_removal(tmp_path):
    admission = make(tmp_path)
    admission.apply('a', [], duration_h=1)
    (tmp_path/'anchor'/'energy.anchor').unlink()
    with pytest.raises(AnchorMismatch): admission.startup()


def test_lock_substitution(tmp_path):
    admission = make(tmp_path)
    admission.startup()
    lock = tmp_path/'lock'/'unified.lock'
    lock.unlink(); lock.symlink_to(tmp_path/'energy.db')
    with pytest.raises(OSError): admission.startup()


def test_crash_before_sqlite_commit(tmp_path):
    admission = make(tmp_path)
    def kill(point):
        if point == 'after_insert': os._exit(77)
    pid = os.fork()
    if pid == 0:
        admission = make(tmp_path)
        admission.apply('killed', [], duration_h=1, fault_hook=kill)
        os._exit(0)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 77
    assert admission.startup()[0] == 0


def test_crash_after_sqlite_commit(tmp_path):
    admission = make(tmp_path)
    def kill(point):
        if point == 'after_sqlite_commit': os._exit(78)
    pid = os.fork()
    if pid == 0:
        admission = make(tmp_path)
        admission.apply('killed', [], duration_h=1, fault_hook=kill)
        os._exit(0)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 78
    assert admission.startup()[0] == 1


def test_legacy_bypass_is_detected_but_not_prevented(tmp_path):
    admission = make(tmp_path)
    admission.gateway.ledger.apply('legacy', [], duration_h=1)
    with pytest.raises(AnchorMismatch): admission.startup()
