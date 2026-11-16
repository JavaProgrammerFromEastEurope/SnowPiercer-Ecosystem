import os,subprocess,time,socket,json,pathlib,signal,sys,tempfile,stat
root=pathlib.Path('/mnt/data/snowpiercer-island-v0.13.0'); evidence=root/'evidence'; U={'client':23001,'service':23002,'witness':23003}; G=23000
base=pathlib.Path(tempfile.mkdtemp(prefix='island-uid-',dir='/tmp'));os.chmod(base,0o755)
for role in U:
 p=base/role;p.mkdir();os.chown(p,U[role],G);os.chmod(p,0o700 if role!='client' else 0o700)
for role in ('service','witness'):
 p=base/(role+'-ipc');p.mkdir();os.chown(p,U[role],G);os.chmod(p,0o711)
def child(role,cmd):
 def drop():os.setgroups([]);os.setgid(G);os.setuid(U[role])
 return subprocess.Popen([sys.executable,'-m','island.multiuid_runtime',*cmd],cwd=root,env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'},preexec_fn=drop,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
w_sock=str(base/'witness-ipc'/'w.sock');s_sock=str(base/'service-ipc'/'s.sock')
w_db=str(base/'witness'/'anchor.db');s_db=str(base/'service'/'local.db')
results={'uids':U,'gid':G,'checks':{},'limitations':[]};procs=[]
def wait(path,proc):
 for _ in range(100):
  if os.path.exists(path):return
  if proc.poll() is not None:break
  time.sleep(.05)
 raise RuntimeError(f'{path} not created; exit {proc.poll()} stderr {proc.stderr.read().decode()}')
try:
 w=child('witness',['witness','--socket',w_sock,'--db',w_db,'--service-uid',str(U['service'])]);procs.append(w);wait(w_sock,w)
 s=child('service',['service','--socket',s_sock,'--db',s_db,'--witness',w_sock,'--client-uid',str(U['client']),'--witness-uid',str(U['witness'])]);procs.append(s);wait(s_sock,s)
 c=child('client',['client','--socket',s_sock,'--payload','hello']);out,err=c.communicate(timeout=12)
 results['checks']['real_client_admit']={'pass':c.returncode==0,'stdout':out.decode(),'stderr':err.decode()}
 for role in ('service','witness'):
  p=child(role,['client','--socket',s_sock,'--payload','unauthorized']);out,err=p.communicate(timeout=12)
  results['checks']['unauthorized_'+role]={'pass':p.returncode!=0,'stderr':err.decode()[-500:]}
 for role in ('client','service'):
  p=base/'witness'/'anchor.db'
  def access():
   def drop():os.setgroups([]);os.setgid(G);os.setuid(U[role])
   return subprocess.run([sys.executable,'-c',f'open({str(p)!r},"rb")'],preexec_fn=drop,capture_output=True,timeout=5)
  r=access();results['checks']['witness_db_denied_'+role]={'pass':r.returncode!=0}
 for role in ('client','witness'):
  p=base/'service'/'local.db'
  def drop():os.setgroups([]);os.setgid(G);os.setuid(U[role])
  r=subprocess.run([sys.executable,'-c',f'open({str(p)!r},"rb")'],preexec_fn=drop,capture_output=True,timeout=5)
  results['checks']['service_db_denied_'+role]={'pass':r.returncode!=0}
 results['checks']['peer_socket_ownership']={'pass':os.stat(s_sock).st_uid==U['service'] and os.stat(w_sock).st_uid==U['witness']}
 # real SIGKILL service; fail-closed socket cleanup needed manually for restart
 os.kill(s.pid,signal.SIGKILL);s.wait(timeout=5)
 results['checks']['real_sigkill_service']={'pass':s.returncode==-signal.SIGKILL}
 results['limitations']=['Only service SIGKILL after successful commit tested; no exhaustive boundary injection','Witness store not protected from privileged host rollback','Legacy API import remains possible under service UID','No independent witness attestation']
finally:
 for p in procs:
  if p.poll() is None:p.terminate()
 for p in procs:
  try:p.communicate(timeout=3)
  except subprocess.TimeoutExpired:p.kill();p.communicate()
 (evidence/'stage012-multiuid.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps(results,indent=2))
