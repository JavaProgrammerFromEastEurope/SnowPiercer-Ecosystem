"""TrainOS v106: independent Linux cgroup-v2 lifecycle authority (experimental).

The authority is OUTSIDE the runner's cgroup and is the parent of its supervisor.
Before exec, a gate blocks the child while the authority moves it into a fresh,
private cgroup. Descendants inherit membership across setsid/double-fork. If
supervisor exits or dies, the independent authority writes cgroup.kill and waits
for cgroup.events populated=0 before reporting cleanup.

This is NOT an authenticated client broker or a certified deployment. Production
requires a real independently provisioned writable cgroup v2, a root-owned
protected delegated subtree, segregated service/client UIDs and an OS manager
that restarts/monitors the authority. Never emulate cgroupfs for production.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import pwd
from pathlib import Path
import secrets
import signal
import stat
import sys
import time

CGROUP2_SUPER_MAGIC = 0x63677270


class AdmissionDenied(RuntimeError):
    """No child may execute when the containment preconditions are not met."""


class _StatFS(ctypes.Structure):
    # First field is sufficient; statfs writes more bytes, hence large buffer.
    _fields_ = [('f_type', ctypes.c_long), ('_rest', ctypes.c_byte * 248)]


def _filesystem_magic(path: Path) -> int:
    lib = ctypes.CDLL(None, use_errno=True)
    buff = _StatFS()
    result = lib.statfs(os.fsencode(path), ctypes.byref(buff))
    if result != 0:
        raise OSError(ctypes.get_errno(), 'statfs failed', str(path))
    return buff.f_type


def _cgroup_state(path: Path) -> dict[str, str]:
    return dict(line.split(None, 1) for line in (path / 'cgroup.events').read_text().splitlines() if ' ' in line)


def probe_environment(delegated_root: Path) -> dict:
    """Non-destructive host inspection. A positive probe is NOT certification."""
    report = {'schema': 'trainos.cgroup-v2-probe.v106', 'pid1': None,
              'path': str(delegated_root), 'cgroup2_mount': False,
              'parent_writable': False, 'production_admitted': False, 'errors': []}
    try:
        report['pid1'] = Path('/proc/1/comm').read_text().strip()
        report['mount_readonly'] = 'ro' in next((s.split(' - ')[0].split()[5].split(',')
               for s in Path('/proc/self/mountinfo').read_text().splitlines()
               if len(s.split()) > 4 and s.split()[4] == '/sys/fs/cgroup'), [])
    except (OSError, StopIteration, IndexError):
        report['errors'].append('mountinfo or pid1 unavailable')
    try:
        report['cgroup2_mount'] = _filesystem_magic(Path('/sys/fs/cgroup')) == CGROUP2_SUPER_MAGIC
        report['parent_writable'] = os.access(delegated_root, os.W_OK)
        if not report['cgroup2_mount']:
            report['errors'].append('not cgroup2 filesystem')
        if not delegated_root.is_dir():
            report['errors'].append('delegated subtree missing')
        if not report['parent_writable']:
            report['errors'].append('delegated subtree not writable')
    except OSError as exc:
        report['errors'].append(f'{type(exc).__name__}: {exc}')
    return report


def require_admission(delegated_root: Path, service_uid: int, client_uid: int) -> None:
    """Validate BEFORE forking. No env-based credentials or fake cgroup roots."""
    if sys.platform != 'linux' or not Path('/proc/self/cgroup').exists():
        raise AdmissionDenied('Linux cgroup v2 and /proc are mandatory')
    if os.geteuid() != 0:
        raise AdmissionDenied('authority must run as privileged OS service')
    if service_uid <= 0 or client_uid <= 0 or service_uid == client_uid:
        raise AdmissionDenied('distinct non-root service and client UIDs required')
    if not delegated_root.is_absolute() or delegated_root.is_symlink() or not delegated_root.is_dir():
        raise AdmissionDenied('delegated cgroup root must be an existing absolute non-symlink directory')
    try:
        path = delegated_root.resolve(strict=True)
        mount = Path('/sys/fs/cgroup').resolve(strict=True)
        if not path.is_relative_to(mount) or path == mount:
            raise AdmissionDenied('a dedicated cgroup v2 subtree is required')
        if _filesystem_magic(path) != CGROUP2_SUPER_MAGIC:
            raise AdmissionDenied('not on the kernel cgroup2 filesystem')
        info = path.stat()
        if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise AdmissionDenied('delegated subtree must be root-owned and deny other writes')
        if not os.access(path, os.W_OK):
            raise AdmissionDenied('no writable delegated subtree')
        # Do not trust access(): a read-only mount may still report access for root.
        probe = path / ('trainos-preflight-' + secrets.token_hex(12))
        probe.mkdir(mode=0o700)
        try:
            if not (probe / 'cgroup.kill').is_file() or not (probe / 'cgroup.procs').is_file():
                raise AdmissionDenied('required kernel cgroup.kill/procs controls unavailable')
        finally:
            probe.rmdir()
    except (OSError, ValueError) as exc:
        raise AdmissionDenied(f'cgroup preflight failed: {type(exc).__name__}: {exc}') from exc


def _write_control(path: Path, value: str) -> None:
    # No buffered append or filesystem emulation: the kernel cgroup pseudo-file.
    with path.open('w', encoding='ascii') as stream:
        stream.write(value)
        stream.flush()


def _spawn_gated(command: list[str], group: Path, uid: int) -> tuple[int, int]:
    """Fork a blocked child, attach it to the cgroup, THEN release exec."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(write_fd)
            os.setsid()
            if os.read(read_fd, 1) != b'1':
                os._exit(126)
            os.close(read_fd)
            os.setgroups([])
            os.setgid(pwd.getpwuid(uid).pw_gid)
            os.setuid(uid)
            os.execvpe(command[0], command, os.environ.copy())
        except BaseException:
            os._exit(126)
    os.close(read_fd)
    pidfd = None
    try:
        pidfd = os.pidfd_open(pid)
        _write_control(group / 'cgroup.procs', str(pid))
        members = (group / 'cgroup.procs').read_text().split()
        if str(pid) not in members:
            raise AdmissionDenied('child not confirmed inside cgroup before exec')
        os.write(write_fd, b'1')
        return pid, pidfd
    except BaseException:
        # Blocked child cannot exec without the gate byte.
        os.close(write_fd)
        if pidfd is not None:
            try:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL, None, 0)
            finally:
                os.close(pidfd)
        os.waitpid(pid, 0)
        raise
    finally:
        try: os.close(write_fd)
        except OSError: pass


def _kill_and_verify(group: Path, timeout: float = 5.0) -> bool:
    """Use kernel cgroup.kill (not PID/PGID enumeration) and verify empty."""
    _write_control(group / 'cgroup.kill', '1')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _cgroup_state(group).get('populated') == '0':
            return True
        time.sleep(0.025)
    return _cgroup_state(group).get('populated') == '0'


def run_authority(command: list[str], delegated_root: Path, service_uid: int,
                  client_uid: int, timeout: float, report_path: Path | None = None) -> int:
    """Parent authority outlives its supervised child and owns kill lifecycle."""
    report = {'schema': 'trainos.cgroup-lifecycle-authority.v106', 'command': command,
              'production_admitted': False, 'cleanup_verified': False, 'status': 'BLOCKED',
              'events': [], 'authority_pid': os.getpid()}
    group = None
    child_pid = None
    pidfd = None
    rc = 125
    began = time.monotonic()
    signalled = []
    timed_out = False
    def on_term(signum, _frame):
        signalled.append(int(signum))
    old = {}
    try:
        if not command or timeout <= 0 or timeout > 86400:
            raise AdmissionDenied('invalid command or timeout')
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise AdmissionDenied('kernel pidfd identity required')
        require_admission(delegated_root, service_uid, client_uid)
        # The authority itself remains in the parent cgroup.
        group = delegated_root / ('trainos-run-' + secrets.token_hex(16))
        group.mkdir(mode=0o700)
        for sig in (signal.SIGTERM, signal.SIGINT):
            old[sig] = signal.signal(sig, on_term)
        child_pid, pidfd = _spawn_gated(command, group, service_uid)
        report['production_admitted'] = True
        report['runner_pid'] = child_pid
        report['events'].append({'event': 'cgroup_attached_before_exec', 'pid': child_pid})
        child_status = None
        while True:
            waited, status = os.waitpid(child_pid, os.WNOHANG)
            if waited:
                child_status = os.waitstatus_to_exitcode(status)
                break
            if signalled or time.monotonic() - began >= timeout:
                timed_out = not bool(signalled)
                report['events'].append({'event': 'authority_termination',
                                         'signals': signalled, 'timeout': timed_out})
                break
            time.sleep(0.025)
        # Mandatory cgroup.kill after supervisor exit OR its SIGKILL, regardless
        # of detached grandchildren. Never assume clean exit means empty group.
        report['cleanup_verified'] = _kill_and_verify(group)
        if child_status is None:
            waited, status = os.waitpid(child_pid, 0)
            child_status = os.waitstatus_to_exitcode(status)
        report['supervisor_exitcode'] = child_status
        rc = (125 if not report['cleanup_verified'] else
              143 if signalled else 124 if timed_out else
              128-child_status if child_status < 0 else child_status)
        report['status'] = 'PASS' if rc == 0 and report['cleanup_verified'] else 'FAIL'
    except (AdmissionDenied, OSError, ValueError) as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        rc = 125
    finally:
        if group is not None:
            try:
                if not report['cleanup_verified']:
                    report['cleanup_verified'] = _kill_and_verify(group)
                if report['cleanup_verified']:
                    group.rmdir()
            except OSError as exc:
                report['cleanup_error'] = f'{type(exc).__name__}: {exc}'
                rc = 125
        if pidfd is not None:
            os.close(pidfd)
        for sig, handler in old.items():
            signal.signal(sig, handler)
        report['authority_exitcode'] = rc
        report['duration_seconds'] = round(time.monotonic()-began, 4)
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2) + '\n')
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--delegated-root', type=Path, default=Path('/sys/fs/cgroup/trainos-authority'))
    parser.add_argument('--service-uid', type=int, default=-1)
    parser.add_argument('--client-uid', type=int, default=-1)
    parser.add_argument('--timeout', type=float, default=7200)
    parser.add_argument('--report', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe_environment(args.delegated_root), indent=2))
        return 0
    if not args.production:
        print('FAIL-CLOSED: --production and external authority configuration required', file=sys.stderr)
        return 125
    cmd = args.command[1:] if args.command[:1] == ['--'] else args.command
    # The authority is intended to launch the trusted supervisor executable.
    # Not a generic privileged command executor.
    expected = [sys.executable, '-m', 'scripts.ci.process_supervisor_v105']
    if cmd[:3] != expected:
        print('FAIL-CLOSED: only the trusted v105 supervisor module may be launched', file=sys.stderr)
        return 125
    return run_authority(cmd, args.delegated_root, args.service_uid,
                         args.client_uid, args.timeout, args.report)


if __name__ == '__main__':
    raise SystemExit(main())
