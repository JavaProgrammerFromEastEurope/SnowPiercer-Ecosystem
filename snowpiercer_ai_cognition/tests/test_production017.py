"""AI-CORE-017: enforce legacy executable fencing without breaking imports."""
import subprocess
import sys
import unittest
from ai_cognition.production013 import create_service, load_config
from ai_cognition.production012 import ProductionAdmissionIPCServer

class Production017Tests(unittest.TestCase):
    def test_legacy_013_cli_fenced(self):
        p = subprocess.run([sys.executable, '-m', 'ai_cognition.production013', 'invalid'],
                           capture_output=True, text=True, timeout=8)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('LEGACY_PRODUCTION_ENTRYPOINT_DISABLED', p.stderr)

    def test_legacy_012_cli_fenced(self):
        p = subprocess.run([sys.executable, '-m', 'ai_cognition.production012', 'invalid:factory'],
                           capture_output=True, text=True, timeout=8)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('LEGACY_PRODUCTION_ENTRYPOINT_DISABLED', p.stderr)

    def test_legacy_library_import_compatibility(self):
        self.assertTrue(callable(create_service))
        self.assertTrue(callable(load_config))
        self.assertTrue(issubclass(ProductionAdmissionIPCServer, object))
