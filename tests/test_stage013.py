import os, socket, tempfile, unittest
from pathlib import Path
from island.stage012 import require_linux_multiuid,check_private_tree,peer_identity
from island.anchored_admission import AdmissionDenied

class Stage013(unittest.TestCase):
    def test_identity(self):
        self.assertTrue(require_linux_multiuid(12001,12002,12003))
        for a in ((0,2,3),(1,1,3),(1,2,2),(-1,2,3),(True,2,3)):
            with self.subTest(a=a),self.assertRaises(AdmissionDenied):require_linux_multiuid(*a)
    def test_private_tree(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);os.chmod(p,0o700)
            self.assertTrue(check_private_tree(p,os.geteuid()))
            f=p/'local.sqlite';f.write_bytes(b'data');os.chmod(f,0o600)
            self.assertTrue(check_private_tree(p,os.geteuid()))
            os.chmod(f,0o644)
            with self.assertRaises(AdmissionDenied):check_private_tree(p,os.geteuid())
            os.chmod(f,0o600);(p/'alias').symlink_to(f)
            with self.assertRaises(AdmissionDenied):check_private_tree(p,os.geteuid())
    def test_real_peer_uid(self):
        if not hasattr(socket,'SO_PEERCRED'):self.skipTest('Linux only')
        a,b=socket.socketpair()
        try:
            self.assertEqual(peer_identity(a,os.geteuid()),os.geteuid())
            with self.assertRaises(AdmissionDenied):peer_identity(a,os.geteuid()+1)
        finally:a.close();b.close()
    def test_modes_property(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for mode in range(0o1000):
                os.chmod(p,mode)
                if mode & 0o077:
                    with self.assertRaises(AdmissionDenied):check_private_tree(p,os.geteuid())
                else:self.assertTrue(check_private_tree(p,os.geteuid()))
