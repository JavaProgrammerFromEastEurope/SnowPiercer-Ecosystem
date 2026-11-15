import os, pathlib, socket, sqlite3, subprocess, sys, tempfile, unittest
from lifesupport.core.cross_uid import authorize_peer, validate_cross_uid_storage, serve_authorized_connection
from lifesupport.core.service import ServiceError

class CrossUIDTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.p=pathlib.Path(self.t.name); self.d=self.p/'private'; self.d.mkdir(mode=0o700)
        self.db=self.d/'life.db'
    def test_reject_same_uid(self):
        with self.assertRaises(ServiceError): validate_cross_uid_storage(self.db,service_uid=os.geteuid(),client_uid=os.geteuid())
    def test_private_storage(self):
        self.assertTrue(validate_cross_uid_storage(self.db,service_uid=os.geteuid(),client_uid=os.geteuid()+1))
    def test_directory_mode(self):
        self.d.chmod(0o750)
        with self.assertRaises(ServiceError): validate_cross_uid_storage(self.db,service_uid=os.geteuid(),client_uid=os.geteuid()+1)
    def test_symlink_db(self):
        self.db.symlink_to(self.p/'target')
        with self.assertRaises(ServiceError): validate_cross_uid_storage(self.db,service_uid=os.geteuid(),client_uid=os.geteuid()+1)
    def test_sidecar_mode(self):
        pathlib.Path(str(self.db)+'-wal').write_bytes(b'x')
        with self.assertRaises(ServiceError): validate_cross_uid_storage(self.db,service_uid=os.geteuid(),client_uid=os.geteuid()+1)
    def test_uid_allowlist(self):
        a,b=socket.socketpair(); self.addCleanup(a.close); self.addCleanup(b.close)
        if not hasattr(socket,'SO_PEERCRED'): self.skipTest('Linux only')
        self.assertEqual(authorize_peer(a,allowed_uids={os.geteuid()}),os.geteuid())
        with self.assertRaises(ServiceError): authorize_peer(a,allowed_uids={os.geteuid()+1})
    def test_invalid_allowlist(self):
        a,b=socket.socketpair(); self.addCleanup(a.close); self.addCleanup(b.close)
        with self.assertRaises(ServiceError): authorize_peer(a,allowed_uids={})
    def test_write_rejected(self):
        a,b=socket.socketpair(); self.addCleanup(a.close); self.addCleanup(b.close)
        b.sendall(b'{"op":"transition"}\n')
        with self.assertRaises(ServiceError): serve_authorized_connection(a,object(),allowed_uids={os.geteuid()})
    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'requires Linux root')
    def test_real_cross_uid_dac(self):
        self.db.write_bytes(b'protected'); self.db.chmod(0o600)
        code='import pathlib,sys; pathlib.Path(sys.argv[1]).read_bytes()'
        result=subprocess.run([sys.executable,'-c',code,str(self.db)],preexec_fn=lambda:os.setuid(65534),capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'PermissionError',result.stderr)
    def test_sigkill_before_sqlite_commit(self):
        # Transactional crash: inserted row must roll back when child is SIGKILLed.
        self.db.touch(mode=0o600)
        conn=sqlite3.connect(self.db); conn.execute('CREATE TABLE t(x INTEGER)'); conn.commit(); conn.close()
        code='import sqlite3,sys,os,signal; c=sqlite3.connect(sys.argv[1]); c.execute("BEGIN IMMEDIATE"); c.execute("INSERT INTO t VALUES(1)"); os.kill(os.getpid(),signal.SIGKILL)'
        p=subprocess.run([sys.executable,'-c',code,str(self.db)],capture_output=True)
        self.assertEqual(p.returncode,-9)
        c=sqlite3.connect(self.db)
        try: self.assertEqual(c.execute('SELECT count(*) FROM t').fetchone()[0],0)
        finally: c.close()
    def test_sigkill_after_sqlite_commit(self):
        self.db.touch(mode=0o600)
        conn=sqlite3.connect(self.db); conn.execute('CREATE TABLE t(x INTEGER)'); conn.commit(); conn.close()
        code='import sqlite3,sys,os,signal; c=sqlite3.connect(sys.argv[1]); c.execute("INSERT INTO t VALUES(1)"); c.commit(); os.kill(os.getpid(),signal.SIGKILL)'
        p=subprocess.run([sys.executable,'-c',code,str(self.db)],capture_output=True)
        self.assertEqual(p.returncode,-9)
        c=sqlite3.connect(self.db)
        try: self.assertEqual(c.execute('SELECT count(*) FROM t').fetchone()[0],1)
        finally: c.close()

class CrossUIDServiceIntegration(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'requires Linux root and alternate UID')
    def test_real_cross_uid_ipc_and_write_denial(self):
        from lifesupport.core.cross_uid import AuthorizedLifecycleService
        import threading, time
        root=pathlib.Path(tempfile.mkdtemp(prefix='life014-',dir='/tmp'))
        self.addCleanup(lambda:__import__('shutil').rmtree(root,ignore_errors=True))
        root.chmod(0o755)
        private=root/'db'; private.mkdir(mode=0o700)
        public=root/'ipc'; public.mkdir(mode=0o711)
        sock=public/'life.sock'
        reg=pathlib.Path(__file__).resolve().parents[1]/'data/registry.json'
        service=AuthorizedLifecycleService(reg,private/'life.db',sock,allowed_uids={65534})
        stop=threading.Event()
        th=threading.Thread(target=lambda:service.serve(stop_event=stop),daemon=True)
        th.start()
        self.addCleanup(lambda:(stop.set(),th.join(timeout=3)))
        for _ in range(100):
            if sock.exists(): break
            time.sleep(.02)
        self.assertTrue(sock.exists())
        code='from lifesupport.core.cross_uid import cross_uid_request; import sys,json; print(json.dumps(cross_uid_request(sys.argv[1],sys.argv[2])))'
        env=dict(os.environ,PYTHONPATH=str(pathlib.Path(__file__).resolve().parents[1]/'src'))
        def run(op):
            return subprocess.run([sys.executable,'-c',code,str(sock),op],preexec_fn=lambda:os.setuid(65534),env=env,capture_output=True,text=True,timeout=4)
        r=run('health'); self.assertEqual(r.returncode,0,r.stderr); self.assertIn('"ok": true',r.stdout)
        r=run('transition'); self.assertEqual(r.returncode,0,r.stderr); self.assertIn('"ok": false',r.stdout)
        r=run('snapshot'); self.assertEqual(r.returncode,0,r.stderr); self.assertIn('"ok": true',r.stdout)
        # Root is deliberately NOT an authorized client despite running service as root.
        from lifesupport.core.cross_uid import cross_uid_request
        self.assertFalse(cross_uid_request(sock)['ok'])
