"""Real 20-client cross-UID IPC burst, durable replay across restart; deny-only."""
from __future__ import annotations
import json,os
from pathlib import Path
import shutil,subprocess,sys,tempfile,time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'AUDIT/evidence_v107'

def drop(uid):
    def setid():
        os.setgroups([]);os.setgid(uid);os.setuid(uid)
    return setid


def spawn_server(folder:Path,n:int,report:Path):
    cmd=[sys.executable,'-m','scripts.ci.uid_broker_v107','serve','--root',str(folder),
         '--allowed-uid','65534','--max-requests',str(n),'--report',str(report)]
    proc=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    for _ in range(200):
        if (folder/'admission.sock').exists():break
        if proc.poll() is not None:raise RuntimeError(proc.stderr.read().decode())
        time.sleep(.02)
    else:raise TimeoutError('broker socket unavailable')
    return proc


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    result={'schema':'trainos.v107.real-crossuid-ipc-burst','production_admitted':False,'cases':[],
            'status':'FAIL','kernel_so_peercred':True}
    tmp=Path(tempfile.mkdtemp(prefix='trainos-v107-burst-',dir='/tmp'))
    os.chmod(tmp,0o711)
    folder=tmp/'broker';folder.mkdir(mode=0o711)
    servers=[]
    clients=[]
    try:
        s=spawn_server(folder,20,OUT/'CROSS_UID_BROKER_BURST_SERVER_V107.json');servers.append(s)
        for n in range(20):
            uid=65534 if n<16 else 65533
            cmd=[sys.executable,'-m','scripts.ci.uid_broker_v107','request','--socket',str(folder/'admission.sock'),
                 '--nonce',('f'*32 if n<16 else f'{n:032x}')]
            clients.append((n,uid,subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,preexec_fn=drop(uid))))
        for n,uid,proc in clients:
            stdout,stderr=proc.communicate(timeout=15)
            status=json.loads(stdout) if stdout else None
            result['cases'].append({'request':n,'uid':uid,'exitcode':proc.returncode,
                                    'response':status,'stdout':stdout.decode(errors='replace'),
                                    'stderr':stderr.decode(errors='replace')})
        s.communicate(timeout=15)
        result['first_server_code']=s.returncode
        s=spawn_server(folder,1,OUT/'CROSS_UID_BROKER_RESTART_SERVER_V107.json');servers.append(s)
        cmd=[sys.executable,'-m','scripts.ci.uid_broker_v107','request','--socket',str(folder/'admission.sock'),'--nonce','f'*32]
        again=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=10,preexec_fn=drop(65534))
        s.communicate(timeout=10)
        result['restart_replay']={'response':json.loads(again.stdout),'exitcode':again.returncode,'server_exitcode':s.returncode}
        successes=sum(x['response']['reason']=='CONTAINMENT_NOT_CERTIFIED' for x in result['cases'] if x['uid']==65534)
        replays=sum(x['response']['reason']=='REPLAY' for x in result['cases'] if x['uid']==65534)
        denied=sum(x['response']['reason']=='INVALID_PEER' for x in result['cases'] if x['uid']==65533)
        result['status']='PASS_NEGATIVE_CONTROL' if (successes==1 and replays==15 and denied==4
                     and all(x['exitcode']==125 for x in result['cases'])
                     and all(p.returncode==0 for p in servers)
                     and result['restart_replay']['response']['reason']=='REPLAY') else 'FAIL'
    except BaseException as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        for _,_,p in clients:
            if p.poll() is None:p.kill()
            try:p.communicate(timeout=5)
            except subprocess.TimeoutExpired:pass
        for s in servers:
            if s.poll() is None:s.kill()
            try:s.communicate(timeout=5)
            except subprocess.TimeoutExpired:pass
        shutil.rmtree(tmp)
        (OUT/'CROSS_UID_BROKER_BURST_V107.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],len(result['cases']),result.get('restart_replay'))
    return 0 if result['status']=='PASS_NEGATIVE_CONTROL' else 1

if __name__=='__main__':raise SystemExit(main())
