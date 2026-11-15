import pytest
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage016 import ConsistencyGatedLogisticsService, kill_boundary_probe, production_admission


def test_production_gate_remains_closed():
    with pytest.raises(AdmissionError, match='BLOCKED'):
        production_admission()


def test_real_sigkill_boundary():
    result = kill_boundary_probe()
    assert result['returncode'] == -9
    assert result['durable_marker']


def test_legacy_permit_issuance_is_denied_before_dispatch():
    obj = object.__new__(ConsistencyGatedLogisticsService)
    with pytest.raises(AdmissionError, match='legacy permit'):
        obj._dispatch(123, {'action': 'issue_permit', 'args': {}})


def test_invalid_ipc_payload_is_denied():
    obj = object.__new__(ConsistencyGatedLogisticsService)
    with pytest.raises(AdmissionError, match='payload'):
        obj._dispatch(123, [])
