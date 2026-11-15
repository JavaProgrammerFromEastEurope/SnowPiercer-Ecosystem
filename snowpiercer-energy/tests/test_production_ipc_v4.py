import socket
import tempfile
from pathlib import Path
import pytest
from energy.production_ipc_v4 import BoundedIsolatedEnergyService
from energy.ipc_diagnostics import AcceptDeadlineExceeded
from energy.trust import AdmissionDenied


def test_deadline_validation_before_service_initialization():
    for bad in (0, -1, 61, True, '1'):
        with pytest.raises(AdmissionDenied):
            BoundedIsolatedEnergyService(accept_timeout_s=bad)
        with pytest.raises(AdmissionDenied):
            BoundedIsolatedEnergyService(request_timeout_s=bad)


def test_bounded_accept_timeout():
    from energy.ipc_diagnostics import bounded_accept
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / 'sock')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(p)
            sock.listen()
            with pytest.raises(AcceptDeadlineExceeded):
                bounded_accept(sock, .01)


def test_production_class_requires_os_policy():
    with pytest.raises(TypeError):
        BoundedIsolatedEnergyService(None, '/tmp/nonexistent', {1}, None, None, None, None)


def test_diagnostic_method_exists():
    assert callable(BoundedIsolatedEnergyService.diagnostic_snapshot)
