"""Run a command with Linux orphan reaping in containers whose PID 1 is not an init.

This changes process supervision only. Tests, warning policy and assertions remain
unchanged. Only children adopted by this process are reaped.
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        raise SystemExit("Usage: python run_with_subreaper.py -- COMMAND [ARGS...]")
    if sys.platform != "linux":
        return subprocess.call(args)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")
    child = subprocess.Popen(args, start_new_session=True)
    def reap_adopted() -> list[int]:
        while True:
            try:
                info = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                return []
            if info is None or info.si_pid == child.pid:
                return []
            os.waitpid(info.si_pid, 0)

    def forward(signum: int, _frame: object) -> None:
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, forward)
    while child.poll() is None:
        reap_adopted()
        time.sleep(0.01)
    reap_adopted()
    return child.returncode if child.returncode >= 0 else 128 - child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
