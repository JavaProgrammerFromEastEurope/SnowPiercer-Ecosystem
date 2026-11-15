"""AI-CORE-020 targeted process lock tests."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ai_cognition.locking020 import acquire_runtime_lock, release_runtime_lock
from ai_cognition.lifecycle import RecoveryRequired
from ai_cognition.service_identity import IsolationError

class RuntimeLock020Tests(unittest.TestCase):
    def test_cross_process_contention_and_release(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); p.chmod(0o700)
            fd = acquire_runtime_lock(p)
            try:
                code = 'import sys; from ai_cognition.locking020 import acquire_runtime_lock; acquire_runtime_lock(sys.argv[1])'
                proc = subprocess.run([sys.executable, '-c', code, str(p)], capture_output=True, text=True, timeout=5)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn('RECOVERY_ALREADY_IN_PROGRESS', proc.stderr)
            finally:
                release_runtime_lock(fd)
            fd = acquire_runtime_lock(p)
            release_runtime_lock(fd)

    def test_symlink_lock_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); p.chmod(0o700)
            (p/'recovery016.lock').symlink_to(p/'target')
            with self.assertRaises(OSError): acquire_runtime_lock(p)

    def test_unsafe_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); p.chmod(0o755)
            with self.assertRaises(IsolationError): acquire_runtime_lock(p)
