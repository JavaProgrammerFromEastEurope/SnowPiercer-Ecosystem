import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from railsystem.anchored_admission import initialize, recover, admit_anchored, RecoveryRequired, AdmissionError, _locked, _read_anchor

class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / 'state'
        self.p.mkdir(mode=0o700)
        initialize(self.p)

    def test_initial(self):
        self.assertEqual(_read_anchor(self.p/'anchor.json')['sequence'], 0)
    def test_no_reset(self):
        with self.assertRaises(AdmissionError): initialize(self.p)
    def test_missing_attestation(self):
        with self.assertRaises(Exception): admit_anchored(self.p, baseline={}, attestation={}, trust={}, state_dir=self.p)
    def test_no_recovery_without_pending(self):
        with self.assertRaises(RecoveryRequired): recover(self.p, permit='a'*32)
    def test_short_permit(self):
        with self.assertRaises(AdmissionError): recover(self.p, permit='short')
    def test_symlink_anchor(self):
        (self.p/'anchor.json').unlink()
        (self.p/'anchor.json').symlink_to('/etc/passwd')
        with self.assertRaises(AdmissionError): _read_anchor(self.p/'anchor.json')
    def test_tampered_anchor(self):
        (self.p/'anchor.json').write_text('{"sequence": 99, "nonce": "fake"}')
        with self.assertRaises(RecoveryRequired): admit_anchored(self.p, baseline={}, attestation={}, trust={}, state_dir=self.p)
    def test_nonprivate_directory(self):
        self.p.chmod(0o755)
        with self.assertRaises(AdmissionError): initialize(self.p)
    def test_lock_is_exclusive(self):
        with _locked(self.p):
            code = "from railsystem.anchored_admission import _locked; from pathlib import Path;\nwith _locked(Path(__import__('sys').argv[1])): pass"
            p = subprocess.Popen([sys.executable, '-c', code, str(self.p)], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                with self.assertRaises(subprocess.TimeoutExpired): p.communicate(timeout=.25)
            finally:
                p.kill(); p.communicate()
    def test_recover_prepared_without_anchor_advance(self):
        import sqlite3
        conn = sqlite3.connect(self.p/'admission.sqlite3')
        conn.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='n' WHERE id=1")
        conn.commit(); conn.close()
        with self.assertRaises(RecoveryRequired): admit_anchored(self.p, baseline={}, attestation={}, trust={}, state_dir=self.p)
        self.assertEqual(recover(self.p, permit='a'*32)['sequence'], 0)
        with self.assertRaises(RecoveryRequired): recover(self.p, permit='b'*32)
    def test_recover_prepared_after_anchor_advance(self):
        import sqlite3
        from railsystem.anchored_admission import _atomic_anchor
        conn = sqlite3.connect(self.p/'admission.sqlite3')
        conn.execute("UPDATE state SET phase='PREPARED',pending_sequence=2,pending_nonce='newnonce' WHERE id=1")
        conn.commit(); conn.close()
        _atomic_anchor(self.p/'anchor.json', {'sequence':2, 'nonce':'newnonce'})
        self.assertEqual(recover(self.p, permit='a'*32)['sequence'], 2)
        with self.assertRaises(AdmissionError): recover(self.p, permit='a'*32)
    def test_ambiguous_anchor(self):
        import sqlite3
        from railsystem.anchored_admission import _atomic_anchor
        conn = sqlite3.connect(self.p/'admission.sqlite3')
        conn.execute("UPDATE state SET phase='PREPARED',pending_sequence=2,pending_nonce='n' WHERE id=1")
        conn.commit(); conn.close()
        _atomic_anchor(self.p/'anchor.json', {'sequence':3, 'nonce':'x'})
        with self.assertRaises(RecoveryRequired): recover(self.p, permit='a'*32)

if __name__ == '__main__': unittest.main()
