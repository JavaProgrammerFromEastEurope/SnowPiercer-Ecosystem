import os, pathlib, socket, sqlite3, subprocess, sys, tempfile, threading, time, unittest
from lifesupport.core.service import ServiceError
from lifesupport.core.supervised_cross_uid import verified_request, reconcile_socket, CrossUIDSupervisor

class SupervisedCrossUIDTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
    def test_reject_unconnected_socket(self):
        with self.assertRaises(OSError): verified_request(self.root/'missing',expected_uid=os.geteuid())
    def test_reject_fake_server_uid(self):
        p=self.root/'socket'
        listener=socket.socket(socket.AF_UNIX); listener.bind(str(p)); listener.listen(1)
        self.addCleanup(listener.close)
        with self.assertRaisesRegex(ServiceError,'identity mismatch'):
            verified_request(p,expected_uid=os.geteuid()+1)
    def test_reject_fake_server_pid(self):
        p=self.root/'socket'
        listener=socket.socket(socket.AF_UNIX); listener.bind(str(p)); listener.listen(1)
        self.addCleanup(listener.close)
        with self.assertRaisesRegex(ServiceError,'identity mismatch'):
            verified_request(p,expected_uid=os.geteuid(),expected_pid=os.getpid()+10000)
    def test_reject_symlink(self):
        p=self.root/'socket'; p.symlink_to(self.root/'target')
        with self.assertRaises(ServiceError): reconcile_socket(p,service_uid=os.geteuid())
    def test_reject_regular_file(self):
        p=self.root/'socket'; p.write_bytes(b'')
        with self.assertRaises(ServiceError): reconcile_socket(p,service_uid=os.geteuid())
    def test_reconcile_stale_socket(self):
        p=self.root/'socket'
        with socket.socket(socket.AF_UNIX) as s:
            s.bind(str(p)); os.chmod(p,0o666)
        reconcile_socket(p,service_uid=os.geteuid())
        self.assertFalse(p.exists())
    def test_reject_live_socket(self):
        p=self.root/'socket'
        with socket.socket(socket.AF_UNIX) as s:
            s.bind(str(p)); os.chmod(p,0o666); s.listen(1)
            with self.assertRaises(ServiceError): reconcile_socket(p,service_uid=os.geteuid())
    def test_same_uid_supervisor_rejected(self):
        s=CrossUIDSupervisor('x','y','z',allowed_uids={os.geteuid()})
        with self.assertRaises(ServiceError): s.run(max_restarts=0)
    def test_sqlite_concurrent_commit_crash(self):
        db=self.root/'db.sqlite'
        c=sqlite3.connect(db); c.execute('CREATE TABLE t(x INTEGER UNIQUE)'); c.commit(); c.close()
        script='''import sqlite3,sys,os,signal,time
c=sqlite3.connect(sys.argv[1],timeout=4); c.execute('BEGIN IMMEDIATE'); c.execute('INSERT INTO t VALUES(?)',(int(sys.argv[2]),));
if sys.argv[3]=='kill': os.kill(os.getpid(),signal.SIGKILL)
c.commit(); c.close()'''
        jobs=[subprocess.Popen([sys.executable,'-c',script,str(db),str(i),'kill' if i%2 else 'commit']) for i in range(8)]
        codes=[p.wait(timeout=10) for p in jobs]
        self.assertEqual(codes.count(0),4); self.assertEqual(codes.count(-9),4)
        c=sqlite3.connect(db)
        try:
            self.assertEqual([r[0] for r in c.execute('SELECT x FROM t ORDER BY x')],[0,2,4,6])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        finally:c.close()
    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'Linux root required')
    def test_supervised_real_cross_uid_sigkill(self):
        import shutil, signal
        root=pathlib.Path(tempfile.mkdtemp(prefix='life015-',dir='/tmp'))
        self.addCleanup(lambda:shutil.rmtree(root,ignore_errors=True))
        root.chmod(0o755)
        private=root/'db'; private.mkdir(mode=0o700)
        public=root/'ipc'; public.mkdir(mode=0o711)
        reg=pathlib.Path(__file__).resolve().parents[1]/'data/registry.json'
        sock=public/'life.sock'
        s=CrossUIDSupervisor(reg,private/'life.db',sock,allowed_uids={65534})
        t=threading.Thread(target=lambda:s.run(max_restarts=1,poll=.02),daemon=True)
        t.start(); self.addCleanup(lambda:(s.stop(),t.join(timeout=3)))
        def ready():
            for _ in range(200):
                try:
                    if s.child and verified_request(sock,expected_uid=0,expected_pid=s.child.pid).get('error')=='unauthorized peer UID': return s.child.pid
                except (OSError,ServiceError,ValueError): pass
                time.sleep(.02)
            self.fail('service did not become ready')
        first=ready()
        code='from lifesupport.core.supervised_cross_uid import verified_request; import sys,json; print(json.dumps(verified_request(sys.argv[1],sys.argv[2],expected_uid=0)))'
        env=dict(os.environ,PYTHONPATH=str(pathlib.Path(__file__).resolve().parents[1]/'src'))
        def client(op):
            return subprocess.run([sys.executable,'-c',code,str(sock),op],preexec_fn=lambda:os.setuid(65534),env=env,capture_output=True,text=True,timeout=5)
        self.assertIn('"ok": true',client('health').stdout)
        self.assertIn('"ok": false',client('transition').stdout)
        os.kill(first,signal.SIGKILL)
        second=ready_after(first,s,ready)
        self.assertNotEqual(first,second)
        self.assertIn('"ok": true',client('snapshot').stdout)
        s.stop(); t.join(timeout=5)

def ready_after(first,s,ready):
    for _ in range(200):
        if s.child is not None and s.child.pid!=first: return ready()
        time.sleep(.02)
    raise AssertionError('no restart')
