import os,sys,subprocess,tempfile,pathlib,socket,time,signal,json,shutil,sqlite3
from island.crash_protocol import POINTS
from island.anchored_admission import WitnessClient
ROOT=pathlib.Path(__file__).resolve().parents[1]
UID_SERVICE=23002; UID_WITNESS=23003; GID=23000

def run():
 results={'points':{},'other':{},'limitations':[]}
 if os.geteuid()!=0 or not hasattr(socket,'SO_PEERCRED'):
  results['limitations'].append('Requires Linux root test coordinator and SO_PEERCRED')
  return results
 base=pathlib.Path(tempfile.mkdtemp(prefix='island-stage013-'))
 os.chmod(base,0o755)
 try:
  for point in POINTS:
   d=base/point;d.mkdir(mode=0o755)
   wd=d/'w';wd.mkdir();os.chown(wd,UID_WITNESS,GID);os.chmod(wd,0o700)
   sd=d/'s';sd.mkdir();os.chown(sd,UID_SERVICE,GID);os.chmod(sd,0o700)
   ipc=d/'ipc';ipc.mkdir();os.chown(ipc,UID_WITNESS,GID);os.chmod(ipc,0o711)
   sock=str(ipc/'w.sock');db=str(sd/'local.db')
   def spawn(uid,argv):
    def drop():os.setgroups([]);os.setgid(GID);os.setuid(uid)
    return subprocess.Popen([sys.executable,'-m',*argv],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'},preexec_fn=drop,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   w=spawn(UID_WITNESS,['island.multiuid_runtime','witness','--socket',sock,'--db',str(wd/'anchor.db'),'--service-uid',str(UID_SERVICE)])
   try:
    for _ in range(100):
     if os.path.exists(sock):break
     if w.poll() is not None:break
     time.sleep(.03)
    if not os.path.exists(sock):raise RuntimeError('witness failed to start')
    a=spawn(UID_SERVICE,['island.crash_worker','--db',db,'--witness',sock,'--crash-at',point]);out,err=a.communicate(timeout=8)
    r=spawn(UID_SERVICE,['island.crash_worker','--db',db,'--witness',sock,'--mode','recover']);ro,re=r.communicate(timeout=8)
    results['points'][point]={'sigkill':a.returncode==-signal.SIGKILL,'recovery_exit':r.returncode,'recovery_output':ro.decode().strip(),'error':re.decode()[-350:],'pass':a.returncode==-signal.SIGKILL and r.returncode==0}
   finally:
    w.terminate()
    try:w.communicate(timeout=3)
    except subprocess.TimeoutExpired:w.kill();w.communicate()
  # One genuine post-commit rollback-to-genesis attempt: restore old witness DB bytes under witness UID (privileged attacker model)
  d=base/'rollback';d.mkdir(mode=0o755)
  wd=d/'w';wd.mkdir();os.chown(wd,UID_WITNESS,GID);os.chmod(wd,0o700)
  sd=d/'s';sd.mkdir();os.chown(sd,UID_SERVICE,GID);os.chmod(sd,0o700)
  ipc=d/'ipc';ipc.mkdir();os.chown(ipc,UID_WITNESS,GID);os.chmod(ipc,0o711)
  sock=str(ipc/'w.sock');wdb=str(wd/'anchor.db');ldb=str(sd/'local.db')
  def spawn(uid,argv):
   def drop():os.setgroups([]);os.setgid(GID);os.setuid(uid)
   return subprocess.Popen([sys.executable,'-m',*argv],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'},preexec_fn=drop,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  w=spawn(UID_WITNESS,['island.multiuid_runtime','witness','--socket',sock,'--db',wdb,'--service-uid',str(UID_SERVICE)])
  for _ in range(100):
   if os.path.exists(sock):break
   time.sleep(.03)
  WitnessClient(sock).execute('read') if False else None
  # cannot query witness as root due UID allowlist: service worker makes first read
  r=spawn(UID_SERVICE,['island.crash_worker','--db',ldb,'--witness',sock,'--mode','recover']);r.communicate(timeout=8)
  old=pathlib.Path(wdb).read_bytes()
  a=spawn(UID_SERVICE,['island.crash_worker','--db',ldb,'--witness',sock]);ao,ae=a.communicate(timeout=8)
  w.terminate();w.communicate(timeout=4)
  pathlib.Path(sock).unlink(missing_ok=True)
  pathlib.Path(wdb).write_bytes(old);os.chown(wdb,UID_WITNESS,GID)
  w=spawn(UID_WITNESS,['island.multiuid_runtime','witness','--socket',sock,'--db',wdb,'--service-uid',str(UID_SERVICE)])
  for _ in range(100):
   if os.path.exists(sock):break
   time.sleep(.03)
  time.sleep(.15)
  r=spawn(UID_SERVICE,['island.crash_worker','--db',ldb,'--witness',sock,'--mode','recover']);ro,re=r.communicate(timeout=8)
  results['other']['witness_genesis_rollback_denied']={'pass':a.returncode==0 and r.returncode!=0 and b'rollback, witness divergence' in re,'admit_exit':a.returncode,'recovery_exit':r.returncode,'stderr':re.decode()[-300:]}
  w.terminate();w.communicate(timeout=4)
  results['limitations']=['Crash points are in an opt-in worker, not the production IPC service','No independent cross-UID recovery permit protocol','No exhaustive concurrency, socket substitution or legacy production bypass proof','Privileged coordinator can rewrite witness; external anchor not independent','SQLite internal fsync crash points and IPC response transmission are not instrumented']
 finally:
  shutil.rmtree(base,ignore_errors=True)
 return results
if __name__=='__main__':
 result=run();print(json.dumps(result,indent=2));sys.exit(0 if result['points'] and all(v['pass'] for v in result['points'].values()) and all(v['pass'] for v in result['other'].values()) else 1)
