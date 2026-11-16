"""Bounded, order-preserving ddmin for reproducible pytest failures.

A candidate reproduces only with exit code 1 and a matching failure signature.
Timeouts, collection errors, and runner errors are inconclusive. Each probe has
its own POSIX process group and is killed/reaped on timeout.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

STRICT = ['-W', 'error::ResourceWarning', '-W', 'error::DeprecationWarning',
          '-W', 'error::pytest.PytestUnraisableExceptionWarning']

def minimize(nodes, probe):
    nodes = list(nodes)
    granularity = 2
    while len(nodes) >= 2:
        size = math.ceil(len(nodes) / granularity)
        reduced = False
        for start in range(0, len(nodes), size):
            candidate = nodes[:start] + nodes[start + size:]
            if candidate and probe(candidate):
                nodes = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if not reduced:
            if granularity >= len(nodes):
                break
            granularity = min(len(nodes), granularity * 2)
    return nodes

def run_probe(command, timeout):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=(os.name == 'posix'))
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        try:
            out, err = proc.communicate(timeout=1.0)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            out, err = proc.communicate(timeout=2.0)
    return proc.returncode, out.decode(errors='replace'), err.decode(errors='replace'), timed_out

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nodes', type=Path, required=True)
    p.add_argument('--match', required=True)
    p.add_argument('--pytest-arg', action='append', default=[], help='Additional pytest option, e.g. --pytest-arg=-p')
    p.add_argument('--timeout', type=float, default=90)
    p.add_argument('--max-probes', type=int, default=100)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args(argv)
    if a.timeout <= 0 or a.max_probes < 1:
        p.error('positive timeout and max-probes required')
    nodes = [s.strip() for s in a.nodes.read_text().splitlines() if s.strip() and not s.startswith('#')]
    a.report.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    def probe(candidate):
        if len(attempts) >= a.max_probes:
            return False
        command = [sys.executable, '-m', 'pytest', '-q', *STRICT, *a.pytest_arg, *candidate]
        started = time.monotonic()
        try:
            rc, out, err, timed_out = run_probe(command, a.timeout)
            status = ('timeout_inconclusive' if timed_out else 'reproduced' if
                      rc == 1 and a.match in out + err else 'not_reproduced')
        except Exception as exc:
            rc, out, err, status = None, '', repr(exc), 'runner_error'
        idx = len(attempts)
        (a.report.parent / f'{a.report.stem}.probe{idx:03d}.stdout.log').write_text(out)
        (a.report.parent / f'{a.report.stem}.probe{idx:03d}.stderr.log').write_text(err)
        attempts.append({'nodes': candidate, 'status': status, 'returncode': rc,
                         'seconds': round(time.monotonic()-started, 3)})
        a.report.write_text(json.dumps({'schema':'trainos.ddmin.v2', 'attempts': attempts}, indent=2))
        return status == 'reproduced'
    reproduced = probe(nodes)
    result = minimize(nodes, probe) if reproduced else None
    a.report.write_text(json.dumps({'schema':'trainos.ddmin.v2', 'initial_reproduced': reproduced,
                                    'minimal_candidate': result, 'attempts': attempts}, indent=2))
    return 0 if reproduced else 2

if __name__ == '__main__':
    raise SystemExit(main())
