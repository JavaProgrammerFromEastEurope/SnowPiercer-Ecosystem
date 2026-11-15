import os
import pytest
from snowpiercer_logistics.stage010 import IsolationPolicy
from snowpiercer_logistics.stage014 import four_uid_ipc_probe, production_admission
from snowpiercer_logistics.secure import AdmissionError

def test_gate_remains_closed():
    with pytest.raises(AdmissionError): production_admission({'passed':True})

def test_rejects_duplicate_identities():
    with pytest.raises(AdmissionError): four_uid_ipc_probe(IsolationPolicy(12001,12002,12003,(12001,)))

@pytest.mark.skipif(os.geteuid()!=0 or os.uname().sysname!='Linux',reason='requires Linux root')
def test_real_four_uid_ipc_accept_and_reject():
    results=four_uid_ipc_probe(IsolationPolicy(12001,12002,12003,(12004,)))
    assert len(results)==6
    assert sum(r['accepted'] for r in results)==3
    assert len({r['server_uid'] for r in results})==3
