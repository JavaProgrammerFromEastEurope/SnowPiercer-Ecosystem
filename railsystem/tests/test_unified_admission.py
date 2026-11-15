import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.anchored_admission import initialize, RecoveryRequired, _locked
from railsystem.unified_admission import admit, recover, _tuple
from railsystem.production_fencing import IndependentAnchorUnavailable

class Provider:
    def __init__(self): self.value = (0, '')
    def read(self): return self.value
    def advance(self, old, new):
        if self.value != old: return False
        self.value = new
        return True

class UnifiedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'private'
        self.path.mkdir(mode=0o700)
        initialize(self.path)
    def test_initial_provider(self):
        self.assertEqual(Provider().read(), (0, ''))
    def test_provider_unavailable(self):
        with self.assertRaises(IndependentAnchorUnavailable):
            admit(self.path, baseline={}, attestation={}, trust={}, state_dir=self.path)
    def test_invalid_external_response(self):
        for bad in (None, [0, ''], (True, ''), (-1, ''), (0, 2)):
            with self.subTest(bad=bad), self.assertRaises(ValueError): _tuple(bad)
    def test_recovery_without_prepared(self):
        with self.assertRaises(RecoveryRequired):
            recover(self.path, provider=Provider(), permit={}, recovery_public_key='')
    def test_untrusted_inputs_fail(self):
        with self.assertRaises((ValueError, OSError)):
            admit(self.path, baseline={}, attestation={}, trust={}, state_dir=self.path, provider=Provider())
    def test_lock_file_symlink_rejected(self):
        lock = self.path / 'admission.lock'
        lock.unlink()
        lock.symlink_to(self.path / 'anchor.json')
        with self.assertRaises((ValueError, OSError)):
            with _locked(self.path): pass
    def test_private_directory_required(self):
        os.chmod(self.path, 0o777)
        with self.assertRaises((ValueError, OSError)):
            admit(self.path, baseline={}, attestation={}, trust={}, state_dir=self.path, provider=Provider())
    def test_provider_cas(self):
        p = Provider()
        self.assertTrue(p.advance((0, ''), (1, 'nonce')))
        self.assertFalse(p.advance((0, ''), (2, 'nonce2')))
    def test_missing_provider_recovery(self):
        with self.assertRaises(RecoveryRequired):
            recover(self.path, permit={}, recovery_public_key='')
