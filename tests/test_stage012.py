import os, tempfile, unittest, stat
from pathlib import Path
from island.anchored_admission import AdmissionDenied
from island.deployment_gate import IdentityPolicy,private_directory,private_file,deployment_preflight,verify_legacy_denied

class Stage012(unittest.TestCase):
    def test_uid_policy(self):
        p=IdentityPolicy(12001,12002,12003)
        self.assertEqual(p.witness_uid,12003)
        for uids in ((0,2,3),(1,1,3),(1,2,2),(True,2,3),(-1,2,3)):
            with self.subTest(uids=uids),self.assertRaises(AdmissionDenied): IdentityPolicy(*uids)
    def test_directory_and_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); os.chmod(p,0o700)
            self.assertEqual(private_directory(p,os.geteuid()),p)
            f=p/'db';f.write_bytes(b'db');os.chmod(f,0o600)
            self.assertEqual(private_file(f,os.geteuid()),f)
            os.chmod(f,0o644)
            with self.assertRaises(AdmissionDenied):private_file(f,os.geteuid())
            os.chmod(f,0o600)
            os.link(f,p/'hard')
            with self.assertRaises(AdmissionDenied):private_file(f,os.geteuid())
            (p/'hard').unlink()
            (p/'sym').symlink_to(f)
            with self.assertRaises(AdmissionDenied):private_file(p/'sym',os.geteuid())
            os.chmod(p,0o755)
            with self.assertRaises(AdmissionDenied):private_directory(p,os.geteuid())
    def test_wrong_identity_denied(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AdmissionDenied):deployment_preflight(IdentityPolicy(12001,12002,12003),d,d,d,d)
    def test_legacy_mode(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'db';p.write_bytes(b'');os.chmod(p,0o600)
            self.assertTrue(verify_legacy_denied(p,os.geteuid()+1))
            os.chmod(p,0o604)
            with self.assertRaises(AdmissionDenied):verify_legacy_denied(p,os.geteuid()+1)
    def test_property_modes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'db';p.write_bytes(b'')
            for mode in range(0o1000):
                os.chmod(p,mode)
                if mode & 0o077:
                    with self.assertRaises(AdmissionDenied):private_file(p,os.geteuid())
                else:
                    self.assertEqual(private_file(p,os.geteuid()),p)
