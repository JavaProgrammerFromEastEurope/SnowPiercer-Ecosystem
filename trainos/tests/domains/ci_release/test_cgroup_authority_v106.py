"""v106 authority regression: real OS refusal versus explicit synthetic unit controls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from scripts.ci import cgroup_authority_v106 as auth

ROOT = Path(__file__).resolve().parents[3]
CMD = [sys.executable, '-m', 'scripts.ci.cgroup_authority_v106']


def test_real_linux_host_cgroup_probe_is_noncertifying():
    result = auth.probe_environment(Path('/sys/fs/cgroup/trainos-authority'))
    assert result['schema'] == 'trainos.cgroup-v2-probe.v106'
    assert result['production_admitted'] is False
    assert isinstance(result['errors'], list)


def test_production_no_delegation_blocks_before_exec(tmp_path):
    marker = tmp_path / 'executed'
    report = tmp_path / 'report.json'
    code = f'from pathlib import Path;Path({str(marker)!r}).write_text("BAD")'
    command = [*CMD, '--production', '--report', str(report),
               '--delegated-root', '/sys/fs/cgroup/trainos-authority',
               '--service-uid', '65534', '--client-uid', '65533', '--',
               sys.executable, '-m', 'scripts.ci.process_supervisor_v105',
               '--', sys.executable, '-c', code]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 125
    assert not marker.exists()
    assert report.exists()
    state = json.loads(report.read_text())
    assert state['production_admitted'] is False
    assert state['authority_exitcode'] == 125


def test_unprivileged_cannot_admit_even_with_fake_writable_directory(tmp_path):
    # An unprivileged direct invocation must not gain privileged service access.
    with pytest.raises(auth.AdmissionDenied):
        auth.require_admission(tmp_path, service_uid=0, client_uid=0)
    with pytest.raises(auth.AdmissionDenied):
        auth.require_admission(tmp_path, service_uid=1, client_uid=1)


def test_symlink_root_rejected_before_attach(tmp_path):
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(auth.AdmissionDenied):
        auth.require_admission(link, 65534, 65533)


def test_kernel_cgroup_kill_control_unit_only(tmp_path, monkeypatch):
    # Synthetic control-file semantics are UNIT ONLY; not an OS safety proof.
    (tmp_path / 'cgroup.kill').write_text('')
    (tmp_path / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
    assert auth._kill_and_verify(tmp_path, 0.1)
    assert (tmp_path / 'cgroup.kill').read_text() == '1'
    (tmp_path / 'cgroup.events').write_text('populated 1\n')
    assert not auth._kill_and_verify(tmp_path, 0.05)


def test_no_production_flag_never_execs_command(tmp_path):
    marker = tmp_path / 'executed'
    result = subprocess.run([*CMD, '--', sys.executable, '-c',
        f'from pathlib import Path;Path({str(marker)!r}).touch()'],
        cwd=ROOT, capture_output=True, text=True, timeout=8)
    assert result.returncode == 125 and not marker.exists()


def test_untrusted_executable_rejected_before_cgroup_work(tmp_path):
    marker = tmp_path / 'executed'
    result = subprocess.run([*CMD, '--production', '--',
        sys.executable, '-c', f'from pathlib import Path;Path({str(marker)!r}).touch()'],
        cwd=ROOT, capture_output=True, text=True, timeout=8)
    assert result.returncode == 125 and not marker.exists()


def test_pidfd_available_for_identity_bound_signals():
    if sys.platform != 'linux' or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        pytest.skip('pidfd unavailable')
    child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
    fd = os.pidfd_open(child.pid)
    try:
        signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
        assert child.wait(timeout=3) == -signal.SIGKILL
        with pytest.raises(ProcessLookupError):
            signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
    finally:
        os.close(fd)
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
