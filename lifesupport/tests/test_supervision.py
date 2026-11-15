import os, signal, socket, stat, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from lifesupport.core.supervision import ServiceSupervisor, ServiceError, _safe_stale_socket, validate_production_paths
from lifesupport.core.service import request
ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'data/registry.json'

class SupervisionTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.d=Path(t.name)/'private'; self.d.mkdir(mode=0o700)
        self.db=self.d/'life.db'; self.sock=self.d/'life.sock'
    def test_production_same_uid_denied(self):
        with self.assertRaises(ServiceError):validate_production_paths(self.db,self.sock,service_uid=os.geteuid(),client_uid=os.geteuid())
    def test_production_other_uid_path_accepted(self):
        self.assertTrue(validate_production_paths(self.db,self.sock,service_uid=os.geteuid(),client_uid=os.geteuid()+1))
    def test_production_symlink_db_denied(self):
        self.db.symlink_to(self.d/'target')
        with self.assertRaises(ServiceError):validate_production_paths(self.db,self.sock,service_uid=os.geteuid(),client_uid=os.geteuid()+1)
    def test_production_sidecar_denied(self):
        self.db.with_name('life.db-wal').write_text('x')
        os.chmod(self.d/'life.db-wal',0o644)
        with self.assertRaises(ServiceError):validate_production_paths(self.db,self.sock,service_uid=os.geteuid(),client_uid=os.geteuid()+1)
    def test_socket_symlink_denied(self):
        self.sock.symlink_to(self.d/'other')
        with self.assertRaises(ServiceError):_safe_stale_socket(self.sock)
    def test_regular_socket_path_denied(self):
        self.sock.write_text('x')
        with self.assertRaises(ServiceError):_safe_stale_socket(self.sock)
    def test_live_socket_not_unlinked(self):
        with socket.socket(socket.AF_UNIX) as s:
            s.bind(str(self.sock)); os.chmod(self.sock,0o600); s.listen(1)
            with self.assertRaises(ServiceError):_safe_stale_socket(self.sock)
            self.assertTrue(self.sock.exists())
    def test_stale_socket_removed(self):
        with socket.socket(socket.AF_UNIX) as s:s.bind(str(self.sock)); os.chmod(self.sock,0o600)
        _safe_stale_socket(self.sock); self.assertFalse(self.sock.exists())
    def test_supervisor_sigkill_restarts(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        cmd=[sys.executable,'-m','lifesupport.supervisor_cli','--registry',str(REG),'--db',str(self.db),'--socket',str(self.sock)]
        p=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            first=None
            for _ in range(150):
                try:
                    r=request(self.sock); first=r['pid']; break
                except Exception:time.sleep(.025)
            self.assertIsNotNone(first)
            os.kill(first,signal.SIGKILL)
            second=None
            for _ in range(200):
                try:
                    r=request(self.sock)
                    if r.get('ok') and r['pid']!=first:second=r['pid'];break
                except Exception:pass
                time.sleep(.025)
            if second is None and p.poll() is not None: print("SUPERVISOR STDERR",p.stderr.read().decode())
            self.assertIsNotNone(second, p.poll())
            self.assertTrue(request(self.sock,'snapshot')['ok'])
        finally:
            p.terminate()
            try:p.communicate(timeout=4)
            except subprocess.TimeoutExpired:p.kill();p.communicate()
    def test_second_supervisor_lock_denied(self):
        fd=os.open(self.d/'.life-supervisor.lock',os.O_CREAT|os.O_RDWR,0o600)
        import fcntl
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            with self.assertRaises(ServiceError):ServiceSupervisor(REG,self.db,self.sock).run(max_restarts=0)
        finally:os.close(fd)
