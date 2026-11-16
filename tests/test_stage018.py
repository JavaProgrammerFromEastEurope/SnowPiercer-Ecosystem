import os
import socket
import tempfile
import unittest
from pathlib import Path
from island.socket_isolation import SocketIsolationPolicy,verify_isolated_layout,deny_legacy_access
from island.anchored_admission import AdmissionDenied

class SocketIsolationTests(unittest.TestCase):
    def test_identity_rejects_duplicate(self):
        with self.assertRaises(AdmissionDenied): SocketIsolationPolicy(1001,1001,1003,1002,1003).validate()
    def test_identity_rejects_root(self):
        with self.assertRaises(AdmissionDenied): SocketIsolationPolicy(0,1002,1003,1002,1003).validate()
    def test_private_layout_rejects_public_ipc_owner(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d); (a/'s').mkdir();(a/'w').mkdir();(a/'ipc').mkdir()
            p=SocketIsolationPolicy(1001,1002,1003,1002,1003)
            with self.assertRaises(AdmissionDenied): verify_isolated_layout(p,service_private=a/'s',witness_private=a/'w',ipc_directory=a/'ipc')
    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d);(a/'real').mkdir();(a/'alias').symlink_to(a/'real')
            p=SocketIsolationPolicy(1001,1002,1003,1002,1003)
            with self.assertRaises(AdmissionDenied): verify_isolated_layout(p,service_private=a/'alias',witness_private=a/'real',ipc_directory=a/'real')
    def test_reject_fake_probe(self):
        with self.assertRaises(AdmissionDenied): deny_legacy_access('/tmp/does-not-matter',1001)
    @unittest.skipUnless(os.geteuid()==0 and hasattr(os,'setuid'),'requires root Linux')
    def test_real_uid_probe(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); os.chmod(root,0o711)
            f=root/'db';f.write_text('private');os.chmod(f,0o600)
            code='import os,sys;from island.socket_isolation import deny_legacy_access;print(deny_legacy_access(sys.argv[1],23001))'
            def drop(): os.setgroups([]);os.setgid(23001);os.setuid(23001)
            env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
            result=subprocess.run([sys.executable,'-c',code,str(f)],env=env,preexec_fn=drop,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('True',result.stdout)
