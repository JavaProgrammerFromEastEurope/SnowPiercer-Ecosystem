import json, os, pathlib, socket, sqlite3, subprocess, sys, tempfile, threading, time, unittest
from lifesupport.core.production_write import validate_identity, process_write, ProductionWriteService
from lifesupport.core.service import ServiceError
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.supervised_cross_uid import verified_request

ROOT=pathlib.Path(__file__).resolve().parents[1]

class ProductionWriteUnit(unittest.TestCase):
    def test_root_or_same_uid_rejected(self):
        with self.assertRaises(ServiceError): validate_identity(allowed_uids={os.geteuid()})
    def test_missing_peer_rejected(self):
        a,b=socket.socketpair(); self.addCleanup(a.close); self.addCleanup(b.close)
        b.sendall(b'{"op":"transition"}\n')
        with self.assertRaises(ServiceError): process_write(a,None,allowed_uids={os.geteuid()+1})
    def test_bad_fields_rejected(self):
        a,b=socket.socketpair(); self.addCleanup(a.close); self.addCleanup(b.close)
        b.sendall(b'{"op":"transition","actor":"forged"}\n')
        with self.assertRaises(ServiceError): process_write(a,None,allowed_uids={os.geteuid()})
    def test_bad_transition_args_rejected(self):
        a,b=socket.socketpair(); self.addCleanup(a.close); self.addCleanup(b.close)
        b.sendall(json.dumps({'op':'transition','component_id':'x','next_state':'ACTIVE','event_id':'x','reason':42}).encode()+b'\n')
        with self.assertRaises(ServiceError): process_write(a,None,allowed_uids={os.geteuid()})

@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'Linux root and setuid required')
class ProductionWriteIntegration(unittest.TestCase):
    def setUp(self):
        import shutil
        self.root=pathlib.Path(tempfile.mkdtemp(prefix='life016-',dir='/tmp'))
        self.addCleanup(lambda:shutil.rmtree(self.root,ignore_errors=True))
        self.root.chmod(0o755)
        self.private=self.root/'private';self.private.mkdir(mode=0o700)
        self.public=self.root/'public';self.public.mkdir(mode=0o711)
        self.db=self.private/'life.db';self.sock=self.public/'life.sock'
        self.registry=ROOT/'data/registry.json'
        self.cid=next(iter(Registry.load(self.registry).components))
        lifecycle=HardenedLifecycle(Registry.load(self.registry),self.db)
        try:
            t=lifecycle.acquire('setup',ttl_ns=10_000_000_000)
            lifecycle.protect(t);lifecycle.harden(t);lifecycle.release(t)
        finally:lifecycle.close()
        # Dedicated service identity 65533; separate client identity 65534.
        for p in [self.private,self.public,self.db]:os.chown(p,65533,65533)
        for p in [self.db,pathlib.Path(str(self.db)+'-wal'),pathlib.Path(str(self.db)+'-shm')]:
            if p.exists():os.chown(p,65533,65533);p.chmod(0o600)
        self.env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        self.proc=None
    def start(self):
        cmd=[sys.executable,'-m','lifesupport.production_write_cli','--registry',str(self.registry),'--db',str(self.db),'--socket',str(self.sock),'--uids','65534']
        self.proc=subprocess.Popen(cmd,preexec_fn=lambda:(os.setgid(65533),os.setuid(65533)),env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.stop)
        for _ in range(200):
            if self.proc.poll() is not None:
                err=self.proc.stderr.read().decode();self.fail('service crashed: '+err)
            if self.sock.is_socket():
                try:
                    verified_request(self.sock,expected_uid=65533,expected_pid=self.proc.pid)
                    return
                except (OSError,ServiceError):pass
            time.sleep(.02)
        self.fail('service not ready')
    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate();self.proc.wait(timeout=5)
        if self.proc:
            self.proc.stdout.close();self.proc.stderr.close()
            self.proc=None
    def client(self,request,uid=65534):
        code='''import json,sys,socket
from lifesupport.core.service import _send,_readline
with socket.socket(socket.AF_UNIX) as s:
 s.settimeout(3);s.connect(sys.argv[1]);_send(s,json.loads(sys.argv[2]));print(json.dumps(_readline(s)))'''
        p=subprocess.run([sys.executable,'-c',code,str(self.sock),json.dumps(request)],env=self.env,preexec_fn=lambda:(os.setgid(uid),os.setuid(uid)),capture_output=True,text=True,timeout=6)
        return p
    def transition(self,event_id='evt1',state='INITIALIZING'):
        return {'op':'transition','component_id':self.cid,'next_state':state,'event_id':event_id,'reason':'offline test'}
    def test_real_uid_write_and_dac_denial(self):
        self.start()
        result=self.client(self.transition());self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'],result.stdout)
        read=self.client({'op':'snapshot'});self.assertTrue(json.loads(read.stdout)['ok'])
        code='import sqlite3,sys;sqlite3.connect(sys.argv[1]).execute("SELECT * FROM events").fetchall()'
        denied=subprocess.run([sys.executable,'-c',code,str(self.db)],preexec_fn=lambda:(os.setgid(65534),os.setuid(65534)),capture_output=True)
        self.assertNotEqual(denied.returncode,0)
        self.assertFalse(json.loads(self.client(self.transition('bad'),uid=65532).stdout)['ok'])
        self.stop()
        db=sqlite3.connect(self.db)
        try:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        finally:db.close()
    def test_sigkill_reopen_and_legacy_denial(self):
        import signal
        self.start();self.assertTrue(json.loads(self.client(self.transition()).stdout)['ok'])
        os.kill(self.proc.pid,signal.SIGKILL);self.proc.wait(timeout=5)
        self.proc.stdout.close();self.proc.stderr.close();self.proc=None
        # Stale socket remains. The supervisor must reconcile it; manual test does so here.
        from lifesupport.core.supervised_cross_uid import reconcile_socket
        reconcile_socket(self.sock,service_uid=65533)
        self.start()
        self.assertTrue(json.loads(self.client(self.transition('evt2','STANDBY')).stdout)['ok'])
        self.stop()
        db=sqlite3.connect(self.db)
        try:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        finally:db.close()
        code='from lifesupport.core.persistence import PersistentLifecycle;from lifesupport.core.registry import Registry;import sys; p=PersistentLifecycle(Registry.load(sys.argv[1]),sys.argv[2]);p.transition(sys.argv[3],"ACTIVE",event_id="legacy",reason="x",actor="legacy")'
        denied=subprocess.run([sys.executable,'-c',code,str(self.registry),str(self.db),self.cid],preexec_fn=lambda:(os.setgid(65534),os.setuid(65534)),env=self.env,capture_output=True)
        self.assertNotEqual(denied.returncode,0)

    def test_parallel_clients_one_commit(self):
        from concurrent.futures import ThreadPoolExecutor
        self.start()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda i:self.client(self.transition('parallel-'+str(i))),range(4)))
        success=sum(json.loads(r.stdout).get('ok') is True for r in results)
        self.assertEqual(success,1)
        self.stop()
        db=sqlite3.connect(self.db)
        try:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        finally:db.close()

    def test_unprotected_db_fails_closed(self):
        self.stop()
        self.db.unlink()
        self.start_unprotected_expect_failure()

    def start_unprotected_expect_failure(self):
        cmd=[sys.executable,'-m','lifesupport.production_write_cli','--registry',str(self.registry),'--db',str(self.db),'--socket',str(self.sock),'--uids','65534']
        p=subprocess.run(cmd,preexec_fn=lambda:(os.setgid(65533),os.setuid(65533)),env=self.env,capture_output=True,timeout=5)
        self.assertNotEqual(p.returncode,0)
        self.assertIn(b'v2 protected database required',p.stderr)
