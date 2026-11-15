import os
import socket
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.stage011 import DeploymentLayout, verify_deployment, verify_legacy_denied
from snowpiercer_logistics.stage010 import IsolationPolicy
from snowpiercer_logistics.secure import AdmissionError

class DeploymentTests(unittest.TestCase):
    def test_layout_refuses_wrong_runtime_uid(self):
        with tempfile.TemporaryDirectory() as d:
            p=IsolationPolicy(os.geteuid()+100, os.geteuid()+101, os.geteuid()+102,(os.geteuid()+103,))
            l=DeploymentLayout(p,d,d,d,d+'/service.sock',d+'/witness.sock',d+'/authority.sock')
            with self.assertRaises(AdmissionError): verify_deployment(l)

    def test_missing_sockets_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=IsolationPolicy(os.geteuid(), os.geteuid()+101, os.geteuid()+102,(os.geteuid()+103,))
            l=DeploymentLayout(p,d,d,d,d+'/service.sock',d+'/witness.sock',d+'/authority.sock')
            with self.assertRaises(AdmissionError): verify_deployment(l)

    def test_symlink_socket_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'sock'; target=Path(d)/'target'
            with socket.socket(socket.AF_UNIX) as s:
                s.bind(str(target))
                path.symlink_to(target)
                p=IsolationPolicy(os.geteuid(),os.geteuid()+101,os.geteuid()+102,(os.geteuid()+103,))
                l=DeploymentLayout(p,d,d,d,str(path),str(target),str(target))
                with self.assertRaises(AdmissionError): verify_deployment(l)

    def test_privileged_legacy_probe_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AdmissionError): verify_legacy_denied(d,service_uid=os.geteuid())

if __name__ == '__main__': unittest.main()
