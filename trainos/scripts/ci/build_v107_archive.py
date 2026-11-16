"""Build cumulative v107 ZIP with no loss and truthful executable evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path('/mnt/data')
PARENT=OUT/'TrainOS-v106-source.zip'
EVID=ROOT/'AUDIT'/'evidence_v107'
ZIP=OUT/'TrainOS-v107-source.zip'
MAN=EVID/'SHA256_MANIFEST_V107.json'
SUMMARY=EVID/'VERIFICATION_SUMMARY_V107.json'
ASSESS=EVID/'RELEASE_ASSESSMENT_V107.md'


def sha(data):
    d=hashlib.sha256()
    if isinstance(data,(bytes,bytearray)):
        d.update(data)
    else:
        with open(data,'rb') as f:
            for b in iter(lambda:f.read(1<<20),b''):d.update(b)
    return d.hexdigest()


def files_now():
    result={}
    for p in ROOT.rglob('*'):
        if not p.is_file() or p in {MAN,SUMMARY,ASSESS}:continue
        if '__pycache__' in p.parts or '.pytest_cache' in p.parts:continue
        result['trainos/'+p.relative_to(ROOT).as_posix()]=p
    return result


def attempts(case):
    result=[]
    for p in sorted(EVID.glob(f'{case}_*.json')):
        if p.name.endswith('.supervisor.json'):continue
        try:r=json.loads(p.read_text())
        except (OSError,json.JSONDecodeError):continue
        if r.get('schema')!='trainos.verification.v107':continue
        result.append({k:r.get(k) for k in ('case','iteration','status','exitcode','timed_out','duration_seconds','warnings','stdout','stderr','error','command')})
    return result


def build():
    EVID.mkdir(exist_ok=True,parents=True)
    # A live harness can append to stdout during hashing; never publish a
    # non-reproducible ZIP or silently omit an in-progress attempt.
    active=[]
    for case in ('strict_full','combined','focused','kernel_default','kernel_workers','kernel_batch'):
        for log in EVID.glob(f'{case}_*.stdout.log'):
            key=log.name.removesuffix('.stdout.log')
            if not (EVID/(key+'.exitcode')).exists():active.append(key)
    if active:
        raise RuntimeError('active runs prohibit cumulative freeze: '+', '.join(sorted(active)))
    with zipfile.ZipFile(PARENT) as z:
        if z.testzip() is not None:raise ValueError('parent ZIP CRC failed')
        baseline={n:sha(z.read(n)) for n in z.namelist() if not n.endswith('/')}
    current=files_now()
    changed=sorted(n for n in baseline if n in current and sha(current[n])!=baseline[n])
    removed=sorted(set(baseline)-set(current))
    added=sorted(set(current)-set(baseline))
    if removed:raise ValueError(f'cumulative source lost: {removed[:10]}')
    from tests.kernel_runner.config import STAGES
    from tests.kernel_runner.runner import KernelTestRunner
    runner=KernelTestRunner()
    configured=sum(len(runner._expand(t)) for stage in STAGES for t in stage.tests)
    cases=('strict_full','combined','focused','kernel_default','kernel_workers','kernel_batch')
    all_attempts={case:attempts(case) for case in cases}
    # Failed report-writing harness attempts have stdout/exitcode but no JSON.
    # They must not silently disappear from the audit denominator.
    incomplete=[]
    for case in cases:
        for codepath in sorted(EVID.glob(f'{case}_*.exitcode')):
            identity=codepath.stem
            if not (EVID/(identity+'.json')).exists():
                incomplete.append({'attempt':identity,'status':'HARNESS_FAILED',
                    'pytest_exitcode':codepath.read_text().strip(),
                    'stdout':identity+'.stdout.log','stderr':identity+'.stderr.log',
                    'classification':'unverified: report-writing harness failed'})
    matrix={k:{'attempts':len(rows)+sum(x['attempt'].startswith(k+'_') for x in incomplete),
               'pass':sum(r['status']=='PASS' and r['exitcode']==0 for r in rows),
               'fail':sum(r['status']!='PASS' or r['exitcode']!=0 for r in rows)
                      +sum(x['attempt'].startswith(k+'_') for x in incomplete)} for k,rows in all_attempts.items()}
    kernel={}
    for case in ('kernel_default','kernel_workers','kernel_batch'):
        kernel[case]=[]
        for a in all_attempts[case]:
            i=a['iteration']
            log=EVID/f'{case}_{i}.stdout.log'
            txt=log.read_text(errors='replace') if log.is_file() else ''
            sfile=EVID/f'{case}_{i}.supervisor.json'
            sup=json.loads(sfile.read_text()) if sfile.is_file() else {}
            starts=len(re.findall(r'\bRUN: tests/',txt))
            batches=txt.count('RUN BATCH:')
            domains=txt.count('[STAGE START]')
            marker='ALL CONFIGURED STAGES PASSED' in txt
            complete=(a['status']=='PASS' and a['exitcode']==0 and marker and domains==len(STAGES)
                      and (batches==len(STAGES) if case=='kernel_batch' else starts==configured)
                      and sup.get('cleanup_complete') is True
                      and not sup.get('residual_running_pids') and sup.get('supervisor_exitcode')==0)
            kernel[case].append({'iteration':i,'verified_complete':complete,'started_files':starts,
              'started_batches':batches,'started_domains':domains,'terminal_marker':marker,
              'supervisor_cleanup':sup.get('cleanup_complete'),'exitcode':a['exitcode'],
              'duration_seconds':a['duration_seconds']})
    host={'pid1':Path('/proc/1/comm').read_text().strip(),
          'cgroup_mountinfo':next((x for x in Path('/proc/self/mountinfo').read_text().splitlines()
                     if ' - cgroup2 ' in x),'not found'),
          'writable_cgroup_delegation':False}
    negative={}
    for name in ('PROCESS_BOUNDARY_PROBES_V107.json',
                 'DOUBLEFORK_SUPERVISOR_SIGKILL_V107.json',
                 'RUNNER_SIGNAL_PROBES_V107.json',
                 'WATCHDOG_LOCK_SIGKILL_V107.json',
                 'CROSS_UID_BROKER_BURST_V107.json',
                 'PRODUCTION_DENIAL_CROSS_UID_V107.json',
                 'CGROUP_HOST_PROBE_V107.json',
                 'WARNING_NEGATIVE_CONTROL_V107.json',
                 'CROSS_UID_LEGACY_BYPASS_V107.json',
                 'SOCKET_TAMPER_CROSS_UID_V107.json',
                 'API_COMPATIBILITY_V107.json'):
        p=EVID/name
        negative[name]=json.loads(p.read_text()) if p.is_file() else {'status':'NOT_EXECUTED'}
    required={'three_strict_full_pass':matrix['strict_full']['pass']>=3,
              'three_combined_pass':matrix['combined']['pass']>=3,
              'kernel_serial_completed':any(x['verified_complete'] for x in kernel['kernel_default']),
              'kernel_worker_completed':any(x['verified_complete'] for x in kernel['kernel_workers']),
              'kernel_batch_completed':any(x['verified_complete'] for x in kernel['kernel_batch'])}
    blockers=[
      'No independent writable delegated cgroup v2; kernel cgroup.kill and process migration defense unverified',
      'PID1 is not systemd; watchdog restart after SIGKILL not verified',
      'Authenticated SO_PEERCRED broker denies every execution: positive production IPC handoff is not implemented',
      'Direct legacy KernelTestRunner remains callable; OS-level write service fencing not deployed',
      'No real authority SIGKILL recovery in writable cgroup, no physical-system integration',
    ]
    summary={'schema':'trainos.release-verification.v107','release':'v107','decision':'BLOCKED/NO-GO',
      'parent_zip_sha256':sha(PARENT),'parent_files':len(baseline),
      'parent_identical_files':len(baseline)-len(changed), 'parent_changed':changed,
      'parent_removed':removed,'added_files':len(added), 'added_paths':added,
      'domains':len(STAGES),'configured_test_files':configured,'matrix':matrix,
      'attempts':all_attempts,'harness_failures':incomplete,'kernel_modes':kernel,'host':host,'process_negative_controls':negative,
      'required_checks':required,'all_requested_regressions_confirmed':all(required.values()),
      'production_cgroup_e2e':False,'production_ipc_e2e':False,'os_legacy_fencing_e2e':False,
      'safety_blockers':blockers}
    SUMMARY.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    assessment=['# TrainOS v107 — cumulative release assessment','',
       '**Decision: BLOCKED / NO-GO**. Production isolation and certification not demonstrated.','',
       '## Test matrix','', '| Check | Attempts | PASS | FAIL |','|---|---:|---:|---:|']
    assessment.extend(f"| {case} | {m['attempts']} | {m['pass']} | {m['fail']} |" for case,m in matrix.items())
    assessment+=['','## Kernel Runner completeness', '', f'Configured {len(STAGES)} domains, {configured} per-file starts.', '']
    for case,rows in kernel.items():
        for r in rows:
            assessment.append(f"- {case} #{r['iteration']}: verified_complete={r['verified_complete']}, files={r['started_files']}, batches={r['started_batches']}, domains={r['started_domains']}, exitcode={r['exitcode']}")
    assessment+=['','## Incomplete/failed verification harness attempts','']
    assessment.extend(f"- {x['attempt']}: report writing failed, pytest exit code={x['pytest_exitcode']}; not counted as PASS." for x in incomplete)
    assessment+=['','## Preservation', '',f'- Parent v106 SHA-256: `{sha(PARENT)}`',
                 f'- Parent files: {len(baseline)}, modified: {len(changed)}, removed: {len(removed)}, newly added: {len(added)}.',
                 '- All historical evidence from v106 is preserved, including failed attempts.','',
                 '## Production blockers', '']
    assessment.extend(f'- {x}' for x in blockers)
    assessment+=['','## Boundary of claims','','- Watchdog startup sweep tested by filesystem mocks only, not cgroupfs.',
       '- Actual cross-UID SO_PEERCRED, replay and UID spoof *negative* controls are tested.',
       '- Real SIGKILL supervisor negative control demonstrates process survivors without OS cgroup containment.',
       '- A systemd service prototype is included but not installed, configured, or certified.',
       '- All completed PASS/FAIL logs retained under `AUDIT/evidence_v107`.', '']
    ASSESS.write_text('\n'.join(assessment))
    current=files_now()
    current['trainos/'+SUMMARY.relative_to(ROOT).as_posix()]=SUMMARY
    current['trainos/'+ASSESS.relative_to(ROOT).as_posix()]=ASSESS
    digests={k:sha(v) for k,v in sorted(current.items())}
    MAN.write_text(json.dumps({'schema':'trainos.sha256.manifest.v107','files':digests,
        'excluded':['trainos/'+MAN.relative_to(ROOT).as_posix()],
        'parent_sha256':sha(PARENT),'removed':removed,'changed':changed,
        'added':added},indent=2)+'\n')
    current['trainos/'+MAN.relative_to(ROOT).as_posix()]=MAN
    tmp=ZIP.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as out:
        for name,path in sorted(current.items()):out.write(path,name)
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:raise RuntimeError('v107 CRC mismatch')
        if len(z.namelist())!=len(digests)+1:raise RuntimeError('v107 file count mismatch')
        for name,digest in digests.items():
            if sha(z.read(name))!=digest:raise RuntimeError('v107 SHA mismatch: '+name)
    tmp.replace(ZIP)
    (OUT/'TrainOS-v107-source.sha256').write_text(f'{sha(ZIP)}  {ZIP.name}\n')
    shutil.copy2(MAN,OUT/'TrainOS-v107-SHA256_MANIFEST.json')
    shutil.copy2(SUMMARY,OUT/'TrainOS-v107-verification-summary.json')
    shutil.copy2(ASSESS,OUT/'TrainOS-v107-release-assessment.md')
    result={'zip':str(ZIP),'sha256':sha(ZIP),'files':len(current),
            'parent_files':len(baseline),'removed':removed,'changed':changed,
            'matrix':matrix,'kernel_modes':kernel,'status':'BLOCKED/NO-GO'}
    (OUT/'TrainOS-v107-build-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(build())
