"""Build cumulative TrainOS v106 ZIP with independently verified SHA-256 records.

Never modify historical v105 data. All attempted tests are included; absent or
failed tests stay visible and do not count as PASS. No production GO is possible
without independent cgroup and cross-UID certification evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path('/mnt/data')
EVIDENCE = ROOT/'AUDIT/evidence_v106'
PARENT = OUT/'TrainOS-v105-source.zip'
ZIP = OUT/'TrainOS-v106-source.zip'
MANIFEST = EVIDENCE/'SHA256_MANIFEST_V106.json'


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(PARENT) as parent:
        base = {info.filename: hashlib.sha256(parent.read(info.filename)).hexdigest()
                for info in parent.infolist() if not info.is_dir()}
        if parent.testzip() is not None:
            raise RuntimeError('parent CRC failure')
    def rel(path):return 'trainos/'+path.relative_to(ROOT).as_posix()
    files={rel(p):sha256(p) for p in ROOT.rglob('*') if p.is_file() and p != MANIFEST
           and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}
    missing=sorted(set(base)-set(files))
    changed=sorted(name for name in base if name in files and base[name]!=files[name])
    added=sorted(set(files)-set(base))
    if missing:
        raise RuntimeError('Cumulative source loss: '+', '.join(missing[:10]))
    from tests.kernel_runner.config import STAGES
    from tests.kernel_runner.runner import KernelTestRunner
    runner=KernelTestRunner()
    count=sum(len([p for target in stage.tests for p in runner._expand(target)]) for stage in STAGES)
    cases=['strict_full','combined','focused','kernel_default','kernel_workers','kernel_batch']
    attempts={k:[] for k in cases}
    for case in cases:
        for p in sorted(EVIDENCE.glob(case+'_*.json')):
            if p.name.endswith('.supervisor.json'):continue
            entry=json.loads(p.read_text())
            if entry.get('schema')!='trainos.verification.v106':continue
            attempts[case].append({field:entry.get(field) for field in
                ('case','iteration','status','exitcode','timed_out','duration_seconds',
                 'command','stdout','stderr','error','warnings')})
    matrix={key:{'attempts':len(arr),'pass':sum(x['status']=='PASS' for x in arr),
                 'fail':sum(x['status']!='PASS' for x in arr)} for key,arr in attempts.items()}
    modes={}
    for case in ('kernel_default','kernel_workers','kernel_batch'):
        modes[case]=[]
        for rec in attempts[case]:
            i=rec['iteration']
            txt=(EVIDENCE/f'{case}_{i}.stdout.log').read_text(errors='replace')
            supfile=EVIDENCE/f'{case}_{i}.supervisor.json'
            sup=json.loads(supfile.read_text()) if supfile.is_file() else {}
            files_started=len(re.findall(r'\bRUN: tests/',txt))
            batches=txt.count('RUN BATCH:')
            domains=txt.count('[STAGE START]')
            finish='ALL CONFIGURED STAGES PASSED' in txt
            complete=(rec['status']=='PASS' and rec['exitcode']==0 and finish
                      and domains==len(STAGES) and
                      (batches==len(STAGES) if case=='kernel_batch' else files_started==count)
                      and sup.get('cleanup_complete') is True
                      and not sup.get('residual_running_pids')
                      and sup.get('supervisor_exitcode')==0)
            modes[case].append({'iteration':i,'completed':complete,'exitcode':rec['exitcode'],
                                'files_started':files_started,'batch_starts':batches,
                                'domain_starts':domains,'finish_marker':finish,
                                'supervisor_cleanup':sup.get('cleanup_complete'),
                                'duration_seconds':rec['duration_seconds']})
    host=json.loads((EVIDENCE/'CGROUP_HOST_PROBE_V106.json').read_text())
    neg=json.loads((EVIDENCE/'DOUBLEFORK_SUPERVISOR_SIGKILL_V106.json').read_text())
    limits=[
       'cgroup v2 read-only/no delegation: real cgroup.kill end-to-end not executed',
       'real SIGKILL supervisor permits runner and double-fork survivor without independent containment',
       'cross-UID production and OS-enforced legacy fencing not independently certified',
       'authority itself can be SIGKILLed; OS lifecycle manager and restart not deployed',
       'hardware, railway safety and payment production readiness not certified',
    ]
    summary={
      'schema':'trainos.release-verification.v106','release':'v106','decision':'BLOCKED/NO-GO',
      'parent_sha256':sha256(PARENT),'parent_entries':len(base),
      'retained_identical':len(base)-len(changed),'changed':changed,'removed':missing,
      'added':added, 'functional_domains':len(STAGES),'configured_files':count,
      'matrix':matrix,'attempts':attempts,'kernel_modes':modes,
      'three_full_pass':matrix['strict_full']['pass']>=3,
      'three_combined_pass':matrix['combined']['pass']>=3,
      'serial_complete':any(x['completed'] for x in modes['kernel_default']),
      'worker_complete':any(x['completed'] for x in modes['kernel_workers']),
      'batch_complete':any(x['completed'] for x in modes['kernel_batch']),
      'host_probe':host,'supervisor_sigkill_negative_control':neg,
      'cgroup_kill_end_to_end':False,'production_admission_e2e':False,
      'cross_uid_os_fence_certified':False,'blockers':limits,
      'evidence_policy':'Unsuccessful and incomplete attempts remain recorded without relabeling',
    }
    summary_path=EVIDENCE/'VERIFICATION_SUMMARY_V106.json'
    summary_path.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    files[rel(summary_path)]=sha256(summary_path)
    MANIFEST.write_text(json.dumps({
       'schema':'trainos.sha256.manifest.v106','files':dict(sorted(files.items())),
       'excluded':[rel(MANIFEST)],'parent_sha256':sha256(PARENT),
       'parent_removed':missing,'parent_changed':changed,'parent_added':added
    },indent=2,ensure_ascii=False)+'\n')
    entries=sorted((p for p in ROOT.rglob('*') if p.is_file()
                    and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts), key=rel)
    pending=ZIP.with_suffix('.zip.partial')
    with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as out:
        for p in entries:out.write(p,rel(p))
    with zipfile.ZipFile(pending) as z:
        if z.testzip() is not None:raise RuntimeError('CRC failed')
        for key,expected in files.items():
            if hashlib.sha256(z.read(key)).hexdigest()!=expected:
                raise RuntimeError('SHA mismatch '+key)
        if len(z.namelist())!=len(files)+1:
            raise RuntimeError('count mismatch')
    pending.replace(ZIP)
    (OUT/'TrainOS-v106-source.sha256').write_text(f'{sha256(ZIP)}  {ZIP.name}\n')
    shutil.copy2(MANIFEST,OUT/'TrainOS-v106-SHA256_MANIFEST.json')
    shutil.copy2(summary_path,OUT/'TrainOS-v106-verification-summary.json')
    shutil.copy2(EVIDENCE/'RELEASE_ASSESSMENT_V106.md',OUT/'TrainOS-v106-release-assessment.md')
    (OUT/'TrainOS-v106-build-result.json').write_text(json.dumps({
        'zip':str(ZIP),'sha256':sha256(ZIP),'size_bytes':ZIP.stat().st_size,
        'manifest_files':len(files),'archive_entries':len(entries),
        'parent_files':len(base),'unchanged':len(base)-len(changed),'changed':len(changed),
        'added':len(added),'removed':len(missing),'matrix':matrix,
        'kernel_modes':modes,'decision':'BLOCKED/NO-GO'},indent=2)+'\n')
    print((OUT/'TrainOS-v106-build-result.json').read_text())
    return 0

if __name__=='__main__':raise SystemExit(main())
