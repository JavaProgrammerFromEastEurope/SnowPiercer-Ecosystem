"""Build deterministic cumulative TrainOS v103 archive and verify SHA-256.

No optimistic acceptance flags are emitted; verification outcomes are taken
only from completed JSON artifacts in AUDIT/evidence_v103/.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'AUDIT' / 'evidence_v103'
ARCHIVE = Path(os.environ.get('TRAINOS_V103_OUTPUT', ROOT.parent.parent / 'TrainOS-v103-source.zip'))
PREDECESSOR = Path(os.environ.get('TRAINOS_V102_SOURCE', ROOT.parent.parent / 'TrainOS-v102-source.zip'))
MANIFEST = EV / 'SHA256_MANIFEST_V103.json'
SUMMARY = EV / 'VERIFICATION_SUMMARY.json'
SHA = hashlib.sha256


def get_report(case, iteration):
    path = EV / f'{case}_{iteration}.json'
    return json.loads(path.read_text()) if path.is_file() else {'case':case, 'iteration':iteration,'status':'NOT_EXECUTED'}


def summarize():
    from tests.kernel_runner.config import STAGES
    v101 = json.loads((EV/'BASELINE_INTEGRITY.json').read_text())
    cases = {case: [get_report(case, i) for i in iterations]
             for case, iterations in {
                 'combined': list(range(1,9)),
                 'strict_full': [2,3,4,5],
                 'selector': [2,3],
                 'kernel_default': [1,2],
                 'kernel_workers': [1],
                 'kernel_batch': [1],
             }.items()}
    for report_list in cases.values():
        for record in report_list:
            stdout = record.get('stdout')
            if not stdout:
                continue
            p = EV / Path(stdout).name
            if not p.exists():
                continue
            s = p.read_text(encoding='utf-8',errors='replace')
            m = re.search(r'(\d+) passed(?:, (\d+) failed)?',s)
            if m:
                record['pytest_passed_count'] = int(m.group(1))
                record['pytest_failed_count'] = int(m.group(2) or 0)
    strict_3 = [get_report('strict_full', n) for n in (3,4,5)]
    joint_3 = [get_report('combined', n) for n in (6,7,8)]
    workspace = {
        'schema':'trainos.v103.verification-summary.v1',
        'release':'v103',
        'decision':'BLOCKED/NO-GO',
        'source_integrity':v101,
        'functional_domains':[{'name':x.name,'file_count':len(x.tests)} for x in STAGES],
        'functional_domain_count':len(STAGES),
        'configured_test_file_count':sum(len(x.tests) for x in STAGES),
        'runs':cases,
        'three_complete_strict_full_pass':all(x.get('status')=='PASS' for x in strict_3),
        'three_complete_strict_joint_pass':all(x.get('status')=='PASS' for x in joint_3),
        'standard_serial_kernel_completed':any(x.get('status')=='PASS' for x in cases['kernel_default']),
        'worker_mode_per_file_completed':any(x.get('status')=='PASS' for x in cases['kernel_workers']),
        'batch_mode_completed':any(x.get('status')=='PASS' for x in cases['kernel_batch']),
        'sigkill_runner_counterexample':json.loads((EV/'runner_sigkill_boundary.json').read_text()),
        'notes':['Archived v101 Codex logs are external/historical, not a v103 test.',
                 'All initial failed/aborted evidence is intentionally retained.',
                 'Worker mode is opt-in and is not a default-serial completion.',
                 'No independent production cross-UID/cgroup/SIGKILL end-to-end evidence.'],
        'blocking_reasons':['SIGKILL runner leaves a live child without independent forced containment',
                            'Default strictly serial Kernel Runner completion not confirmed unless explicitly reported PASS',
                            'No production PID1/cgroup or cross-UID isolation evidence',
                            'SnowPiercer physical integration not verified'],
    }
    SUMMARY.write_text(json.dumps(workspace,indent=2,ensure_ascii=False)+'\n')
    lines = ['# TrainOS v103 — final release assessment', '',
             '**Decision: BLOCKED / NO-GO.**', '',
             '| Acceptance check | Result |', '|---|---|',
             f'| 24 domain registry | {len(STAGES)} domains, {workspace["configured_test_file_count"]} test files |',
             f'| Three complete strict full regressions | {"PASS" if workspace["three_complete_strict_full_pass"] else "NOT PROVEN"} |',
             f'| Three final strict joint regressions | {"PASS" if workspace["three_complete_strict_joint_pass"] else "NOT PROVEN"} |',
             f'| Default strictly serial Kernel Runner | {"PASS" if workspace["standard_serial_kernel_completed"] else "NOT COMPLETED"} |',
             f'| Opt-in 4-worker per-file Kernel Runner | {"PASS" if workspace["worker_mode_per_file_completed"] else "NOT PROVEN"} |',
             f'| Opt-in batch Kernel Runner | {"PASS" if workspace["batch_mode_completed"] else "NOT PROVEN"} |',
             '| Automatic cleanup after SIGKILL of Runner | **FAIL: counterexample confirmed** |',
             '', '## Exact completed runs', '']
    for group, reports in cases.items():
        for x in reports:
            if x.get('status') == 'NOT_EXECUTED':
                continue
            lines.append(f'- `{group}_{x["iteration"]}`: {x["status"]}, exit={x.get("exitcode")}, duration={x.get("duration_seconds")} s')
    lines += ['', 'Failed or interrupted runs are preserved, not silently discarded.',
              'Source integrity and checksums: BASELINE_INTEGRITY.json and SHA256_MANIFEST_V103.json.',
              'See SAFETY_CASE_V103.md and FAILURE_TRIAGE_V103.md for limitations and root causes.', '']
    (EV / 'RELEASE_ASSESSMENT_V103.md').write_text('\n'.join(lines),encoding='utf-8')
    return workspace


def eligible(path):
    rel=path.relative_to(ROOT)
    if any(s in {'__pycache__','.pytest_cache','.git','.mypy_cache','.ruff_cache'} for s in rel.parts):
        return False
    if path.suffix in {'.pyc','.pyo'}:
        return False
    return path.is_file() and path != MANIFEST


def build():
    EV.mkdir(exist_ok=True,parents=True)
    summary=summarize()
    files=sorted((p for p in ROOT.rglob('*') if eligible(p)),key=lambda p:p.relative_to(ROOT).as_posix())
    manifest={p.relative_to(ROOT).as_posix():SHA(p.read_bytes()).hexdigest() for p in files}
    with ZipFile(PREDECESSOR) as predecessor:
        v102_files = json.loads(predecessor.read('trainos/AUDIT/evidence_v102/SHA256_MANIFEST.json'))['files']
    omitted = set(v102_files) - set(manifest)
    if omitted:
        raise RuntimeError(f'Cumulative compatibility violation: missing v102 files: {sorted(omitted)[:20]}')
    MANIFEST.write_text(json.dumps({'schema':'trainos.v103.sha256.v1',
                                    'base':'TrainOS-v102-source.zip',
                                    'algorithm':'SHA-256',
                                    'excluded':['AUDIT/evidence_v103/SHA256_MANIFEST_V103.json'],
                                    'files':manifest}, indent=2,sort_keys=True)+'\n')
    ARCHIVE.parent.mkdir(exist_ok=True,parents=True)
    with ZipFile(ARCHIVE,'w',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for f in files + [MANIFEST]:
            rel=f.relative_to(ROOT).as_posix()
            info=ZipInfo('trainos/'+rel,date_time=(1980,1,1,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=((0o100755 if os.access(f,os.X_OK) else 0o100644) << 16)
            with f.open('rb') as fin, z.open(info, 'w', force_zip64=True) as fout:
                shutil.copyfileobj(fin,fout,65536)
    with ZipFile(ARCHIVE,'r') as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP CRC verification failed')
        listed=json.loads(z.read('trainos/'+MANIFEST.relative_to(ROOT).as_posix()))['files']
        actual=set(z.namelist())
        expected={'trainos/'+s for s in listed} | {'trainos/'+MANIFEST.relative_to(ROOT).as_posix()}
        if actual!=expected:
            raise RuntimeError(f'ZIP member mismatch missing={expected-actual}, extra={actual-expected}')
        for rel,digest in listed.items():
            if SHA(z.read('trainos/'+rel)).hexdigest()!=digest:
                raise RuntimeError(f'SHA-256 mismatch: {rel}')
        restored_modes = json.loads((EV / 'MODE_RESTORATION_V103.json').read_text())
        for entry in restored_modes['executables']:
            archive_mode = (z.getinfo('trainos/' + entry['path']).external_attr >> 16) & 0o777
            if archive_mode != 0o755:
                raise RuntimeError(f'Executable permission lost: {entry["path"]} = {archive_mode:o}')
    package_sha=SHA(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix('.sha256').write_text(f'{package_sha}  {ARCHIVE.name}\n')
    print(json.dumps({'path':str(ARCHIVE),'size':ARCHIVE.stat().st_size,
                      'sha256':package_sha,'manifest_entries':len(manifest),
                      'zip_files':len(manifest)+1,
                      'three_full_pass':summary['three_complete_strict_full_pass'],
                      'three_joint_pass':summary['three_complete_strict_joint_pass'],
                      'status':summary['decision']},indent=2))


if __name__=='__main__':
    build()
