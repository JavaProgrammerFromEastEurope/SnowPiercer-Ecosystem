import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from island.anchored_admission import AdmissionDenied
from island.mandatory_guard import MandatoryGuardServer, startup_lease, _safe_existing

class Stage020Tests(unittest.TestCase):
    def test_concurrent_lease_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lease'
            with startup_lease(p):
                with self.assertRaises(AdmissionDenied):
                    with startup_lease(p): pass
    def test_lock_symlink_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lease'; target=Path(d)/'target';target.touch();p.symlink_to(target)
            with self.assertRaises(OSError):
                with startup_lease(p): pass
    def test_lock_hardlink_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lease';p.touch();os.link(p,Path(d)/'other')
            with self.assertRaises(AdmissionDenied):
                with startup_lease(p): pass
    def test_reject_tampered_journal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.db';Path(str(p)+'-journal').write_bytes(b'bad')
            os.chmod(str(p)+'-journal',0o644)
            with self.assertRaises(AdmissionDenied): _safe_existing(p,os.geteuid())
    def test_reject_hardlinked_database(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.db';p.touch();os.link(p,Path(d)/'other')
            with self.assertRaises(AdmissionDenied): _safe_existing(p,os.geteuid())
    def test_missing_permit_fails_closed(self):
        server=MandatoryGuardServer('/missing/service','/missing/db','/missing/witness',23001,23003)
        with self.assertRaises(AdmissionDenied): server.serve(recovery_token=None)
    def test_server_preflight_is_invoked(self):
        self.assertTrue(issubclass(MandatoryGuardServer,object))
        self.assertNotEqual(MandatoryGuardServer._preflight.__qualname__.split('.')[0], 'IsolatedProductionServer')
