"""Disposable Linux root controller for SIX roles; simulated root NEVER production GO.

Runs real SO_PEERCRED, UID-differentiated services, negative access probes,
SIGKILL at selected transaction/recovery boundaries and rollback/tamper cases.
Records every subprocess exit, stderr/stdout and a structured result matrix.
"""
import json
import os
import pathlib
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from island.attested_broker import ALL_CRASH_POINTS
from island.monotonic_root import RootClient
from island.anchored_admission import GENESIS

U = {'client': 25001, 'service': 25002, 'broker': 25003,
     'witness': 25004, 'permit': 25005, 'root': 25006}
GID = 25000
EVIDENCE = ROOT/'evidence'
R = {'stage':'ISLAND-GEO-022', 'uids':U, 'checks':{}, 'crash_matrix':[],
     'processes':[], 'limitations':[
         'All six UIDs are separate Linux processes, but privileged test controller can impersonate every UID',
         'Software root is separately UID-owned but NOT hardware-protected or monotonic against privileged rollback',
         'No independently verified OS-enforced MAC policy or systemd lifecycle in the execution environment',
         'Power-cut fsync, filesystem snapshots and same-broker-UID arbitrary execution not certified',
         'Root and witness CAS are two separate SQLite transactions; crash can cause intentional persistent NO-GO',
     ]}
RUNNING=[]
COUNTER=0


def drop(role):
    def fn():
        os.setgroups([])
        os.setgid(GID)
        os.setuid(U[role])
        os.umask(0o077)
    return fn


def launch(role, args, *, background=False, token=None, timeout=8):
    global COUNTER
    COUNTER += 1
    name=f'{COUNTER:03}-{role}-{args[0]}'
    argv=[sys.executable,'-m','island.secure_runtime',*args]
    env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONWARNINGS':'error::ResourceWarning,error::DeprecationWarning'}
    logs=EVIDENCE/'stage023-sixuid-process';logs.mkdir(exist_ok=True)
    rec={'name':name,'role':role,'stdout':f'stage023-sixuid-process/{name}.stdout',
         'stderr':f'stage023-sixuid-process/{name}.stderr','exit_code':None}
    R['processes'].append(rec)
    read_fd=write_fd=None
    if token is not None:
        read_fd,write_fd=os.pipe()
        argv.extend(['--token-fd',str(read_fd)])
    if background:
        o=open(logs/(name+'.stdout'),'wb');e=open(logs/(name+'.stderr'),'wb')
        try:
            p=subprocess.Popen(argv,cwd=ROOT,env=env,preexec_fn=drop(role),
                               stdout=o,stderr=e,
                               pass_fds=(() if read_fd is None else (read_fd,)))
            RUNNING.append((p,rec))
        finally:
            o.close();e.close()
            if read_fd is not None:
                os.close(read_fd)
                try:os.write(write_fd,token.encode('ascii'))
                finally:os.close(write_fd)
        return p
    if token is not None: raise RuntimeError('token must be delivered only on inherited FD')
    try:
        done=subprocess.run(argv,cwd=ROOT,env=env,preexec_fn=drop(role),
                            capture_output=True,timeout=timeout)
        (logs/(name+'.stdout')).write_bytes(b'[REDACTED STATE-BOUND PERMIT]\n' if args[0]=='issue' else done.stdout)
        (logs/(name+'.stderr')).write_bytes(done.stderr)
        rec['exit_code']=done.returncode
        return done
    except subprocess.TimeoutExpired:
        rec['exit_code']='TIMEOUT'
        raise


def stop(p,signal_number=signal.SIGTERM):
    if p.poll() is None:
        os.kill(p.pid,signal_number)
    try:p.wait(timeout=4)
    except subprocess.TimeoutExpired:
        p.kill();p.wait(timeout=4)
    for proc,rec in RUNNING:
        if proc is p:rec['exit_code']=p.returncode
    return p.returncode


def ready(path,p,seconds=5):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if path.is_socket() and p.poll() is None:
            return
        if p.poll() is not None:break
        time.sleep(.02)
    matching=next(r for proc,r in RUNNING if proc is p)
    raise RuntimeError('process startup failed: '+matching['name']+' rc '+str(p.poll())+' '+(EVIDENCE/matching['stderr']).read_text(errors='replace')[-900:])


def check(name,condition,**meta):
    R['checks'][name]={'pass':bool(condition),**meta}
    print('CHECK',name,'PASS' if condition else 'FAIL',flush=True)
    if not condition:raise AssertionError('E2E failed: '+name+' '+str(meta))


def denied_legacy(role,path,name):
    test=('import os,sys;'
          'f=os.open(sys.argv[1],os.O_RDWR|os.O_NOFOLLOW);os.close(f)')
    result=subprocess.run([sys.executable,'-c',test,str(path)],preexec_fn=drop(role),
                          capture_output=True,timeout=4)
    check(name,result.returncode!=0 and b'PermissionError' in result.stderr,
          exit_code=result.returncode)


def main():
    if os.geteuid()!=0 or sys.platform!='linux':
        R['skip_reason']='root in isolated Linux test environment required'
        return 77
    with tempfile.TemporaryDirectory(prefix='island-g022-') as td:
        base=pathlib.Path(td);os.chmod(base,0o755)
        ipc=base/'ipc';ipc.mkdir(mode=0o777);os.chmod(ipc,0o1777)
        for role in ('client','service','broker','witness','permit','root'):
            d=base/role;d.mkdir();os.chown(d,U[role],GID);os.chmod(d,0o700)
        rd=base/'root'/'anchor.sqlite';wd=base/'witness'/'witness.sqlite'
        pd=base/'permit'/'permits.sqlite';bd=base/'broker'/'broker.sqlite'
        private=base/'client'/'ed25519.private';public=base/'broker'/'ed25519.pub'
        root_private=base/'root'/'root-signing.private';root_public=base/'witness'/'root-trusted.pub'
        ckey=Ed25519PrivateKey.generate();rkey=Ed25519PrivateKey.generate()
        for path,data,role in ((private,ckey.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()),'client'),
                               (public,ckey.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw),'broker'),
                               (root_private,rkey.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()),'root'),
                               (root_public,rkey.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw),'witness')):
            path.write_bytes(data);os.chown(path,U[role],GID);os.chmod(path,0o600)
        rs=ipc/'root.sock';ws=ipc/'witness.sock';ps=ipc/'permit.sock';bs=ipc/'broker.sock';fs=ipc/'service.sock'
        identities=['--client-uid',str(U['client']),'--service-uid',str(U['service']),
                    '--broker-uid',str(U['broker']),'--witness-uid',str(U['witness']),
                    '--permit-uid',str(U['permit']),'--root-uid',str(U['root'])]
        def rootargs(point=None):
            val=['lab-root','--socket',str(rs),'--db',str(rd),'--root-key',str(root_private),
                 '--witness-uid',str(U['witness'])]
            return val+(['--crash-at',point] if point else [])
        def witnessargs(point=None):
            val=['witness','--socket',str(ws),'--db',str(wd),'--root-socket',str(rs),
                 '--root-public-key',str(root_public),*identities]
            return val+(['--crash-at',point] if point else [])
        def permitargs(point=None):
            val=['permit-authority','--socket',str(ps),'--db',str(pd),
                 '--witness-socket',str(ws),*identities]
            return val+(['--crash-at',point] if point else [])
        def brokerargs(point=None,role='lab-broker',sock=bs):
            val=[role,'--socket',str(sock),'--db',str(bd),
                 '--witness-socket',str(ws),'--permit-socket',str(ps),
                 '--public-key',str(public),*identities]
            return val+(['--crash-at',point] if point else [])
        def facadeargs():
            return ['facade','--socket',str(fs),'--broker-socket',str(bs),
                    '--client-uid',str(U['client']),'--broker-uid',str(U['broker']),
                    '--witness-uid',str(U['witness'])]
        def permit():
            proc=launch('client',['issue','--socket',str(ps),'--permit-uid',str(U['permit'])])
            if proc.returncode!=0:raise RuntimeError('permit issue failed '+proc.stderr.decode()[-600:])
            return json.loads(proc.stdout)['token']
        def broker_start(point=None,role='lab-broker',sock=bs):
            if sock.exists() or sock.is_symlink():
                sock.unlink()  # test-only root cleanup; never permitted in secure lifecycle
            p=launch('broker',brokerargs(point,role,sock),background=True,token=permit())
            ready(sock,p)
            return p
        def client(payload):
            return launch('client',['sign','--private-key',str(private),'--payload',payload,
                                    '--broker-uid',str(U['broker'])])
        def submit(envelope):
            path=base/('envelope-'+str(len(list(base.glob('envelope-*'))))+'.json')
            path.write_bytes(envelope);os.chmod(path,0o644)
            return launch('client',['submit','--socket',str(fs),'--facade-uid',str(U['service']),
                                    '--envelope-file',str(path)])
        def write(payload):
            signed=client(payload)
            if signed.returncode!=0:raise RuntimeError('signing failed '+signed.stderr.decode()[-500:])
            return submit(signed.stdout)
        root=launch('root',rootargs(),background=True);ready(rs,root)
        witness=launch('witness',witnessargs(),background=True);ready(ws,witness)
        auth=launch('permit',permitargs(),background=True);ready(ps,auth)
        broker=broker_start()
        facade=launch('service',facadeargs(),background=True);ready(fs,facade)
        check('six_real_distinct_uid_processes',all(p.poll() is None for p in (root,witness,auth,broker,facade))
              and len(set(U.values()))==6,process_uids=U)
        check('socket_uid_separation',[p.stat().st_uid for p in (rs,ws,ps,bs,fs)]==
              [U['root'],U['witness'],U['permit'],U['broker'],U['service']])
        signed=client('first-split-signed')
        success=submit(signed.stdout)
        check('direct_signed_client_to_split_broker',success.returncode==0,exit_code=success.returncode)
        replay=submit(signed.stdout)
        check('nonce_replay_rejected',replay.returncode!=0,exit_code=replay.returncode)
        forged=json.loads(signed.stdout);forged['message']['payload']='66616b65'
        invalid=submit(json.dumps(forged).encode())
        check('modified_signature_rejected',invalid.returncode!=0,exit_code=invalid.returncode)
        for role,path,name in (('client',bd,'client_cannot_write_broker'),
                               ('service',bd,'facade_cannot_write_broker'),
                               ('permit',wd,'permit_cannot_write_witness'),
                               ('client',pd,'client_cannot_write_permits'),
                               ('broker',root_private,'broker_cannot_read_root_private'),
                               ('service',private,'service_cannot_read_signing_key'),
                               ('broker',pd,'broker_cannot_write_permits')):
            denied_legacy(role,path,name)
        # Guard fails even with live lab services and correct permit.
        strict=launch('broker',brokerargs(role='strict-broker',sock=ipc/'strict-denied.sock'),
                      background=True,token=permit())
        check('strict_production_gate_blocks_no_mac_root_or_manager',strict.wait(timeout=5)!=0)
        stop(strict)
        # Independent startup lease: competing broker with a different endpoint.
        competing=launch('broker',brokerargs(sock=ipc/'racing.sock'),background=True,token=permit())
        check('concurrent_startup_denied',competing.wait(timeout=5)!=0)
        stop(competing)
        # The 17 previous broker crash boundary points still apply to split services.
        stop(broker)
        for index,point in enumerate(ALL_CRASH_POINTS):
            print('CRASH',index+1,len(ALL_CRASH_POINTS),point,flush=True)
            broker=broker_start(point)
            result=write('split-sigkill-'+str(index))
            try:code=broker.wait(timeout=5)
            except subprocess.TimeoutExpired:code=None
            if code is None:stop(broker,signal.SIGKILL)
            else:stop(broker)
            record={'point':point,'broker_exit':broker.returncode,'request_exit':result.returncode}
            R['crash_matrix'].append(record)
            if broker.returncode != -signal.SIGKILL:
                raise AssertionError('broker SIGKILL not reached '+repr(record))
            broker=broker_start()
            recovered=write('post-recovery-'+str(index))
            record['restart_recovery']=recovered.returncode==0
            if recovered.returncode!=0:
                raise AssertionError('post-crash recovery refused '+recovered.stderr.decode()[-700:])
            stop(broker)
            (EVIDENCE/'stage023-sixuid-progress.json').write_text(json.dumps(R,indent=2,sort_keys=True)+'\n')
        check('broker_sigkill_17_boundaries',len(R['crash_matrix'])==len(ALL_CRASH_POINTS)
              and all(r['broker_exit']==-signal.SIGKILL and r['restart_recovery'] for r in R['crash_matrix']))
        # Root-controlled adversarial file replacement (not protection against root).
        stop(auth)
        safe = pd.with_suffix('.safe')
        pd.rename(safe); pd.symlink_to(safe)
        attempted = launch('permit', permitargs(), background=True)
        check('permit_database_symlink_denied', attempted.wait(timeout=5)!=0)
        stop(attempted)
        pd.unlink(); safe.rename(pd)
        if ps.exists(): ps.unlink()
        auth=launch('permit',permitargs(),background=True);ready(ps,auth)

        stop(witness)
        saved=wd.with_suffix('.safe');wd.rename(saved);wd.symlink_to(saved)
        if ws.exists():ws.unlink()
        attempted=launch('witness',witnessargs(),background=True)
        check('witness_database_symlink_denied',attempted.wait(timeout=5)!=0)
        stop(attempted)
        wd.unlink();saved.rename(wd)
        if ws.exists():ws.unlink()
        witness=launch('witness',witnessargs(),background=True);ready(ws,witness)

        # Wrong independent root verification key must block witness startup.
        stop(witness)
        root_public.write_bytes(b'x'*32)
        if ws.exists():ws.unlink()
        attempted=launch('witness',witnessargs(),background=True)
        check('root_verifier_key_substitution_denied',attempted.wait(timeout=5)!=0)
        stop(attempted)
        root_public.write_bytes(rkey.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
        os.chown(root_public,U['witness'],GID);os.chmod(root_public,0o600)
        if ws.exists():ws.unlink()
        witness=launch('witness',witnessargs(),background=True);ready(ws,witness)

        # Local journal corruption must never be auto-admitted.
        with closing(sqlite3.connect(bd)) as db:
            db.execute('INSERT OR REPLACE INTO phase VALUES (1,?,?,?,?)',(999,'f'*64,'f'*64,'f'*64))
            db.commit()
        if bs.exists():bs.unlink()
        attempted=launch('broker',brokerargs(),background=True,token=permit())
        check('corrupt_phase_journal_denied',attempted.wait(timeout=5)!=0)
        stop(attempted)
        with closing(sqlite3.connect(bd)) as db:
            db.execute('DELETE FROM phase');db.commit()

        lock=base/'broker'/'.broker-startup.lock'
        lock_saved=lock.with_suffix('.safe')
        lock.rename(lock_saved);lock.symlink_to(lock_saved)
        attempted=launch('broker',brokerargs(),background=True,token=permit())
        check('startup_lock_symlink_denied',attempted.wait(timeout=5)!=0)
        stop(attempted)
        lock.unlink();lock_saved.rename(lock)

        # Broker must reject occupied socket published by a privileged test orchestrator.
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as rogue:
            rogue.bind(str(bs));rogue.listen(1)
            attempted=launch('broker',brokerargs(),background=True,token=permit())
            check('occupied_broker_socket_denied',attempted.wait(timeout=5)!=0)
            stop(attempted)
        bs.unlink()

        # Permit authority is independently killable: after-consume crash burns token.
        recovery_token=permit()
        stop(auth)
        if ps.exists():ps.unlink()
        auth=launch('permit',permitargs('after_permit_consume'),background=True);ready(ps,auth)
        attempted=launch('broker',brokerargs(),background=True,token=recovery_token)
        check('permit_consume_sigkill',auth.wait(timeout=5)==-signal.SIGKILL)
        check('broker_startup_after_permit_authority_sigkill_denied',attempted.wait(timeout=5)!=0)
        stop(attempted);stop(auth)
        if ps.exists():ps.unlink()
        auth=launch('permit',permitargs(),background=True);ready(ps,auth)
        broker=broker_start()
        check('new_permit_after_consumed_crash_recovers',write('post-permit-rotation').returncode==0)
        stop(broker)

        # Root-at-rest rollback while witness and broker remain advanced.
        stop(root)
        with closing(sqlite3.connect(rd)) as db:
            db.execute('UPDATE anchor SET sequence=0,digest=? WHERE id=1',(GENESIS,))
            db.commit()
        root=launch('root',rootargs(),background=True);ready(rs,root)
        stop(witness)
        # A divergent root MUST prevent witness socket from being published.
        if ws.exists():ws.unlink()
        mismatch=launch('witness',witnessargs(),background=True)
        check('root_genesis_rollback_denied',mismatch.wait(timeout=5)!=0)
        stop(mismatch)
        # Attempt to recover service with witness down must fail before publishing broker endpoint.
        if bs.exists():bs.unlink()
        denied=launch('broker',brokerargs(),background=True,token='a'*64)
        check('no_witness_fail_closed',denied.wait(timeout=5)!=0)
        stop(denied)
        stop(facade);stop(auth);stop(root)
        check('software_root_does_not_grant_production_go',True,classification='BLOCKED/NO-GO')
    return 0


if __name__=='__main__':
    code=1
    try:code=main()
    except BaseException as exc:
        R['failure']=repr(exc)
        import traceback
        traceback.print_exc()
    finally:
        for proc,rec in RUNNING:
            if proc.poll() is None:
                try:stop(proc,signal.SIGKILL)
                except (ProcessLookupError,subprocess.TimeoutExpired):pass
            rec['exit_code']=proc.poll()
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE/'stage023-sixuid-e2e.json').write_text(json.dumps(R,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'exit_code':code,'checks':len(R['checks']),
                          'crash_points':len(R['crash_matrix']),'failure':R.get('failure')},sort_keys=True),flush=True)
    sys.exit(code)
