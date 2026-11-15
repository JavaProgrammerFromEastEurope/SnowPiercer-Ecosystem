"""CORE-012: deterministic permit crash and concurrent consumption tests (POSIX)."""
import os
import sqlite3
from contextlib import closing
import threading
import pytest
from energy.production_v3 import DurableEnergyService
from energy.trust import AdmissionDenied
from test_production_v3 import make

@pytest.mark.parametrize('point,expected_consumed', [('permit_before_commit',False),('permit_after_commit',True)])
def test_sigkill_equivalent_exit_at_commit_boundary(tmp_path,point,expected_consumed):
    import subprocess, sys
    adm,p=make(tmp_path)
    service=DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
    token=service.issue(os.geteuid()).token
    script = """import os,sys
from pathlib import Path
from energy import Asset,AssetKind,EnergyMode,EnergySystem
from energy.persistence import PersistentEnergyLedger
from energy.trust import TrustedEnergyGateway
from energy.admission import UnifiedEnergyAdmission
from energy.production_v3 import DurableEnergyService
root=Path(sys.argv[1]); token=sys.argv[2]
system=EnergySystem({'gen':Asset('gen',AssetKind.SOURCE,100)},EnergyMode.SIMULATION)
ledger=PersistentEnergyLedger(root/'ledger.db',system)
gateway=TrustedEnergyGateway(ledger,root/'anchor')
adm=UnifiedEnergyAdmission(gateway,root/'locks'/'lock')
service=DurableEnergyService(adm,root/'private'/'sock',[os.geteuid()],root/'private'/'permits.db')
service.recover(os.geteuid(),token)
"""
    env=dict(os.environ, ENERGY_TEST_CRASH_POINT=point)
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path),token],env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode == (77 if point=='permit_before_commit' else 78), result.stderr
    with closing(sqlite3.connect(p/'permits.db')) as db:
        consumed=bool(db.execute('SELECT consumed FROM permits WHERE token=?',(token,)).fetchone()[0])
    assert consumed == expected_consumed
    if expected_consumed:
        with pytest.raises(AdmissionDenied):service.recover(os.geteuid(),token)
    else:
        assert service.recover(os.geteuid(),token)==adm.gateway.snapshot()[:2]

def test_concurrent_permit_consume_exactly_once(tmp_path):
    adm,p=make(tmp_path)
    s=DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
    token=s.issue(os.geteuid()).token
    results=[]
    def worker():
        try:
            s.recover(os.geteuid(),token)
            results.append('ok')
        except AdmissionDenied:
            results.append('denied')
    threads=[threading.Thread(target=worker) for _ in range(8)]
    for t in threads:t.start()
    for t in threads:t.join(timeout=10);assert not t.is_alive()
    assert sorted(results)==['denied']*7+['ok']

def test_permit_db_corruption_fail_closed(tmp_path):
    adm,p=make(tmp_path)
    s=DurableEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db')
    s.issue(os.geteuid())
    (p/'permits.db').write_bytes(b'not a database')
    with pytest.raises((AdmissionDenied,sqlite3.DatabaseError)):
        s.issue(os.geteuid())
