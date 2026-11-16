"""Fail-closed, bounded per-file Kernel Runner (compatible with v101/v102).

The default interface remains ``KernelTestRunner.run/_run_test/_run_batch``.
Each pytest subprocess is started in a new POSIX session. A process group
surviving a completed pytest leader is a failure, not a successful test file.
The Linux orphan reaper is intentionally an *optional* external supervisor.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path

from tests.kernel_runner.config import STAGES
from tests.kernel_runner.logger import KernelTestLogger


class KernelTestRunner:
    def __init__(self):
        # Opt-in production mode must never fall back to an uncontained direct
        # library invocation. v105 production admission is not certified;
        # fail closed rather than accept forged environment-only credentials.
        if os.environ.get('TRAINOS_KERNEL_PRODUCTION') == '1':
            raise RuntimeError('TrainOS production Runner admission unavailable: independent OS cgroup authority required')
        self.logger = KernelTestLogger()
        self.failed = []
        self.timeout_seconds = float(os.environ.get('TRAINOS_KERNEL_FILE_TIMEOUT', '120'))
        self.grace_seconds = float(os.environ.get('TRAINOS_KERNEL_KILL_GRACE', '2'))
        raw_workers = os.environ.get('TRAINOS_KERNEL_WORKERS', '1')
        try:
            self.workers = int(raw_workers)
        except ValueError as exc:
            raise ValueError('Invalid Kernel Runner worker configuration') from exc
        if not 1 <= self.workers <= 16:
            raise ValueError('Invalid Kernel Runner worker configuration')
        if not (0 < self.timeout_seconds <= 86400 and 0 <= self.grace_seconds <= 60):
            raise ValueError('Invalid bounded runner timeout configuration')

    def run(self):
        self.logger.log('BOOTING TRAINOS TEST KERNEL')
        for stage in STAGES:
            self.logger.stage(stage.name)
            if os.environ.get('TRAINOS_KERNEL_BATCH') == '1':
                files = [file for target in stage.tests for file in self._expand(target)]
                if files:
                    self.logger.log(f'RUN BATCH: {stage.name} ({len(files)} files)')
                    if self._run_batch(files) != 0:
                        self.failed.extend(files)
                        self.logger.log(f'FAIL: {stage.name}')
                        self.logger.log('KERNEL HALTED DUE TO FAILURE')
                        return 1
            else:
                files = [file for target in stage.tests for file in self._expand(target)]
                if self.workers == 1:
                    # Strictly preserve the legacy default's ordered fail-fast
                    # per-file subprocess contract.
                    for test_file in files:
                        if self._run_test(test_file) != 0:
                            self.failed.append(test_file)
                            self.logger.log(f'FAIL: {test_file}')
                            self.logger.log('KERNEL HALTED DUE TO FAILURE')
                            return 1
                else:
                    # Opt-in throughput mode: each file still gets an isolated
                    # pytest process. A barrier retains functional stage order.
                    # All submitted files finish before a failing stage halts.
                    self.logger.log(f'PER-FILE WORKERS: {self.workers}')
                    with ThreadPoolExecutor(max_workers=self.workers) as pool:
                        codes = list(pool.map(self._run_test, files))
                    for test_file, code in zip(files, codes):
                        if code != 0:
                            self.failed.append(test_file)
                            self.logger.log(f'FAIL: {test_file} (exit={code})')
                    if self.failed:
                        self.logger.log('KERNEL HALTED DUE TO FAILURE')
                        return 1
        self.logger.log('ALL CONFIGURED STAGES PASSED')
        return 0

    def _expand(self, target):
        if os.path.isdir(target):
            return sorted(str(p) for p in Path(target).rglob('test_*.py'))
        return [target]

    def _run_batch(self, test_files):
        return self._execute([sys.executable, '-m', 'pytest', '-q', *test_files])

    def _run_test(self, test_file):
        self.logger.log(f'RUN: {test_file}')
        return self._execute([sys.executable, '-m', 'pytest', test_file, '-q'])

    @staticmethod
    def _group_alive(pgid):
        if os.name != 'posix':
            return False
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Cannot prove absence: reject success.
            return True

    @staticmethod
    def _signal_group(pgid, signum):
        try:
            os.killpg(pgid, signum)
        except ProcessLookupError:
            pass

    def _execute(self, argv):
        # Temporary files bound RAM usage; no unbounded PIPE.communicate buffers.
        with tempfile.TemporaryFile(mode='w+b') as stdout, tempfile.TemporaryFile(mode='w+b') as stderr:
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr,
                                       start_new_session=(os.name == 'posix'))
            timed_out = False
            residual = False
            old_term = None
            handler_installed = False

            def interrupt_term(signum, frame):
                raise SystemExit(128 + signum)

            try:
                # SIGKILL cannot be caught. SIGTERM cleanup is supported only
                # in the main Python thread; an external supervisor must cover
                # leader SIGKILL and container PID-1 orphan-reaping behavior.
                if threading.current_thread() is threading.main_thread():
                    old_term = signal.getsignal(signal.SIGTERM)
                    signal.signal(signal.SIGTERM, interrupt_term)
                    handler_installed = True
                try:
                    process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self.logger.log(f'TIMEOUT: pid={process.pid} limit={self.timeout_seconds}s')
                finally:
                    # Always reap descendants, including when leader exited
                    # *before* timeout, on SIGTERM, or by a direct SIGKILL.
                    residual = self._group_alive(process.pid)
                    self._terminate_tree(process)
            finally:
                if handler_installed:
                    signal.signal(signal.SIGTERM, old_term)
                for handle, stream in ((stdout, sys.stdout), (stderr, sys.stderr)):
                    handle.seek(0)
                    while True:
                        chunk = handle.read(65536)
                        if not chunk:
                            break
                        stream.write(chunk.decode('utf-8', errors='replace'))
                    stream.flush()
            if timed_out:
                return 124
            if residual:
                self.logger.log(f'RESIDUAL GROUP: pgid={process.pid}; fail-closed')
                return 125
            return process.returncode if process.returncode is not None else 125

    def _terminate_tree(self, process):
        # Do NOT return early when the leader has already exited: other members
        # can still hold the original PGID and must be terminated.
        if os.name == 'posix':
            self._signal_group(process.pid, signal.SIGTERM)
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=self.grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        if os.name == 'posix':
            self._signal_group(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
        process.wait()
