"""LOG-CORE-016: opt-in consistency gate and bounded crash probe.

This module does not claim distributed atomicity or production admission.
"""
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from .secure import AdmissionError
from .stage015 import AttestedLogisticsService


class ConsistencyGatedLogisticsService(AttestedLogisticsService):
    """Fail closed when witness, checkpoint or phase journal disagree.

    No automatic reconciliation is performed by this gate. Existing public APIs
    and recovery admission semantics are preserved.
    """
    def _assert_consistent(self):
        self._check_files()
        if self.phase_path.exists():
            raise AdmissionError('pending phase journal: offline reconciliation required')
        if self._read_anchor() != self._checkpoint():
            raise AdmissionError('ledger/witness checkpoint mismatch')

    def _dispatch(self, uid, req):
        if not isinstance(req, dict):
            raise AdmissionError('invalid IPC payload')
        action = req.get('action')
        if action in ('recover', 'verify', 'get_cargo'):
            self._assert_consistent()
        if action == 'issue_permit':
            raise AdmissionError('legacy permit issuance prohibited')
        return super()._dispatch(uid, req)


def kill_boundary_probe(*, timeout=4):
    """Test one *real* SIGKILL boundary with a disposable child process.

    The child signals readiness before SIGKILL. This is not an exhaustive
    SQLite/witness/permit/IPC crash-point matrix.
    """
    if not hasattr(signal, 'SIGKILL'):
        raise AdmissionError('SIGKILL unavailable')
    with tempfile.TemporaryDirectory(prefix='log016_') as root:
        marker = Path(root) / 'prepared'
        script = ('import os,sys,time; fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); '
                  'os.write(fd,b"prepared"); os.fsync(fd); os.close(fd); '
                  'print("READY",flush=True); time.sleep(30)')
        p = subprocess.Popen([sys.executable, '-u', '-c', script, str(marker)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import select
            if not select.select([p.stdout], [], [], timeout)[0] or p.stdout.readline().strip() != 'READY':
                raise AdmissionError('crash probe not ready')
            os.kill(p.pid, signal.SIGKILL)
            p.communicate(timeout=timeout)
            if p.returncode != -signal.SIGKILL or marker.read_bytes() != b'prepared':
                raise AdmissionError('SIGKILL boundary evidence mismatch')
            return {'signal': 'SIGKILL', 'returncode': p.returncode, 'durable_marker': True}
        finally:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=timeout)


def production_admission(*args, **kwargs):
    raise AdmissionError('LOG-CORE-016 BLOCKED: independent four-UID transaction and crash evidence absent')
