import json, os, socket, subprocess, sys, tempfile, time, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from lifesupport.core.service import LifecycleService, ServiceError, request

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'data/registry.json'

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.private=self.root/'private'; self.private.mkdir(mode=0o700)
        self.db=self.private/'life.db'; self.sock=self.private/'service.sock'; self.proc=None
    def start(self):
        env=dict(os.environ, PYTHONPATH=str(ROOT/'src'))
        self.proc=subprocess.Popen([sys.executable,'-m','lifesupport.service_cli','--registry',str(REG),'--db',str(self.db),'--socket',str(self.sock)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        self.addCleanup(self.stop)
        for _ in range(100):
            if self.sock.exists(): return
            if self.proc.poll() is not None: raise AssertionError(self.proc.stderr.read().decode())
            time.sleep(.02)
        self.fail('service startup timeout')
    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill(); self.proc.communicate(timeout=3)
        self.proc=None
    def test_health(self):
        self.start(); self.assertTrue(request(self.sock)['ok'])
    def test_snapshot(self):
        self.start(); r=request(self.sock,'snapshot'); self.assertTrue(r['ok']); self.assertEqual(len(r['states']),20)
    def test_unsupported_write(self):
        self.start(); self.assertFalse(request(self.sock,'transition')['ok'])
    def test_permissions(self):
        self.start(); self.assertEqual(self.sock.stat().st_mode&0o777,0o600); self.assertEqual(self.db.stat().st_mode&0o777,0o600)
    def test_socket_symlink_rejected(self):
        self.start(); link=self.private/'alias'; link.symlink_to(self.sock); self.assertRaises(ServiceError,request,link)
    def test_insecure_dir_rejected(self):
        self.private.chmod(0o777); self.assertRaises(ServiceError,LifecycleService(REG,self.db,self.sock).serve)
    def test_sigkill_restart_sqlite_reopen(self):
        self.start(); self.assertTrue(request(self.sock)['ok']); self.stop()
        # SIGKILL leaves socket inode: refuse to unlink without operator validation
        self.assertTrue(self.sock.exists()); self.sock.unlink()
        self.start(); self.assertTrue(request(self.sock,'snapshot')['ok'])
    def test_parallel_clients(self):
        self.start()
        with ThreadPoolExecutor(max_workers=12) as pool:
            out=list(pool.map(lambda _:request(self.sock,'health'),range(36)))
        self.assertTrue(all(x['ok'] for x in out))
    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'requires Linux root to test another UID')
    def test_different_uid_denied(self):
        self.start()
        code='import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1])'
        p=subprocess.run([sys.executable,'-c',code,str(self.sock)],preexec_fn=lambda:os.setuid(65534),capture_output=True)
        self.assertNotEqual(p.returncode,0)
