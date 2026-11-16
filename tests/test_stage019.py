import os
import socket
import tempfile
import unittest
from pathlib import Path
from island.production_guard import (inspect_endpoint,assert_endpoint_unchanged,verify_legacy_fence,verify_storage_owner)
from island.anchored_admission import AdmissionDenied

class Stage019Tests(unittest.TestCase):
    def test_owner_private_storage(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'private';f.write_bytes(b'x');f.chmod(0o600)
            self.assertTrue(verify_storage_owner(f,os.geteuid()))
            f.chmod(0o644)
            with self.assertRaises(AdmissionDenied): verify_storage_owner(f,os.geteuid())
    def test_reject_symlink_storage(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'file';f.write_bytes(b'x');f.chmod(0o600)
            s=Path(d)/'link';s.symlink_to(f)
            with self.assertRaises(AdmissionDenied):verify_storage_owner(s,os.geteuid())
    def test_reject_hardlink_storage(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'file';f.write_bytes(b'x');f.chmod(0o600)
            os.link(f,Path(d)/'alias')
            with self.assertRaises(AdmissionDenied):verify_storage_owner(f,os.geteuid())
    def test_reject_untrusted_socket_parent(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'endpoint'
            with socket.socket(socket.AF_UNIX) as s:
                s.bind(str(p))
                with self.assertRaises(AdmissionDenied):inspect_endpoint(p,owner=os.geteuid(),group=os.getegid(),directory=d)
    def test_no_fake_fence(self):
        with self.assertRaises(AdmissionDenied):verify_legacy_fence('/tmp/nonexistent',23001)
    def test_missing_endpoint(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AdmissionDenied):assert_endpoint_unchanged(Path(d)/'missing',type('I',(),{'device':0,'inode':0,'owner':0,'group':0})())
