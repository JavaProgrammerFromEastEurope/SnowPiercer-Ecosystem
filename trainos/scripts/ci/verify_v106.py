"""Per-run, strict, bounded, non-overwriting TrainOS v106 verification evidence."""
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
EVIDENCE = ROOT / 'AUDIT' / 'evidence_v106'
WARN = 'error::ResourceWarning,error::DeprecationWarning'
STRICT = ['-W', 'error::ResourceWarning', '-W', 'error::DeprecationWarning',
          '-W', 'error::pytest.PytestUnraisableExceptionWarning']
SOURCE_FILES = ['tests/kernel_runner/runner.py',
                'scripts/ci/cgroup_authority_v106.py',
                'scripts/ci/verify_v106.py',
                'kernel/economy/ledger_contract/store.py',
                'tests/domains/ci_release/test_cgroup_authority_v106.py',
                'tests/ledger_contract/test_financial_ledger_v105.py']


def run_case(case: str, iteration: int, timeout_seconds: float) -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    name = f'{case}_{iteration}'
    paths = {kind: EVIDENCE / f'{name}.{kind}' for kind in ('json', 'stdout.log', 'stderr.log', 'exitcode')}
    # Never overwrite a verification attempt; evidence must remain independently attributable.
    if any(p.exists() for p in paths.values()):
        raise FileExistsError(f'Attempt {name} already exists; use a new iteration')
    pytest = [sys.executable, '-m', 'pytest', '-q', *STRICT]
    if case == 'combined':
        cmd = pytest + ['tests/domains/recovery', 'tests/domains/ci_release', 'tests/domains/pytest_diagnostics']
    elif case == 'strict_full':
        cmd = pytest + ['tests']
    elif case == 'focused':
        cmd = pytest + ['tests/domains/ci_release/test_cgroup_authority_v106.py',
                        'tests/ledger_contract/test_financial_ledger_v105.py',
                        'tests/domains/ci_release/test_kernel_runner_v103.py',
                        'tests/domains/ci_release/test_kernel_runner_workers_v103.py']
    elif case in ('kernel_default','kernel_workers','kernel_batch'):
        cmd = [sys.executable, '-m', 'tests.kernel_runner']
    else:
        raise ValueError(f'Unknown case: {case}')
    if case.startswith('kernel_'):
        outer = [sys.executable, '-m', 'scripts.ci.process_supervisor_v105',
                 '--report', str(EVIDENCE / f'{name}.supervisor.json'),
                 '--timeout', str(timeout_seconds - 30), '--', *cmd]
    else:
        outer = [sys.executable, str(ROOT / 'scripts' / 'ci' / 'run_with_subreaper.py'), '--', *cmd]
    env = dict(os.environ, PYTHONWARNINGS=WARN, PYTHONUNBUFFERED='1',
               PYTEST_ADDOPTS=f'-c {ROOT / "pytest.ini"}')
    env.pop('TRAINOS_KERNEL_BATCH', None)
    env.pop('TRAINOS_KERNEL_WORKERS', None)
    if case == 'kernel_workers': env['TRAINOS_KERNEL_WORKERS'] = '4'
    if case == 'kernel_batch': env['TRAINOS_KERNEL_BATCH'] = '1'
    began = time.monotonic()
    started_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    timed_out = False
    actions = []
    error = None
    rc = None
    with paths['stdout.log'].open('wb') as stdout, paths['stderr.log'].open('wb') as stderr:
        proc = None
        try:
            proc = subprocess.Popen(outer, stdout=stdout, stderr=stderr,
                                    cwd=ROOT, env=env, start_new_session=True)
            try:
                rc = proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                actions.append('harness_timeout')
                os.kill(proc.pid, signal.SIGTERM)
                try:
                    rc = proc.wait(timeout=10)
                    actions.append('supervisor_term_returned')
                except subprocess.TimeoutExpired:
                    actions.append('supervisor_sigkill_emergency_no_containment_guarantee')
                    os.kill(proc.pid, signal.SIGKILL)
                    rc = proc.wait(timeout=5)
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            actions.append('harness_exception')
            if proc is not None and proc.poll() is None:
                os.kill(proc.pid, signal.SIGTERM)
                try: rc = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.kill(proc.pid, signal.SIGKILL)
                    rc = proc.wait(timeout=5)
    exitcode = 124 if timed_out else rc if rc is not None else 125
    paths['exitcode'].write_text(f'{exitcode}\n')
    report = {
        'schema': 'trainos.verification.v106', 'case':case, 'iteration':iteration,
        'started_at':started_at, 'duration_seconds':round(time.monotonic() - began,3),
        'timeout_seconds':timeout_seconds, 'command':outer, 'cwd':str(ROOT),
        'python':sys.version, 'platform':platform.platform(),
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                         for name in SOURCE_FILES},
        'warnings':WARN, 'pytest_addopts':env['PYTEST_ADDOPTS'],
        'pytest_explicit_warning_filters':STRICT if 'pytest' in cmd else None,
        'supervisor':case.startswith('kernel_'),
        'kernel_workers':env.get('TRAINOS_KERNEL_WORKERS', '1'),
        'kernel_batch':env.get('TRAINOS_KERNEL_BATCH') == '1',
        'exitcode':rc, 'timed_out':timed_out, 'actions':actions, 'error':error,
        'stdout':paths['stdout.log'].name, 'stderr':paths['stderr.log'].name,
        'status':'PASS' if rc == 0 and not timed_out and not error else 'FAIL',
    }
    paths['json'].write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return exitcode


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', required=True, choices=('combined','strict_full','focused','kernel_default','kernel_workers','kernel_batch'))
    p.add_argument('--iteration',type=int,default=1)
    p.add_argument('--timeout',type=float,default=900.0)
    args = p.parse_args()
    return run_case(args.case,args.iteration,args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
