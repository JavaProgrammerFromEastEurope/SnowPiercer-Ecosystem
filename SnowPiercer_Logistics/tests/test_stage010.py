import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.stage010 import (IsolationPolicy, require_private_directory,
                                              verify_isolated_deployment)
from snowpiercer_logistics.secure import AdmissionError

class IsolationPreflightTests(unittest.TestCase):
    def test_distinct_uids(self):
        self.assertTrue(IsolationPolicy(1001,1002,1003,(1004,1005)).validate())
        with self.assertRaises(AdmissionError):
            IsolationPolicy(1001,1002,1003,(1001,)).validate()

    def test_missing_or_invalid_identities(self):
        for p in [IsolationPolicy(1,2,3,()), IsolationPolicy(0,2,3,(4,)),
                  IsolationPolicy(1,2,3,(4,4)), IsolationPolicy(True,2,3,(4,))]:
            with self.subTest(p=p), self.assertRaises(AdmissionError): p.validate()

    def test_symlink_and_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'private'; p.mkdir(mode=0o700)
            self.assertTrue(require_private_directory(p, os.geteuid()))
            link=Path(d)/'link'; link.symlink_to(p, target_is_directory=True)
            with self.assertRaises(AdmissionError): require_private_directory(link, os.geteuid())
            p.chmod(0o755)
            with self.assertRaises(AdmissionError): require_private_directory(p, os.geteuid())

    def test_runtime_uid_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            policy=IsolationPolicy(os.geteuid()+10000, os.geteuid()+10001,
                                   os.geteuid()+10002,(os.geteuid()+10003,))
            with self.assertRaisesRegex(AdmissionError, 'runtime UID'):
                verify_isolated_deployment(policy,service_root=d,witness_root=d,authority_root=d)

if __name__ == '__main__': unittest.main()
