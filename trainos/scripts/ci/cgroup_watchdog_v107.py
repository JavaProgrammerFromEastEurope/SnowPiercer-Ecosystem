"""TrainOS v107 independent cgroup lifecycle watchdog: production FAIL-CLOSED.

This is an OS-service process, not a thread/child of the authority. The service
manager MUST restart it after SIGKILL. On restart it FIRST kills all outstanding
managed cgroups before authorizing another operation. The watchdog itself must
run outside those cgroups. No fake cgroupfs is accepted by production admission.

Note: on this host cgroup2 is read-only and PID1 is not systemd; all production
admission MUST be denied. A passing mock unit test is never kernel evidence.
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Callable

from scripts.ci.cgroup_authority_v106 import (AdmissionDenied, _cgroup_state,
    _write_control, probe_environment, require_admission)

GROUP_PATTERN = re.compile(r'^trainos-run-[0-9a-f]{32}$')
SERVICE_NAME = 'trainos-watchdog-v107.service'


def verify_os_manager() -> None:
    """Do not trust merely supplied environment variables as OS admission proof."""
    try:
        init = Path('/proc/1/comm').read_text().strip()
        cgroup = Path('/proc/self/cgroup').read_text()
    except OSError as exc:
        raise AdmissionDenied(f'OS manager provenance unavailable: {exc}') from exc
    if init != 'systemd' or SERVICE_NAME not in cgroup:
        raise AdmissionDenied('dedicated systemd watchdog service cgroup not verified')


def _protected_directory(directory: Path) -> None:
    if not directory.is_absolute() or directory.is_symlink():
        raise AdmissionDenied('state directory must be absolute and not symlink')
    s = directory.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or (s.st_mode & 0o077):
        raise AdmissionDenied('state directory must be root-owned and mode 0700')


class SingleWatchdog:
    """OS-backed exclusive lock; FD is held for entire watchdog lifetime."""
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.fd: int | None = None

    def __enter__(self):
        _protected_directory(self.state_dir)
        fd = os.open(self.state_dir / 'watchdog.lock',
                     os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_nlink != 1 or (info.st_mode & 0o077):
                raise AdmissionDenied('watchdog lock permissions/owner invalid')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def kill_managed_groups(delegated_root: Path, timeout: float = 5.0,
                        writer: Callable[[Path, str], None] = _write_control,
                        state_reader: Callable[[Path], dict] = _cgroup_state) -> list[dict]:
    """Destructively sweep ONLY root-owned, private, regex-matched run groups.

    Called by independent OS manager on initial startup, authority termination,
    and systemd restart after watchdog SIGKILL. Errors always block admission.
    """
    if not 0 < timeout <= 60:
        raise ValueError('invalid cleanup timeout')
    records = []
    for group in sorted(delegated_root.iterdir()):
        if not GROUP_PATTERN.fullmatch(group.name):
            continue
        info = group.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or (info.st_mode & 0o077):
            raise AdmissionDenied(f'untrusted cgroup path: {group}')
        control = group / 'cgroup.kill'
        if not control.is_file() or not (group / 'cgroup.events').is_file():
            raise AdmissionDenied(f'kernel cgroup controls unavailable: {group}')
        writer(control, '1')
        deadline = time.monotonic() + timeout
        while state_reader(group).get('populated') != '0' and time.monotonic() < deadline:
            time.sleep(0.025)
        if state_reader(group).get('populated') != '0':
            raise AdmissionDenied(f'cgroup remains populated: {group}')
        group.rmdir()
        records.append({'cgroup':group.name,'cgroup_kill_written':True,'empty_verified':True})
    return records


def run_watchdog(root: Path, state_dir: Path, service_uid: int, client_uid: int,
                 timeout: float, report_path: Path, command: list[str]) -> int:
    """Run exactly one authority, recover orphaned groups before/after.

    The production watchdog is launched by systemd (Restart=always). Its own
    termination with SIGKILL requires systemd to restart it and sweep groups;
    this second half cannot be proven in a non-systemd host.
    """
    report = {'schema':'trainos.cgroup-watchdog.v107','production_admitted':False,
              'cleanup_verified':False,'status':'BLOCKED/NO-GO','events':[],
              'pid1':None,'exit_code':125}
    proc = None
    pidfd = None
    try:
        if timeout <= 0 or timeout > 86400:
            raise AdmissionDenied('invalid watchdog timeout')
        verify_os_manager()
        require_admission(root, service_uid, client_uid)
        _protected_directory(state_dir)
        if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):
            raise AdmissionDenied('pidfd required')
        if command[:3] != [sys.executable,'-m','scripts.ci.cgroup_authority_v106']:
            raise AdmissionDenied('watchdog may launch only registered authority')
        with SingleWatchdog(state_dir):
            report['events'].append({'startup_recovered':kill_managed_groups(root)})
            # A real cgroup admission is done by the authority's pre-exec gate.
            proc = subprocess.Popen(command, close_fds=True)
            pidfd = os.pidfd_open(proc.pid)
            report['production_admitted'] = True
            began = time.monotonic()
            while proc.poll() is None and time.monotonic()-began < timeout:
                time.sleep(0.025)
            if proc.poll() is None:
                report['events'].append({'timeout':True})
                signal.pidfd_send_signal(pidfd,signal.SIGKILL,None,0)
            report['authority_exitcode'] = proc.wait(timeout=10)
            report['events'].append({'shutdown_recovered':kill_managed_groups(root)})
            report['cleanup_verified'] = True
            report['exit_code'] = (124 if time.monotonic()-began>=timeout else
                                  128-proc.returncode if proc.returncode<0 else proc.returncode)
            report['status'] = 'PASS' if report['exit_code']==0 else 'FAIL'
    except (AdmissionDenied, OSError, ValueError, BlockingIOError, subprocess.TimeoutExpired) as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        if proc is not None and proc.poll() is None and pidfd is not None:
            try:signal.pidfd_send_signal(pidfd,signal.SIGKILL,None,0)
            except OSError:pass
        if proc is not None:
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:pass
        report['exit_code'] = 125
    finally:
        if pidfd is not None:os.close(pidfd)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        tmp=report_path.with_suffix(report_path.suffix+'.tmp')
        tmp.write_text(json.dumps(report,indent=2)+'\n')
        tmp.replace(report_path)
    return report['exit_code']


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe',action='store_true')
    p.add_argument('--production',action='store_true')
    p.add_argument('--delegated-root',type=Path,default=Path('/sys/fs/cgroup/trainos-authority'))
    p.add_argument('--state-dir',type=Path,default=Path('/run/trainos-v107'))
    p.add_argument('--service-uid',type=int,default=-1)
    p.add_argument('--client-uid',type=int,default=-1)
    p.add_argument('--timeout',type=float,default=3600)
    p.add_argument('--report',type=Path,default=Path('/run/trainos-v107/watchdog.json'))
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args(argv)
    if a.probe:
        result=probe_environment(a.delegated_root)
        try:verify_os_manager();result['manager_verified']=True
        except AdmissionDenied as e:result.update(manager_verified=False,manager_reason=str(e))
        print(json.dumps(result,indent=2));return 0
    if not a.production:
        print('production mode required',file=sys.stderr);return 125
    cmd=a.command[1:] if a.command[:1]==['--'] else a.command
    return run_watchdog(a.delegated_root,a.state_dir,a.service_uid,a.client_uid,a.timeout,a.report,cmd)


if __name__=='__main__':
    raise SystemExit(main())
