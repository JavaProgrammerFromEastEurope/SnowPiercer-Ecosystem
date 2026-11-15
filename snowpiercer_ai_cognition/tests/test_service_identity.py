import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ai_cognition import (IsolationError, provision_service_layout,
                          verify_service_layout, verify_runtime_identity)

class ServiceIdentityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); self.private=root/'private'; self.sock=root/'socket'
        provision_service_layout(self.private,self.sock)
    def test_modes_and_layout(self):
        self.assertTrue(verify_service_layout(self.private,self.sock))
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode),0o700)
    def test_private_file(self):
        p=self.private/'db'; p.write_bytes(b'1'); p.chmod(0o600)
        self.assertTrue(verify_service_layout(self.private,self.sock))
    def test_exposed_db_fails_closed(self):
        p=self.private/'db'; p.write_bytes(b'1'); p.chmod(0o644)
        with self.assertRaises(IsolationError): verify_service_layout(self.private,self.sock)
    def test_symlink_fails_closed(self):
        (self.private/'link').symlink_to(self.sock)
        with self.assertRaises(IsolationError): verify_service_layout(self.private,self.sock)
    def test_socket_substitution_fails_closed(self):
        (self.sock/'ipc').write_bytes(b'fake')
        with self.assertRaises(IsolationError): verify_service_layout(self.private,self.sock)
    def test_directory_permission_tamper(self):
        self.private.chmod(0o755)
        with self.assertRaises(IsolationError): verify_service_layout(self.private,self.sock)
    def test_reprovision_refuses_existing_files(self):
        (self.private/'key').write_bytes(b'key')
        with self.assertRaises(IsolationError): provision_service_layout(self.private,self.sock)
    def test_wrong_uid_fails(self):
        with self.assertRaises(IsolationError): verify_runtime_identity(os.geteuid()+100000,self.private,self.sock)
    def test_root_service_denied(self):
        if os.geteuid()!=0: self.skipTest('requires root')
        with self.assertRaises(IsolationError): verify_runtime_identity(0,self.private,self.sock)
    def test_actual_cross_uid_denial(self):
        if os.geteuid()!=0: self.skipTest('root required to switch UID')
        script='import os,sys; from pathlib import Path; p=Path(sys.argv[1]);\ntry: p.joinpath("db").write_bytes(b"evil"); sys.exit(1)\nexcept PermissionError: sys.exit(0)'
        proc=subprocess.run([sys.executable,'-c',script,str(self.private)],preexec_fn=lambda:(os.setgroups([]),os.setgid(65534),os.setuid(65534)),capture_output=True,timeout=5)
        self.assertEqual(proc.returncode,0,proc.stderr)
    def test_actual_cross_uid_socket_denial(self):
        if os.geteuid()!=0: self.skipTest('root required to switch UID')
        script='import os,sys; from pathlib import Path; p=Path(sys.argv[1]);\ntry: p.joinpath("ipc").write_bytes(b"fake"); sys.exit(1)\nexcept PermissionError: sys.exit(0)'
        proc=subprocess.run([sys.executable,'-c',script,str(self.sock)],preexec_fn=lambda:(os.setgroups([]),os.setgid(65534),os.setuid(65534)),capture_output=True,timeout=5)
        self.assertEqual(proc.returncode,0,proc.stderr)

class IsolatedServerPreflightTests(unittest.TestCase):
    def test_rejects_root_before_gateway_access(self):
        from ai_cognition import IsolatedAdmissionIPCServer
        with tempfile.TemporaryDirectory() as root:
            private=Path(root)/'private'; sock=Path(root)/'socket'
            provision_service_layout(private,sock)
            with self.assertRaises(IsolationError):
                IsolatedAdmissionIPCServer(None,sock/'ipc',service_uid=0,private_dir=private,
                    socket_dir=sock,allowed_uids=[0],recovery_secret=b'x'*32)
    def test_rejects_socket_outside_directory(self):
        from ai_cognition import IsolatedAdmissionIPCServer
        with tempfile.TemporaryDirectory() as root:
            private=Path(root)/'private'; sock=Path(root)/'socket'
            provision_service_layout(private,sock)
            with self.assertRaises(IsolationError):
                IsolatedAdmissionIPCServer(None,private/'ipc',service_uid=os.geteuid(),
                    private_dir=private,socket_dir=sock,allowed_uids=[os.geteuid()],recovery_secret=b'x'*32)
