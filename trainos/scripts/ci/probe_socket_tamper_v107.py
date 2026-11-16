"""Cross-UID local socket and SQLite journal filesystem tamper negative test."""
from __future__ import annotations
import json,os
from pathlib import Path
import shutil,subprocess,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'AUDIT/evidence_v107'


def main():
    E.mkdir(exist_ok=True,parents=True)
    top=Path(tempfile.mkdtemp(prefix='trainos-v107-tamper-',dir='/tmp'))
    os.chmod(top,0o711)
    d=top/'service';d.mkdir(mode=0o711)
    srv=subprocess.Popen([sys.executable,'-m','scripts.ci.uid_broker_v107','serve',
        '--root',str(d),'--allowed-uid','65534','--max-requests','1',
        '--report',str(E/'SOCKET_TAMPER_SERVER_V107.json')],cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    result={'schema':'trainos.v107.socket-tamper','status':'FAIL','production_admitted':False}
    try:
        for _ in range(150):
            if (d/'admission.sock').exists():break
            time.sleep(.02)
        code=("import os, pathlib, json\n"
              f"sock=pathlib.Path({str(d/'admission.sock')!r})\n"
              f"db=pathlib.Path({str(d/'broker-journal.sqlite')!r})\n"
              "r={}\n"
              "try:sock.unlink();r['unlink']='SUCCEEDED'\n"
              "except OSError as e:r['unlink']=str(e.errno)\n"
              "try:db.open('rb').read(1);r['read']='SUCCEEDED'\n"
              "except OSError as e:r['read']=str(e.errno)\n"
              "print(json.dumps(r))\n")
        def drop():os.setgroups([]);os.setgid(65534);os.setuid(65534)
        p=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,timeout=8,preexec_fn=drop)
        tamper=json.loads(p.stdout)
        req=subprocess.run([sys.executable,'-m','scripts.ci.uid_broker_v107','request',
            '--socket',str(d/'admission.sock'),'--nonce','b'*32],cwd=ROOT,
            capture_output=True,timeout=8,preexec_fn=drop)
        out,err=srv.communicate(timeout=10)
        result['observations']={'tamper_exitcode':p.returncode,'tamper':tamper,
            'request_exitcode':req.returncode,'request_response':json.loads(req.stdout),
            'server_exitcode':srv.returncode,'server_stderr':err.decode(errors='replace')}
        if p.returncode==0 and tamper=={'unlink':'13','read':'13'} and req.returncode==125 and srv.returncode==0:
            result['status']='PASS_NEGATIVE_CONTROL'
    except BaseException as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if srv.poll() is None:srv.kill()
        srv.communicate(timeout=5)
        shutil.rmtree(top)
        (E/'SOCKET_TAMPER_CROSS_UID_V107.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result.get('observations'))
    return 0 if result['status']=='PASS_NEGATIVE_CONTROL' else 1

if __name__=='__main__':raise SystemExit(main())
