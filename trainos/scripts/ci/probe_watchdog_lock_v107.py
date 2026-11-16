"""Real lock race + SIGKILL lock release; not a kernel containment test."""
from __future__ import annotations
import json,os
from pathlib import Path
import signal,subprocess,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[2]
EVID=ROOT/'AUDIT/evidence_v107'


def main():
    EVID.mkdir(exist_ok=True,parents=True)
    result={'schema':'trainos.v107.watchdog-process-lock','status':'FAIL',
            'production_containment_proved':False,'os_service_restart_proved':False}
    with tempfile.TemporaryDirectory(prefix='trainos-v107-lock-') as folder:
        root=Path(folder)
        marker=root/'READY'
        hold=('import time,pathlib;from scripts.ci.cgroup_watchdog_v107 import SingleWatchdog;'
              f'with SingleWatchdog(pathlib.Path({folder!r})):\n'
              f'    pathlib.Path({str(marker)!r}).write_text("locked")\n'
              '    time.sleep(60)\n')
        # A compound `with` cannot follow a semicolon; use newline-based script.
        hold=("from scripts.ci.cgroup_watchdog_v107 import SingleWatchdog\n"
              "from pathlib import Path\nimport time\n"
              f"with SingleWatchdog(Path({folder!r})):\n"
              f"    Path({str(marker)!r}).write_text('locked')\n    time.sleep(60)\n")
        trial=("from scripts.ci.cgroup_watchdog_v107 import SingleWatchdog\n"
              "from pathlib import Path\nimport sys\n"
              f"try:\n    with SingleWatchdog(Path({folder!r})):\n        print('LOCK_ACQUIRED')\n"
              "except BlockingIOError:\n    print('LOCK_DENIED')\n    sys.exit(125)\n")
        a=subprocess.Popen([sys.executable,'-c',hold],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for _ in range(150):
                if marker.is_file():break
                if a.poll() is not None:raise RuntimeError('lock holder failed')
                time.sleep(.02)
            if not marker.is_file():raise TimeoutError('lock not acquired')
            b=subprocess.run([sys.executable,'-c',trial],cwd=ROOT,capture_output=True,text=True,timeout=10)
            os.kill(a.pid,signal.SIGKILL)
            a.wait(timeout=5)
            c=subprocess.run([sys.executable,'-c',trial],cwd=ROOT,capture_output=True,text=True,timeout=10)
            result['observations']={'holder_sigkill_exitcode':a.returncode,
                'competing_exitcode':b.returncode,'competing_stdout':b.stdout,'competing_stderr':b.stderr,
                'after_kill_exitcode':c.returncode,'after_kill_stdout':c.stdout,'after_kill_stderr':c.stderr}
            if a.returncode==-9 and b.returncode==125 and 'LOCK_DENIED' in b.stdout and c.returncode==0 and 'LOCK_ACQUIRED' in c.stdout:
                result['status']='PASS_NEGATIVE_CONTROL'
        except BaseException as exc:
            result['error']=f'{type(exc).__name__}: {exc}'
        finally:
            if a.poll() is None:
                a.kill();a.wait(timeout=5)
            (EVID/'WATCHDOG_LOCK_SIGKILL_V107.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result.get('observations'))
    return 0 if result['status']=='PASS_NEGATIVE_CONTROL' else 1

if __name__=='__main__':raise SystemExit(main())
