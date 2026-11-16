"""Generate a factual release assessment from actual completed v106 attempt evidence."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'AUDIT/evidence_v106'
CASES=['strict_full','combined','kernel_default','kernel_workers','kernel_batch']


def generate():
    from tests.kernel_runner.config import STAGES
    from tests.kernel_runner.runner import KernelTestRunner
    runner=KernelTestRunner()
    nfiles=sum(len([p for target in area.tests for p in runner._expand(target)]) for area in STAGES)
    discovered=defaultdict(list)
    for p in E.glob('*.json'):
        try: record=json.loads(p.read_text())
        except (ValueError,OSError):continue
        if record.get('schema')=='trainos.verification.v106':
            discovered[record['case']].append((record['iteration'],record))
    for case in discovered:discovered[case].sort()
    out=['# TrainOS v106 — cumulative release assessment','',
         '**Decision: BLOCKED / NO-GO.** No independent real cgroup v2 containment, cross-UID production boundary, or authority lifetime certificate.','',
         '## Executed verification matrix','',
         '| Mode | Completed attempts | PASS | FAIL | Evidence |',
         '|---|---:|---:|---:|---|']
    for case in CASES:
        arr=discovered[case]
        passes=sum(r['status']=='PASS' for _,r in arr)
        failures=len(arr)-passes
        out.append(f'| {case} | {len(arr)} | {passes} | {failures} | '+', '.join(
            f'#{i}: {r["status"]} exit={r["exitcode"]}' for i,r in arr)+' |')
    out.extend(['','### Full and joint regression completeness','',
                '- Full strict regression requires >= 3 independent successful completed runs; '+
                ('**CONFIRMED**' if sum(r['status']=='PASS' for _,r in discovered['strict_full'])>=3 else '**NOT CONFIRMED**')+'.',
                '- Joint recovery + CI + pytest_diagnostics requires >= 3 successful runs; '+
                ('**CONFIRMED**' if sum(r['status']=='PASS' for _,r in discovered['combined'])>=3 else '**NOT CONFIRMED**')+'.',
                '- Explicit warning negative control produced 2 intentionally failed tests (exit=1); this does not count as a release failure.','',
                '### Kernel Runner mode checks','',
                f'- Registered functional areas: **{len(STAGES)}**. Configured per-file test starts: **{nfiles}**.',
                '- Batch executes a different process-isolation contract from serial/worker; none substitute for another.'])
    for case in ('kernel_default','kernel_workers','kernel_batch'):
        good=False
        for i,record in discovered[case]:
            text=(E/f'{case}_{i}.stdout.log').read_text(errors='replace')
            supervisor_p=E/f'{case}_{i}.supervisor.json'
            sup=json.loads(supervisor_p.read_text()) if supervisor_p.exists() else {}
            starts=len(re.findall(r'\bRUN: tests/',text))
            batches=text.count('RUN BATCH:')
            stages=text.count('[STAGE START]')
            complete=(record['status']=='PASS' and stages==len(STAGES) and
                      (batches==len(STAGES) if case=='kernel_batch' else starts==nfiles) and
                      'ALL CONFIGURED STAGES PASSED' in text and
                      sup.get('cleanup_complete') and not sup.get('residual_running_pids') and
                      sup.get('supervisor_exitcode')==0)
            good=good or bool(complete)
            out.append(f'- {case} #{i}: **{"COMPLETE" if complete else "NOT COMPLETE"}**; '+
                       f'exit={record["exitcode"]}, domains={stages}, per-file starts={starts}, '+
                       f'batches={batches}, supervisor cleanup={sup.get("cleanup_complete")}, '+
                       f'duration={record["duration_seconds"]}s.')
        if not good:
            out.append(f'  **No fully verified {case} execution in this release.**')
    out.extend(['','## v105 source compatibility and archive lineage','',
                '- All v105 archive files retained; final ZIP build enforces zero deletions and verifies every SHA-256 entry.',
                '- Four executable script modes restored after Python ZIP extraction; historical bytes unchanged.',
                '- Failure `strict_full_1` is retained: 1,521 passed and 1 failed due to missing execute mode on run_stage_matrix.sh.',
                '- New v106 authority and probes are additive; `KernelTestRunner` legacy signatures unchanged.','',
                '## Process and production safety boundaries','',
                '- v106 authority provides a fork gate before exec, pidfd identity of its supervised child and a cgroup.kill cleanup protocol.',
                '- Only unit tests of cgroup.kill and fail-closed host admission executed here: host cgroup v2 read-only, no delegated subtree.',
                '- Real SIGKILL supervisor negative control: Runner and double-fork detached child survived; external independent probe cleaned both.',
                '- Runner SIGTERM (143) and SIGKILL (137) probes passed with v105 development supervisor cleanup; SIGTERM supervisor (143) and timeout (124) also passed.',
                '- Actual cross-UID probes under numeric UIDs 65534 and 65533 rejected production; development legacy invocation remains available. This is NOT OS-enforced legacy fencing.',
                '- Concurrent production admission: 16 attempts denied without command execution. This does NOT prove successful admission races.',
                '- pidfd presence/identity is proven for observed direct processes only; independent authority cgroup lifecycle requires real external verification.',
                '- SIGKILL of authority itself and service-manager restart behavior were not proven.',
                '- Physical SnowPiercer integration and safety certification are outside the demonstrated boundary.','',
                '## Decision and next steps','',
                '**BLOCKED/NO-GO** until an independently controlled writable cgroup v2, real supervisor/authority crash testing, peer-authenticated cross-UID production broker, OS-level legacy fencing and physical subsystem safety evidence are available.','',
                'All stdout, stderr, exit codes, JSON outcomes, including failures, are retained under `AUDIT/evidence_v106/`.',''])
    path=E/'RELEASE_ASSESSMENT_V106.md';path.write_text('\n'.join(out))
    print(path)


if __name__=='__main__':generate()
