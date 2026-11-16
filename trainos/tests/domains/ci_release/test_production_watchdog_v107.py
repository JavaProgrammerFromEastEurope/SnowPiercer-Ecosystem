"""v107 fail-closed and mock-only watchdog checks: not real kernel cgroup proof."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.ci.cgroup_watchdog_v107 import (AdmissionDenied, GROUP_PATTERN,
    SingleWatchdog, kill_managed_groups, verify_os_manager, run_watchdog)


def test_group_name_strict():
    assert GROUP_PATTERN.fullmatch('trainos-run-'+'a'*32)
    assert not GROUP_PATTERN.fullmatch('trainos-run-../escape')
    assert not GROUP_PATTERN.fullmatch('trainos-run-'+'a'*31+'x')


def test_untrusted_watchdog_lock_denied(tmp_path):
    state=tmp_path/'state'
    state.mkdir(mode=0o777)
    os.chmod(state,0o777)
    with pytest.raises(AdmissionDenied):
        with SingleWatchdog(state):pass


def test_watchdog_lock_exclusive(tmp_path):
    state=tmp_path/'state';state.mkdir(mode=0o700)
    with SingleWatchdog(state):
        with pytest.raises(BlockingIOError):
            with SingleWatchdog(state): pass


def test_cgroup_mock_sweep_is_only_logical_not_kernel(tmp_path):
    root=tmp_path/'cgroups';root.mkdir()
    group=root/('trainos-run-'+'0'*32);group.mkdir(mode=0o700)
    (group/'cgroup.events').write_text('populated 0\n')
    (group/'cgroup.kill').write_text('')
    outside=root/'not-a-managed-group';outside.mkdir()
    invocations=[]
    def fake_write(path,value):
        invocations.append((path.name,value))
        # Ordinary filesystem mock cannot rmdir kernel pseudo-files; simulate it.
        (group/'cgroup.events').unlink()
        (group/'cgroup.kill').unlink()
    report=kill_managed_groups(root,writer=fake_write,state_reader=lambda g:{'populated':'0'})
    assert report[0]['empty_verified']
    assert invocations==[('cgroup.kill','1')]
    assert not group.exists() and outside.exists()


def test_cgroup_mock_tamper_denies(tmp_path):
    root=tmp_path/'groups';root.mkdir()
    group=root/('trainos-run-'+'a'*32);group.mkdir(mode=0o777)
    os.chmod(group,0o777)
    (group/'cgroup.events').write_text('populated 1\n')
    (group/'cgroup.kill').write_text('')
    with pytest.raises(AdmissionDenied):kill_managed_groups(root)


def test_production_entrypoint_denied_by_os(tmp_path):
    report=tmp_path/'denial.json'
    marker=tmp_path/'MUST_NOT_RUN'
    cmd=[sys.executable,'-m','scripts.ci.cgroup_authority_v106',
         '--','/usr/bin/touch',str(marker)]
    rc=run_watchdog(Path('/sys/fs/cgroup/trainos-authority'),tmp_path,
                    65534,65533,2.0,report,cmd)
    result=json.loads(report.read_text())
    assert rc==125 and result['production_admitted'] is False
    assert not marker.exists()
    assert result['status']=='BLOCKED/NO-GO'


def test_os_manager_not_proven_on_non_systemd():
    assert Path('/proc/1/comm').read_text().strip()!='systemd'
    with pytest.raises(AdmissionDenied):verify_os_manager()


def test_bad_command_denied_without_fork(tmp_path):
    report=tmp_path/'denied.json'
    assert run_watchdog(tmp_path,tmp_path,1,2,1,report,['/bin/echo','hello'])==125
    assert json.loads(report.read_text())['production_admitted'] is False
