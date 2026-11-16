import os, tempfile, unittest, socket, multiprocessing, pathlib
from island.production_fencing import check_private_directory, check_private_file, pinned_lock, verify_peer, PinnedWitnessClient, HardenedProductionServer, PinnedProductionClient
from island.anchored_admission import AdmissionDenied

class TestGeo010(unittest.TestCase):
    def test_private_directory(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'private'; p.mkdir(mode=0o700)
            self.assertEqual(check_private_directory(p,os.geteuid()),p)
            p.chmod(0o755)
            with self.assertRaises(AdmissionDenied): check_private_directory(p,os.geteuid())
    def test_private_file(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'file'; p.write_bytes(b'a'); p.chmod(0o600)
            check_private_file(p,os.geteuid())
            q=pathlib.Path(t)/'hardlink'; os.link(p,q)
            with self.assertRaises(AdmissionDenied): check_private_file(p,os.geteuid())
    def test_symlink_lock(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'lock'; target=pathlib.Path(t)/'target'; target.touch(); p.symlink_to(target)
            with self.assertRaises(OSError):
                with pinned_lock(p,os.geteuid()): pass
    def test_lock_inode_replacement(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'lock'
            with self.assertRaises(AdmissionDenied):
                with pinned_lock(p,os.geteuid()):
                    p.unlink(); p.write_text('replaced')
    def test_peer_identity(self):
        a,b=socket.socketpair()
        try:
            self.assertEqual(verify_peer(a,os.geteuid()),os.geteuid())
            with self.assertRaises(AdmissionDenied): verify_peer(a,os.geteuid()+10000)
        finally: a.close(); b.close()
    def test_separate_uids(self):
        with self.assertRaises(AdmissionDenied): HardenedProductionServer('/x','/y','/z',{42},43,42)
        with self.assertRaises(AdmissionDenied): HardenedProductionServer('/x','/y','/z',{42},43,43)
    def test_witness_uid_validation(self):
        with self.assertRaises(AdmissionDenied): PinnedWitnessClient('/missing',-1)
    def test_missing_endpoint(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(OSError): PinnedProductionClient(t+'/absent',os.geteuid()).admit(b'abc')
    def test_invalid_payload(self):
        with self.assertRaises(AdmissionDenied): PinnedProductionClient('/missing',os.geteuid()).admit('bad')
    def test_missing_witness(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(OSError): PinnedWitnessClient(t+'/missing',os.geteuid()).execute('read')
    def test_lock_reuse(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'lock'
            for _ in range(20):
                with pinned_lock(p,os.geteuid()): self.assertTrue(p.exists())
