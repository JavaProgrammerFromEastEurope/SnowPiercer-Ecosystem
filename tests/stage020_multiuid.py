"""Run as root in disposable Linux test environment; creates no OS users."""
import json,os,pathlib,signal,subprocess,sys,tempfile,time
root=pathlib.Path(__file__).resolve().parents[1]
U={'client':23001,'service':23002,'witness':23003};G=23000
results={'uids':U,'checks':{},'limitations':[]};procs=[]
def drop(role):
 def run():os.setgroups([]);os.setgid(G);os.setuid(U[role])
 return run
def cmd(role,args,background=False):
 command=[sys.executable,'-m','island.guarded_runtime',*args[1:]] if role=='service' else [sys.executable,'-m','island.isolated_runtime',*args]
 env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
 if background:
  p=subprocess.Popen(command,cwd=root,env=env,preexec_fn=drop(role),stdout=subprocess.PIPE,stderr=subprocess.PIPE);procs.append(p);return p
 return subprocess.run(command,cwd=root,env=env,preexec_fn=drop(role),capture_output=True,text=True,timeout=12)
def wait(path,p):
 for _ in range(100):
  if path.exists():return
  if p.poll() is not None:break
  time.sleep(.05)
 raise RuntimeError('startup failed: '+p.stderr.read().decode())
with tempfile.TemporaryDirectory(prefix='island017-') as d:
 base=pathlib.Path(d);os.chmod(base,0o711)
 ipc=base/'ipc';ipc.mkdir();os.chown(ipc,0,0);os.chmod(ipc,0o1777)
 for role in ('service','witness'):
  x=base/role;x.mkdir();os.chown(x,U[role],G);os.chmod(x,0o700)
 ws=ipc/'w.sock';ss=ipc/'s.sock';wd=base/'witness'/'w.db';pd=base/'witness'/'p.db';sd=base/'service'/'s.db'
 try:
  w=cmd('witness',['authority','--socket',str(ws),'--db',str(wd),'--permit-db',str(pd),'--client-uid',str(U['client']),'--service-uid',str(U['service'])],True);wait(ws,w)
  issued=cmd('client',['permit','--socket',str(ws),'--witness-uid',str(U['witness'])]);results['checks']['direct_client_permit']={'pass':issued.returncode==0,'stderr':issued.stderr[-300:]}
  if issued.returncode!=0:raise RuntimeError('issue: '+issued.stderr)
  token=json.loads(issued.stdout)['token']
  s=cmd('service',['service','--socket',str(ss),'--db',str(sd),'--authority',str(ws),'--client-uid',str(U['client']),'--witness-uid',str(U['witness']),'--recovery-token',token],True);wait(ss,s)
  admitted=cmd('client',['client','--socket',str(ss),'--payload','stage020-e2e']);results['checks']['admission']={'pass':admitted.returncode==0,'stderr':admitted.stderr[-300:],'stdout':admitted.stdout[-400:]}
  for role in ('client','service'):
   f=wd
   probe=subprocess.run([sys.executable,'-c',f'open({str(f)!r},"rb")'],preexec_fn=drop(role),capture_output=True,timeout=5)
   results['checks']['witness_storage_denied_'+role]={'pass':probe.returncode!=0}
  for role in ('client','witness'):
   probe=subprocess.run([sys.executable,'-c',f'open({str(sd)!r},"rb")'],preexec_fn=drop(role),capture_output=True,timeout=5)
   results['checks']['service_storage_denied_'+role]={'pass':probe.returncode!=0}
  results['checks']['socket_owners']={'pass':ws.stat().st_uid==U['witness'] and ss.stat().st_uid==U['service']}
  replay=cmd('service',['service','--socket',str(ipc/'second.sock'),'--db',str(sd),'--authority',str(ws),'--client-uid',str(U['client']),'--witness-uid',str(U['witness']),'--recovery-token',token]);results['checks']['permit_replay_denied']={'pass':replay.returncode!=0}
  os.kill(s.pid,signal.SIGKILL);s.wait(timeout=5);results['checks']['service_sigkill']={'pass':s.returncode==-signal.SIGKILL}
  # Rollback witness to genesis after committed admission; fail-closed recovery.
  os.kill(w.pid,signal.SIGTERM);w.wait(timeout=5)
  for suffix in ('','-journal','-wal','-shm'):
   f=pathlib.Path(str(wd)+suffix)
   if f.exists():f.unlink()
  if ws.exists():ws.unlink()
  w2=cmd('witness',['authority','--socket',str(ws),'--db',str(wd),'--permit-db',str(pd),'--client-uid',str(U['client']),'--service-uid',str(U['service'])],True);wait(ws,w2)
  fresh=cmd('client',['permit','--socket',str(ws),'--witness-uid',str(U['witness'])]);results['checks']['fresh_permit_after_rollback']={'pass':fresh.returncode==0}
  if fresh.returncode==0:
   if ss.exists():ss.unlink() # privileged test orchestrator removes dead socket
   t=json.loads(fresh.stdout)['token']
   rejected=cmd('service',['service','--socket',str(ss),'--db',str(sd),'--authority',str(ws),'--client-uid',str(U['client']),'--witness-uid',str(U['witness']),'--recovery-token',t]);results['checks']['genesis_rollback_denied']={'pass':rejected.returncode!=0,'stderr':rejected.stderr[-300:]}
 except Exception as e:results['error']=repr(e)
 finally:
  for p in procs:
   if p.poll() is None:p.terminate()
  for p in procs:
   try:p.communicate(timeout=3)
   except subprocess.TimeoutExpired:p.kill();p.communicate()
results['limitations']=['No exhaustive production SIGKILL matrix','Root test controller can replace storage','Legacy service UID can still call library API','Witness rollback to genesis is detectable only if local history remains','No independent hardware-backed witness']
(root/'evidence/stage020-multiuid.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
if 'error' in results or not all(v['pass'] for v in results['checks'].values()):sys.exit(1)
