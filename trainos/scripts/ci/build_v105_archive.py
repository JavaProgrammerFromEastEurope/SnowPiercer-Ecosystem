"""Deterministic lineage audit, SHA-256 manifest and cumulative TrainOS v105 ZIP.

Use only AFTER all v105 verification processes have finished. Does not fabricate
PASS: each candidate report is read from the independent attempt record.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import re
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'AUDIT/evidence_v105'
OUTDIR = Path('/mnt/data')
ARCHIVE = OUTDIR / 'TrainOS-v105-source.zip'
BASE = OUTDIR / 'TrainOS-v104-source.zip'
MANIFEST = EVIDENCE / 'SHA256_MANIFEST_V105.json'


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    if not BASE.is_file():
        raise FileNotFoundError(BASE)
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(BASE) as old:
        base_hashes = {item.filename: hashlib.sha256(old.read(item.filename)).hexdigest()
                       for item in old.infolist() if not item.is_dir()}
    def rel(p: Path) -> str:
        return 'trainos/' + p.relative_to(ROOT).as_posix()
    source = {rel(p): hash_file(p) for p in ROOT.rglob('*') if p.is_file()
              and p != MANIFEST and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}
    removed = sorted(set(base_hashes)-set(source))
    changed = sorted(x for x in base_hashes if x in source and source[x]!=base_hashes[x])
    added = sorted(set(source)-set(base_hashes))
    if removed:
        raise RuntimeError(f'Legacy lineage loss: {removed[:10]}')
    prefix = ('strict_full','combined','kernel_default','kernel_workers','kernel_batch','focused')
    runs={}
    for case in prefix:
        runs[case]=[]
        for report in sorted(EVIDENCE.glob(case+'_*.json')):
            if report.name.endswith('.supervisor.json'):
                continue
            payload=json.loads(report.read_text())
            if payload.get('schema')!='trainos.verification.v105':
                continue
            runs[case].append({k:payload.get(k) for k in ('case','iteration','status','exitcode','timed_out','duration_seconds')})
    matrix = {case:{'runs':len(reports),'pass':sum(r['status']=='PASS' for r in reports),
                    'fail':sum(r['status']!='PASS' for r in reports)} for case,reports in runs.items()}
    modes = {}
    # Independent completion proof: process exit=0 alone is insufficient.
    from tests.kernel_runner.config import STAGES
    from tests.kernel_runner.runner import KernelTestRunner
    legacy_runner = KernelTestRunner()
    configured_count = sum(len([f for target in stage.tests
                                for f in legacy_runner._expand(target)]) for stage in STAGES)
    for case in ('kernel_default','kernel_workers','kernel_batch'):
        modes[case] = []
        for record in runs[case]:
            n=record['iteration']
            log=EVIDENCE/f'{case}_{n}.stdout.log'
            output=log.read_text(encoding='utf-8',errors='replace') if log.exists() else ''
            supervisor_path=EVIDENCE/f'{case}_{n}.supervisor.json'
            sup=json.loads(supervisor_path.read_text()) if supervisor_path.exists() else {}
            file_starts=len(re.findall(r'\bRUN: tests/',output))
            batch_starts=output.count('RUN BATCH:')
            domain_starts=output.count('[STAGE START]')
            finish='ALL CONFIGURED STAGES PASSED' in output
            complete=(record['status']=='PASS' and finish and domain_starts==len(STAGES)
                      and (batch_starts==len(STAGES) if case=='kernel_batch'
                           else file_starts==configured_count)
                      and sup.get('cleanup_complete') is True
                      and not sup.get('residual_running_pids'))
            modes[case].append({'iteration':n,'recorded_status':record['status'],
                                'confirmed_complete':complete,'files_started':file_starts,
                                'batches_started':batch_starts,'domains_started':domain_starts,
                                'expected_domains':len(STAGES),'expected_files':configured_count,
                                'finished_marker':finish,'cleanup_complete':sup.get('cleanup_complete'),
                                'duration_seconds':record.get('duration_seconds')})
    safety=json.loads((EVIDENCE/'SUPERVISOR_SELF_SIGKILL_NEGATIVE_CONTROL.json').read_text())
    boundary=json.loads((EVIDENCE/'CGROUP_PID1_PIDFD_PROBE_V105.json').read_text())
    summary={
        'schema':'trainos.release-verification.v105','release':'v105','decision':'BLOCKED/NO-GO',
        'parent_archive_sha256':hash_file(BASE),'base_file_count':len(base_hashes),
        'base_removed':removed,'base_changed':changed,'base_added':added,
        'test_area_count':len(STAGES),'configured_file_count':configured_count,
        'attempts':runs,'matrix':matrix,'kernel_modes':modes,
        'negative_control_supervisor_self_sigkill':safety,
        'environment_boundary':boundary,
        'full_strict_three_pass':matrix['strict_full']['pass']>=3,
        'joint_strict_three_pass':matrix['combined']['pass']>=3,
        'serial_complete':any(x['confirmed_complete'] for x in modes['kernel_default']),
        'worker_complete':any(x['confirmed_complete'] for x in modes['kernel_workers']),
        'batch_complete':any(x['confirmed_complete'] for x in modes['kernel_batch']),
        'production_cgroup_certified':False,
        'independent_supervisor_self_kill_containment':False,
        'blockers':['no OS-managed cgroup v2 delegation in this environment',
                    'real supervisor-self SIGKILL leaves active descendants until independently cleaned',
                    'mandatory production admission currently refuses startup, no production E2E',
                    'no cross-UID/PID1 or physical integration certification']
    }
    (EVIDENCE/'VERIFICATION_SUMMARY_V105.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    # Include summary itself in the manifest (no circular self-hash).
    source[rel(EVIDENCE/'VERIFICATION_SUMMARY_V105.json')] = hash_file(EVIDENCE/'VERIFICATION_SUMMARY_V105.json')
    MANIFEST.write_text(json.dumps({
        'schema':'trainos.sha256.manifest.v105',
        'excludes':['trainos/AUDIT/evidence_v105/SHA256_MANIFEST_V105.json'],
        'files':dict(sorted(source.items())),
        'lineage_removed':removed,'lineage_changed':changed,'lineage_added':added,
    },indent=2,ensure_ascii=False)+'\n')
    archive_entries = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts]
    tmp=ARCHIVE.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as zipout:
        for p in sorted(archive_entries, key=lambda x:rel(x)):
            zipout.write(p,rel(p))
    with zipfile.ZipFile(tmp) as checked:
        if checked.testzip() is not None:raise RuntimeError('ZIP CRC mismatch')
        for name, digest in source.items():
            if hashlib.sha256(checked.read(name)).hexdigest()!=digest:
                raise RuntimeError('ZIP SHA mismatch '+name)
        if len(checked.namelist()) != len(source)+1:
            raise RuntimeError('ZIP count mismatch')
    tmp.replace(ARCHIVE)
    checksum=hash_file(ARCHIVE)
    (OUTDIR/'TrainOS-v105-source.sha256').write_text(f'{checksum}  TrainOS-v105-source.zip\n')
    shutil.copy2(MANIFEST,OUTDIR/'TrainOS-v105-SHA256_MANIFEST.json')
    shutil.copy2(EVIDENCE/'VERIFICATION_SUMMARY_V105.json',OUTDIR/'TrainOS-v105-verification-summary.json')
    (OUTDIR/'TrainOS-v105-build-result.json').write_text(json.dumps({
        'archive':str(ARCHIVE),'sha256':checksum,'size':ARCHIVE.stat().st_size,
        'manifest_file_count':len(source),'archive_entries':len(source)+1,
        'v104_base_entries':len(base_hashes),'retained_byte_identical':len(base_hashes)-len(changed),
        'removed':len(removed),'modified':len(changed),'added':len(added),'verification':matrix,
    },indent=2)+'\n')
    print((OUTDIR/'TrainOS-v105-build-result.json').read_text())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
