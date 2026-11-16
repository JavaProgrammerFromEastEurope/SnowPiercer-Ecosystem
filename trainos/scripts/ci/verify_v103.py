"""Bounded, evidence-producing TrainOS v103 verification harness.

Use via `python -m scripts.ci.verify_v103 --case combined --iteration 1`.
Linux PR_SET_CHILD_SUBREAPER is used for container orphan reaping when available;
this is not a substitute for PID 1 or a production process supervisor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'AUDIT' / 'evidence_v103'
WARN = 'error::ResourceWarning,error::DeprecationWarning'


def run_case(case: str, iteration: int, timeout_seconds: float) -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    prefix = [sys.executable, str(ROOT / 'scripts' / 'ci' / 'run_with_subreaper.py'), '--']
    strict = ['-W', 'error::ResourceWarning', '-W', 'error::DeprecationWarning',
              '-W', 'error::pytest.PytestUnraisableExceptionWarning']
    if case == 'combined':
        target = [sys.executable, '-m', 'pytest', '-q', *strict,
                  'tests/domains/recovery', 'tests/domains/ci_release',
                  'tests/domains/pytest_diagnostics']
    elif case == 'strict_full':
        target = [sys.executable, '-m', 'pytest', '-q', *strict, 'tests']
    elif case in ('kernel_default', 'kernel_batch', 'kernel_workers'):
        target = [sys.executable, '-m', 'tests.kernel_runner']
    elif case == 'selector':
        target = [sys.executable, '-m', 'pytest', '-q', *strict, 'tests/stage83',
                  'tests/stage84', 'tests/stage85']
    else:
        raise ValueError(f'Unknown case: {case}')
    name = f'{case}_{iteration}'
    out = EVIDENCE / (name + '.stdout.log')
    err = EVIDENCE / (name + '.stderr.log')
    report = EVIDENCE / (name + '.json')
    # A subprocess pytest targeting an external tmp_path otherwise misses
    # this project's pytest.ini; pytest-asyncio then emits a deprecation
    # warning. Do not suppress the warning: provide the required config.
    env = dict(os.environ, PYTHONWARNINGS=WARN, PYTHONUNBUFFERED='1',
               PYTEST_ADDOPTS=f'-c {ROOT / "pytest.ini"}')
    env.pop('TRAINOS_KERNEL_BATCH', None)
    env.pop('TRAINOS_KERNEL_WORKERS', None)
    if case == 'kernel_batch':
        env['TRAINOS_KERNEL_BATCH'] = '1'
    if case == 'kernel_workers':
        env['TRAINOS_KERNEL_WORKERS'] = '4'
    started = time.monotonic()
    started_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    rc = None
    timed_out = False
    error = None
    actions = []
    cmd = prefix + target
    proc = None
    with out.open('wb') as o, err.open('wb') as e:
        try:
            proc = subprocess.Popen(cmd, stdout=o, stderr=e, env=env, cwd=ROOT,
                                    start_new_session=(os.name == 'posix'))
            try:
                rc = proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                actions.append('timeout')
                if os.name == 'posix':
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name == 'posix':
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.wait(timeout=5)
                rc = proc.returncode
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            actions.append('harness_exception')
            if proc is not None and proc.poll() is None:
                if os.name == 'posix':
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    proc.kill()
                proc.wait()
            rc = proc.returncode if proc else None
    (EVIDENCE / (name + '.exitcode')).write_text(str(124 if timed_out else rc) + '\n')
    source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                     for path in ('tests/kernel_runner/runner.py',
                                  'tests/domains/ci_release/test_kernel_runner_v103.py',
                                  'tests/domains/ci_release/test_kernel_runner_workers_v103.py')}
    evidence = {
        'schema': 'trainos.verification.v103',
        'case': case, 'iteration': iteration, 'started_at': started_at,
        'source_sha256': source_hashes,
        'duration_seconds': round(time.monotonic() - started, 3),
        'timeout_seconds': timeout_seconds, 'command': cmd,
        'cwd': str(ROOT), 'python': sys.version, 'platform': platform.platform(),
        'strict_warnings': WARN, 'nested_pytest_addopts': env['PYTEST_ADDOPTS'],
        'kernel_workers': env.get('TRAINOS_KERNEL_WORKERS', '1'), 'pytest_warning_filter': strict if 'pytest' in target else None,
        'subreaper': sys.platform == 'linux', 'pid1_comm': Path('/proc/1/comm').read_text().strip() if sys.platform == 'linux' else None,
        'exitcode': rc, 'timed_out': timed_out, 'actions': actions,
        'error': error, 'stdout': out.name, 'stderr': err.name,
        'status': 'PASS' if rc == 0 and not timed_out and not error else 'FAIL',
    }
    report.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return 124 if timed_out else rc if rc is not None else 125


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', required=True, choices=['combined', 'strict_full', 'kernel_default', 'kernel_batch', 'kernel_workers', 'selector'])
    p.add_argument('--iteration', type=int, default=1)
    p.add_argument('--timeout', type=float, default=900.0)
    args = p.parse_args()
    return run_case(args.case, args.iteration, args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
