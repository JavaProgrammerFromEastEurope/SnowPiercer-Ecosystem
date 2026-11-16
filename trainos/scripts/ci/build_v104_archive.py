"""Build and verify cumulative TrainOS v104 from v103 and complete evidence.

Safety states are derived from reports and never coerced to PASS.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'AUDIT' / 'evidence_v104'
BASE = Path(os.environ.get('TRAINOS_V103_SOURCE', ROOT.parent.parent / 'TrainOS-v103-source.zip'))
ARCHIVE = Path(os.environ.get('TRAINOS_V104_OUTPUT', ROOT.parent.parent / 'TrainOS-v104-source.zip'))
MANIFEST = EV / 'SHA256_MANIFEST_V104.json'
SUMMARY = EV / 'VERIFICATION_SUMMARY_V104.json'
SHA = hashlib.sha256


def eligible(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in {'__pycache__', '.pytest_cache', '.git', '.mypy_cache', '.ruff_cache'} for part in rel.parts):
        return False
    return path.is_file() and path.suffix not in {'.pyc', '.pyo'} and path != MANIFEST


def read_report(case: str, iteration: int) -> dict:
    prefix = f'{case}_{iteration}'
    j = EV / f'{prefix}.json'
    code = EV / f'{prefix}.exitcode'
    out = EV / f'{prefix}.stdout.log'
    err = EV / f'{prefix}.stderr.log'
    if not all(p.exists() for p in (j, code, out, err)):
        return {'case':case,'iteration':iteration,'status':'NOT_EXECUTED','complete_artifacts':False}
    obj = json.loads(j.read_text(encoding='utf-8'))
    obj['complete_artifacts'] = True
    obj['source_hashes_match_final'] = all(
        (ROOT / rel).is_file() and SHA((ROOT / rel).read_bytes()).hexdigest() == digest
        for rel, digest in obj.get('source_sha256', {}).items()
    ) and bool(obj.get('source_sha256'))
    if not obj['source_hashes_match_final']:
        obj['status'] = 'FAIL'
        obj['source_mismatch'] = True
    if case.startswith('kernel_'):
        supervisor = EV / f'{prefix}.supervisor.json'
        if supervisor.is_file():
            sup = json.loads(supervisor.read_text())
            obj['supervisor_cleanup_proven'] = (sup.get('cleanup_complete') is True and
               not sup.get('residual_running_pids') and
               sup.get('supervisor_exitcode') == obj.get('exitcode'))
        else:
            obj['supervisor_cleanup_proven'] = False
        if not obj['supervisor_cleanup_proven']:
            obj['status'] = 'FAIL'
    stdout = out.read_text(encoding='utf-8', errors='replace')
    matches = re.findall(r'(\d+) passed(?:, (\d+) failed)?', stdout)
    if matches:
        obj['pytest_passed_count'] = int(matches[-1][0])
        obj['pytest_failed_count'] = int(matches[-1][1] or '0')
    obj['kernel_finished_message'] = 'ALL CONFIGURED STAGES PASSED' in stdout
    obj['kernel_file_start_count'] = len(re.findall(r'\[KERNEL-TEST [^]]+\] RUN: ',stdout))
    obj['kernel_batch_start_count'] = len(re.findall(r'\[KERNEL-TEST [^]]+\] RUN BATCH: ',stdout))
    try:
        obj['recorded_exitcode'] = int(code.read_text().strip())
        if obj['recorded_exitcode'] != obj.get('exitcode'):
            obj['status'] = 'FAIL'
            obj['exitcode_disagreement'] = True
    except ValueError:
        obj['status'] = 'FAIL'
        obj['exitcode_disagreement'] = True
    return obj


def summary() -> dict:
    from tests.kernel_runner.config import STAGES
    entries = {'strict_full':[read_report('strict_full', n) for n in (1,2,3,4,5)],
               'combined':[read_report('combined', n) for n in (1,2,3)],
               'focused':[read_report('focused',n) for n in (1,)],
               'kernel_default':[read_report('kernel_default',n) for n in (1,)],
               'kernel_workers':[read_report('kernel_workers',n) for n in (1,2)],
               'kernel_batch':[read_report('kernel_batch',n) for n in (1,)]}
    strict_full_passes = [x['iteration'] for x in entries['strict_full'] if x.get('status')=='PASS' and x.get('complete_artifacts')]
    strict_joint_passes = [x['iteration'] for x in entries['combined'] if x.get('status')=='PASS' and x.get('complete_artifacts')]
    three_full = len(strict_full_passes) >= 3
    three_joint = len(strict_joint_passes) >= 3
    num_files = sum(len(s.tests) for s in STAGES)
    serial = any(x.get('status')=='PASS' and x.get('kernel_finished_message') and
                 x.get('kernel_file_start_count')==num_files and x.get('supervisor_cleanup_proven')
                 for x in entries['kernel_default'])
    worker = any(x.get('status')=='PASS' and x.get('kernel_finished_message') and
                 x.get('kernel_file_start_count')==num_files and x.get('supervisor_cleanup_proven')
                 for x in entries['kernel_workers'])
    batch = any(x.get('status')=='PASS' and x.get('kernel_finished_message') and
                x.get('kernel_batch_start_count')==len(STAGES) and x.get('supervisor_cleanup_proven')
                for x in entries['kernel_batch'])
    return {
        'schema':'trainos.v104.verification-summary.v1',
        'release':'v104','decision':'BLOCKED/NO-GO',
        'functional_domain_count':len(STAGES), 'configured_test_file_count':num_files,
        'functional_domains':[{'name':x.name,'file_count':len(x.tests)} for x in STAGES],
        'runs':entries,
        'three_complete_strict_full_pass':three_full,
        'completed_strict_full_pass_iterations': strict_full_passes,
        'completed_strict_joint_pass_iterations': strict_joint_passes,
        'three_complete_strict_joint_pass':three_joint,
        'standard_serial_kernel_completed':serial,
        'worker_per_file_completed':worker,
        'batch_mode_completed':batch,
        'independent_supervisor_cleanup_tested': (entries['focused'][0].get('status')=='PASS' and
            all((EV / f'sigkill_fanout_{i}.json').is_file() and
                json.loads((EV / f'sigkill_fanout_{i}.json').read_text()).get('result')=='PASS'
                for i in range(1,6)) and
            json.loads((EV / 'ACTUAL_KERNEL_SIGKILL_V104.json').read_text()).get('status')=='PASS' and
            json.loads((EV / 'TERM_ESCALATION_PROBE_V104.json').read_text()).get('test_status')=='PASS'),
        'mandatory_cgroup_production_containment_verified':False,
        'production_pid1_verified':False,
        'cross_uid_verified':False,
        'physical_snowpiercer_integration_verified':False,
        'blocking_reasons':[
            'No independent production PID1/writable-cgroup containment',
            'Supervisor SIGKILL itself not covered by external enforced lifecycle',
            'PID reuse and /proc TOCTOU not eliminated via pidfds',
            'Cross-UID process-isolation not verified',
            'Legacy direct Kernel Runner entrypoint bypasses external supervisor',
            'SnowPiercer physical integrations not certified',
            'Strict full attempts 3 and 4 exposed intermittent SQLite WAL initialization database locks',
            'Four-worker attempt 1 failed two timing-sensitive CI process cleanup tests',
        ] + ([] if serial else ['Default sequential per-file Kernel Runner not proved complete']),
        'notes':['Earlier v101 Codex 1487 test/24-domain claims are historical external reports, not a v104 execution.',
                 'All evidence is attributable to unique v104 attempts, with source hashes and exit codes.',
                 'Batch/worker successes cannot substitute for the ordered serial per-file contract.'],
    }


def build() -> None:
    EV.mkdir(exist_ok=True,parents=True)
    if not BASE.is_file():
        raise FileNotFoundError(f'v103 predecessor required: {BASE}')
    with ZipFile(BASE) as z:
        if z.testzip() is not None:
            raise RuntimeError('Bad v103 ZIP CRC')
        old_manifest = json.loads(z.read('trainos/AUDIT/evidence_v103/SHA256_MANIFEST_V103.json'))['files']
        for name, digest in old_manifest.items():
            src_bytes = z.read('trainos/'+name)
            if SHA(src_bytes).hexdigest()!=digest:
                raise RuntimeError('Predecessor manifest mismatch: '+name)
            src_file = ROOT / name
            if not src_file.is_file():
                raise RuntimeError('Cumulative deletion of: '+name)
            if src_file.read_bytes()!=src_bytes:
                raise RuntimeError('Cumulative modification of predecessor file: '+name)
        previous_manifest = ROOT / 'AUDIT/evidence_v103/SHA256_MANIFEST_V103.json'
        if previous_manifest.read_bytes()!=z.read('trainos/AUDIT/evidence_v103/SHA256_MANIFEST_V103.json'):
            raise RuntimeError('v103 manifest modified')
    status = summary()
    SUMMARY.write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    changed = 0
    new_files = []
    for p in ROOT.rglob('*'):
        if eligible(p):
            rel=p.relative_to(ROOT).as_posix()
            if rel not in old_manifest:
                new_files.append(rel)
            else:
                changed += 0 if SHA(p.read_bytes()).hexdigest()==old_manifest[rel] else 1
    if changed:
        raise RuntimeError('Unexpected change to old sources')
    provenance = {'schema':'trainos.v104.source-diff.v1',
                  'baseline':'TrainOS-v103-source.zip',
                  'baseline_sha256':SHA(BASE.read_bytes()).hexdigest(),
                  'previous_files_preserved':len(old_manifest),
                  'previous_files_removed':0, 'previous_files_modified':changed,
                  'new_files':sorted(set(new_files) | {
                      'AUDIT/evidence_v104/SOURCE_DIFF_V104.json',
                      'AUDIT/evidence_v104/RELEASE_ASSESSMENT_V104.md'})}
    (EV/'SOURCE_DIFF_V104.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    lines = ['# TrainOS v104 — release assessment', '', '**Decision: BLOCKED / NO-GO.**', '',
             'v103 source and evidence are byte-for-byte preserved.',
             f'24 functional domains; {status["configured_test_file_count"]} per-file test modules.', '',
             '| Acceptance | Result |','|---|---|',
             f'| At least 3 complete strict full pytest PASS | {status["three_complete_strict_full_pass"]} (PASS attempts {status["completed_strict_full_pass_iterations"]}; FAIL attempts 3 and 4) |',
             f'| 3 complete strict joint recovery/CI/diagnostics PASS | {status["three_complete_strict_joint_pass"]} (PASS attempts {status["completed_strict_joint_pass_iterations"]}) |',
             f'| Standard ordered serial per-file Kernel Runner | {status["standard_serial_kernel_completed"]} |',
             f'| Opt-in 4-worker per-file Kernel Runner | {status["worker_per_file_completed"]} |',
             f'| Opt-in batch Kernel Runner | {status["batch_mode_completed"]} |',
             '| Production PID1/cgroup/cross-UID verified | **False** |', '',
             'See VERIFICATION_SUMMARY_V104.json, SAFETY_CASE_V104.md and per-attempt logs.',
             'Strict full attempts 3 and 4 failed due to SQLite WAL initialization lock and remain in the evidence.',
             'Four-worker attempt 1 failed two timing-sensitive CI process tests and remains in the evidence.',
             'No result from v101 Codex/v103 is reclassified as a v104 PASS.',
             'Legacy direct runner bypass and supervisor-self SIGKILL keep production status NO-GO.', '']
    (EV/'RELEASE_ASSESSMENT_V104.md').write_text('\n'.join(lines),encoding='utf-8')
    files=sorted((p for p in ROOT.rglob('*') if eligible(p)), key=lambda p:p.relative_to(ROOT).as_posix())
    manifest={p.relative_to(ROOT).as_posix():SHA(p.read_bytes()).hexdigest() for p in files}
    if not set(old_manifest).issubset(set(manifest)):
        raise RuntimeError('Predecessor manifest regression')
    MANIFEST.write_text(json.dumps({'schema':'trainos.v104.sha256.v1',
                                    'base':'TrainOS-v103-source.zip',
                                    'base_sha256':SHA(BASE.read_bytes()).hexdigest(),
                                    'algorithm':'SHA-256',
                                    'excluded':[MANIFEST.relative_to(ROOT).as_posix()],
                                    'files':manifest},indent=2,sort_keys=True)+'\n',encoding='utf-8')
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(ARCHIVE,'w',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in files + [MANIFEST]:
            rel=p.relative_to(ROOT).as_posix()
            info=ZipInfo('trainos/'+rel,date_time=(1980,1,1,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=((0o100755 if os.access(p,os.X_OK) else 0o100644)<<16)
            with p.open('rb') as source, z.open(info,'w',force_zip64=True) as dest:
                shutil.copyfileobj(source,dest,65536)
    with ZipFile(ARCHIVE) as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP CRC verification failed')
        listed=json.loads(z.read('trainos/'+MANIFEST.relative_to(ROOT).as_posix()))['files']
        want={'trainos/'+s for s in listed} | {'trainos/'+MANIFEST.relative_to(ROOT).as_posix()}
        if set(z.namelist())!=want:
            raise RuntimeError('ZIP member completeness check failed')
        for rel,digest in listed.items():
            if SHA(z.read('trainos/'+rel)).hexdigest()!=digest:
                raise RuntimeError('ZIP SHA256 mismatch: '+rel)
        modechecks=json.loads((ROOT/'AUDIT/evidence_v103/MODE_RESTORATION_V103.json').read_text())
        for entry in modechecks['executables']:
            mode=(z.getinfo('trainos/'+entry['path']).external_attr>>16)&0o777
            if mode!=0o755:
                raise RuntimeError(f'Executable flag lost: {entry["path"]}')
    digest=SHA(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix('.sha256').write_text(f'{digest}  {ARCHIVE.name}\n')
    result={'path':str(ARCHIVE),'size_bytes':ARCHIVE.stat().st_size,
            'sha256':digest,'manifest_entries':len(manifest),'zip_files':len(manifest)+1,
            'unchanged_v103_members':len(old_manifest),
            'new_v104_files':len(provenance['new_files']),
            'three_strict_full_pass':status['three_complete_strict_full_pass'],
            'three_strict_joint_pass':status['three_complete_strict_joint_pass'],
            'serial_complete':status['standard_serial_kernel_completed'],
            'worker_complete':status['worker_per_file_completed'],
            'batch_complete':status['batch_mode_completed'],
            'decision':status['decision']}
    output = ARCHIVE.with_name('TrainOS-v104-build-result.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    build()
