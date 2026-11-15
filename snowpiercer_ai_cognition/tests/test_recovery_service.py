import os
import socket
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from ai_cognition import reclaim_stale_socket, production_gateway_only, IsolationError

class RecoveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)/'ipc'; self.directory.mkdir(mode=0o710)
        os.chmod(self.directory,0o710)
        self.path=self.directory/'socket'

    def reclaim(self):
        return reclaim_stale_socket(self.path, service_uid=os.geteuid(), socket_dir=self.directory)

    def test_no_socket(self):
        self.assertFalse(self.reclaim())

    def test_stale_socket(self):
        s=socket.socket(socket.AF_UNIX); s.bind(str(self.path)); s.close()
        self.assertTrue(self.reclaim()); self.assertFalse(self.path.exists())

    def test_live_socket_fenced(self):
        s=socket.socket(socket.AF_UNIX); s.bind(str(self.path)); s.listen(1)
        self.addCleanup(s.close)
        with self.assertRaises(IsolationError): self.reclaim()
        self.assertTrue(self.path.exists())

    def test_symlink_fenced(self):
        self.path.symlink_to('/tmp/target')
        with self.assertRaises(IsolationError): self.reclaim()
        self.assertTrue(self.path.is_symlink())

    def test_regular_file_fenced(self):
        self.path.write_text('not a socket')
        with self.assertRaises(IsolationError): self.reclaim()

    def test_directory_mode_fenced(self):
        os.chmod(self.directory,0o777)
        with self.assertRaises(IsolationError): self.reclaim()

    def test_path_outside_fenced(self):
        with self.assertRaises(IsolationError):
            reclaim_stale_socket(Path(self.tmp.name)/'other',service_uid=os.geteuid(),socket_dir=self.directory)

    def test_production_root_fenced(self):
        if os.geteuid()==0:
            with self.assertRaises(IsolationError): production_gateway_only(gateway=Mock(),service_uid=0)
        else:
            with self.assertRaises(IsolationError): production_gateway_only(gateway=Mock(),service_uid=0)

    def test_production_verifies_gateway(self):
        if os.geteuid()==0: self.skipTest('requires unprivileged UID')
        gw=Mock(); self.assertTrue(production_gateway_only(gateway=gw,service_uid=os.geteuid()))
        gw.verify.assert_called_once()

class CrashRestartTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='posix' and hasattr(socket,'SO_PEERCRED'),'Linux required')
    def test_sigkill_stale_socket_recovery(self):
        import multiprocessing, signal, time
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'ipc'; directory.mkdir(mode=0o710)
            os.chmod(directory,0o710); path=directory/'service.sock'
            ctx=multiprocessing.get_context('fork')
            ready=ctx.Event()
            def serve():
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
                    s.bind(str(path)); s.listen(1); ready.set()
                    while True: time.sleep(1)
            child=ctx.Process(target=serve); child.start()
            try:
                self.assertTrue(ready.wait(4))
                with self.assertRaises(IsolationError):
                    reclaim_stale_socket(path,service_uid=os.geteuid(),socket_dir=directory)
                os.kill(child.pid,signal.SIGKILL); child.join(4)
                self.assertEqual(child.exitcode,-signal.SIGKILL)
                self.assertTrue(reclaim_stale_socket(path,service_uid=os.geteuid(),socket_dir=directory))
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as restarted:
                    restarted.bind(str(path)); restarted.listen(1)
                    self.assertTrue(path.exists())
            finally:
                if child.is_alive(): child.kill(); child.join()
