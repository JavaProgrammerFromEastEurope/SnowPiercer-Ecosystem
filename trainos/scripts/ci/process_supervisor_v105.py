"""External Linux process supervisor for untrusted *accidental* runner failures (v105 pidfd).

The supervisor is intentionally an independent ancestor of the Kernel Runner:
PR_SET_CHILD_SUBREAPER ensures that orphaned descendants, including setsid()
children, are adopted here rather than by an unsuitable container PID 1.

Contract: preserve runner exit codes, emit bounded evidence, terminate adopted
processes on SIGKILL of the runner, fail closed on residual live descendants.
Not a cgroup/namespace or adversarial cross-UID security boundary. A SIGKILL of
*the supervisor* itself cannot be caught; use a separate OS service manager.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

PR_SET_CHILD_SUBREAPER = 36


def _proc_table() -> dict[int, tuple[int, str, int]]:
    """PID -> (PPID, state, start_ticks), using /proc/PID/stat safely."""
    result = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            stat = (entry / 'stat').read_text()
            # The comm (field 2) may contain parentheses and spaces.
            fields = stat[stat.rfind(')') + 2:].split()
            result[int(entry.name)] = (int(fields[1]), fields[0], int(fields[19]))
        except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
            pass
    return result


def _descendants(table: dict[int, tuple[int, str, int]], parents: set[int]) -> set[int]:
    result = set()
    frontier = set(parents)
    while frontier:
        next_frontier = {pid for pid, data in table.items() if data[0] in frontier and pid not in result and pid not in parents}
        result.update(next_frontier)
        frontier = next_frontier
    return result


def _kill_identity(pid: int, start_ticks: int, signum: int) -> bool:
    """Signal the *opened kernel process identity*, never a reused integer PID.

    /proc observation before and AFTER pidfd_open closes the association race.
    pidfd_send_signal addresses the fd identity, not the transient numeric PID.
    If pidfd is unsupported, do not fall back to a racy os.kill(pid).
    """
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        return False
    fd = None
    try:
        fd = os.pidfd_open(pid, 0)
        stat = Path(f'/proc/{pid}/stat').read_text()
        fields = stat[stat.rfind(')') + 2:].split()
        if int(fields[19]) != start_ticks or fields[0] == 'Z':
            return False
        signal.pidfd_send_signal(fd, signum, None, 0)
        return True
    except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError, OSError):
        return False
    finally:
        if fd is not None:
            os.close(fd)


def _reap_adopted(root_pid: int, events: list[dict]) -> None:
    """Reap adopted children without stealing Popen's wait status for root."""
    while True:
        try:
            info = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        except ChildProcessError:
            return
        if info is None or info.si_pid == root_pid:
            return
        try:
            pid, status = os.waitpid(info.si_pid, os.WNOHANG)
        except ChildProcessError:
            continue
        if pid:
            events.append({'event': 'reaped_adopted', 'pid': pid, 'wait_status': status})


def _enable_subreaper() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER failed')


def supervise(command: list[str], *, report_path: Path | None = None, grace: float = 1.5,
              poll: float = 0.025, timeout: float = 7200.0,
              production: bool = False) -> int:
    if sys.platform != 'linux' or not Path('/proc/self/stat').is_file():
        raise RuntimeError('Unsupported system: Linux /proc and PR_SET_CHILD_SUBREAPER are mandatory')
    if not command or not (0 < poll <= 1 and 0 <= grace <= 60 and 0 < timeout <= 86400):
        raise ValueError('Invalid supervisor command or limits')
    # Development admission uses subreaper + pidfd. Production MUST be blocked
    # unless a separately administered OS authority guarantees cleanup when
    # THIS supervisor is killed. Merely having cgroup v2 mounted is insufficient.
    if production:
        raise RuntimeError('production admission requires independent writable cgroup v2 delegation and external lifecycle authority; not verified')
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Linux pidfd_open + pidfd_send_signal required for v105')
    _enable_subreaper()  # fail closed before admitting runner
    events: list[dict] = []
    root = None
    root_pidfd = None
    exit_reason = None
    observed: dict[int, int] = {}
    began = time.monotonic()
    terminating = False
    first_term = None
    timeout_hit = False
    report = {
        'schema': 'trainos.process-supervisor.v105', 'command': command,
        'supervisor_pid': os.getpid(), 'pid1_comm': Path('/proc/1/comm').read_text().strip(),
        'cgroup_v2': Path('/sys/fs/cgroup/cgroup.controllers').exists(),
        'cgroup_writable': os.access('/sys/fs/cgroup', os.W_OK),
        'subreaper': True, 'pidfd_required': True, 'pidfd_available': True,
        'production_admitted': False, 'events': events, 'status': 'STARTED',
    }

    def on_term(signum: int, _frame: object) -> None:
        nonlocal terminating, first_term
        terminating = True
        if first_term is None:
            first_term = signum
        events.append({'event': 'supervisor_signal', 'signal': signum})

    previous = {sig: signal.signal(sig, on_term) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        root = subprocess.Popen(command, start_new_session=True)
        root_pidfd = os.pidfd_open(root.pid, 0)
        report['runner_pid'] = root.pid
        events.append({'event': 'runner_spawned', 'pid': root.pid})
        # Track both normal ancestry and descendants subsequently reparented
        # directly to this subreaper; PID-starttime guards against PID reuse.
        while True:
            table = _proc_table()
            ancestors = {root.pid, os.getpid()}
            live = _descendants(table, ancestors)
            for pid in live:
                if pid != root.pid:
                    observed[pid] = table[pid][2]
            for pid in list(observed):
                if pid not in table or table[pid][2] != observed[pid]:
                    observed.pop(pid, None)
            _reap_adopted(root.pid, events)
            root_code = root.poll()
            now = time.monotonic()
            if root_code is None and now - began > timeout:
                timeout_hit = True
                terminating = True
                events.append({'event': 'runner_timeout', 'seconds': timeout})
            if root_code is None and terminating:
                events.append({'event': 'runner_terminate', 'signal': signal.SIGTERM})
                try:
                    signal.pidfd_send_signal(root_pidfd, signal.SIGTERM, None, 0)
                    # Group cleanup remains an extra attempt. PIDFD identities
                    # are used for all independently tracked descendants.
                    os.killpg(root.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + grace
                while root.poll() is None and time.monotonic() < deadline:
                    time.sleep(poll)
                if root.poll() is None:
                    try:
                        signal.pidfd_send_signal(root_pidfd, signal.SIGKILL, None, 0)
                        os.killpg(root.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            if root_code is not None or terminating:
                exit_reason = root.poll()
                break
            time.sleep(poll)
        # A successful runner may not silently leak descendants even when
        # supervisor cleanup succeeds: preserve fail-closed classification.
        exit_table = _proc_table()
        live_at_exit = sorted(pid for pid in _descendants(exit_table, {os.getpid(), root.pid})
                              if pid != root.pid and exit_table[pid][1] != "Z")
        report["residual_at_runner_exit"] = live_at_exit
        # Regardless of normal or abnormal runner exit, kill any leftover
        # descendants. In particular, setsid() descendants survive killpg().
        deadline = time.monotonic() + grace
        signals = ((signal.SIGTERM, deadline), (signal.SIGKILL, time.monotonic() + grace + 2))
        for signum, until in signals:
            while True:
                table = _proc_table()
                live_ids = {pid: start for pid, start in observed.items()
                            if pid in table and table[pid][2] == start and table[pid][1] != 'Z'}
                for pid in _descendants(table, {os.getpid()}):
                    if pid != root.pid and table[pid][1] != 'Z':
                        live_ids[pid] = table[pid][2]
                if not live_ids:
                    break
                for pid, start in live_ids.items():
                    if _kill_identity(pid, start, signum):
                        events.append({'event': 'signal_descendant', 'pid': pid, 'signal': int(signum)})
                if time.monotonic() >= until:
                    break
                time.sleep(poll)
            _reap_adopted(root.pid, events)
        root_code = root.wait(timeout=3)
        # Allow short bounded period for kernel reparenting and zombie reaping.
        settle = time.monotonic() + 1
        residual = []
        while True:
            _reap_adopted(root.pid, events)
            table = _proc_table()
            residual = [pid for pid, start in observed.items() if pid in table and table[pid][2] == start and table[pid][1] != 'Z']
            residual.extend(pid for pid in _descendants(table, {os.getpid()}) if pid != root.pid and table[pid][1] != 'Z' and pid not in residual)
            if not residual or time.monotonic() >= settle:
                break
            time.sleep(poll)
        report.update({'runner_exitcode': root_code, 'supervisor_signal': first_term,
                       'timeout': timeout_hit, 'residual_running_pids': residual,
                       'observed_descendant_count': len(observed)})
        if timeout_hit:
            rc = 124
        elif residual or (root_code == 0 and live_at_exit):
            rc = 125
        elif first_term is not None:
            rc = 128 + first_term
        elif root_code < 0:
            rc = 128 - root_code
        else:
            rc = root_code
        report.update({'supervisor_exitcode': rc,
                       'status': 'FAIL' if rc or residual else 'PASS',
                       'cleanup_complete': not residual, 'duration_seconds': round(time.monotonic()-began,3)})
        return rc
    finally:
        if root is not None and root.poll() is None:
            if root_pidfd is not None:
                try:
                    signal.pidfd_send_signal(root_pidfd, signal.SIGKILL, None, 0)
                except ProcessLookupError:
                    pass
            root.kill()
            root.wait()
        if root_pidfd is not None:
            os.close(root_pidfd)
        for sig, old in previous.items():
            signal.signal(sig, old)
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path)
    p.add_argument('--production', action='store_true')
    p.add_argument('--grace', type=float, default=1.5)
    p.add_argument('--poll', type=float, default=0.025)
    p.add_argument('--timeout', type=float, default=7200.0)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    try:
        return supervise(command, report_path=args.report, grace=args.grace,
                         poll=args.poll, timeout=args.timeout, production=args.production)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f'SUPERVISOR FAIL-CLOSED: {exc}', file=sys.stderr)
        return 125


if __name__ == '__main__':
    raise SystemExit(main())
