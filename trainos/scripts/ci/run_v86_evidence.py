"""Bounded strict evidence collection. Never promote a pytest summary without exit 0."""
import json, subprocess, sys, time, os, signal
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'AUDIT/evidence_v86';out.mkdir(parents=True,exist_ok=True)
strict=['-W','error::ResourceWarning','-W','error::DeprecationWarning','-W','error::pytest.PytestUnraisableExceptionWarning']
combined=['tests/domains/recovery','tests/domains/ci_release','tests/domains/pytest_diagnostics']
items=[(f'strict_combined_{n}',combined,65) for n in range(1,4)]+[('full_suite_strict',['tests'],95)]
summary=[]
for name,paths,limit in items:
    cmd=[sys.executable,'-m','pytest','-q',*strict,*paths]
    start=time.monotonic()
    with (out/f'{name}.log').open('wb') as f:
        proc=subprocess.Popen(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code=proc.wait(timeout=limit)
            status='PASS' if code==0 else 'FAIL'
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)
            status='TIMEOUT';code=None
    result={'name':name,'status':status,'exit_code':code,'seconds':round(time.monotonic()-start,2),'timeout_seconds':limit,'log':str((out/f'{name}.log').relative_to(root))}
    summary.append(result)
    (out/f'{name}.json').write_text(json.dumps(result,indent=2))
    print(result,flush=True)
(out/'runs.json').write_text(json.dumps(summary,indent=2))
