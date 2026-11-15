import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.permit_authority import RecoveryPermitAuthority, permit_request
from snowpiercer_logistics.secure import AdmissionError

class Stage007Tests(unittest.TestCase):
    def test_issue_consume_replay(self):
        with tempfile.TemporaryDirectory() as d:
            uid=os.geteuid()
            with RecoveryPermitAuthority(Path(d),uid,uid) as authority:
                scope='recovery-test'
                permit=permit_request(authority.socket_path,'issue',scope=scope,target_uid=uid)['permit']
                self.assertTrue(permit_request(authority.socket_path,'consume',scope=scope,permit=permit)['consumed'])
                with self.assertRaises(AdmissionError):
                    permit_request(authority.socket_path,'consume',scope=scope,permit=permit)
    def test_scope_mismatch_does_not_consume(self):
        with tempfile.TemporaryDirectory() as d:
            uid=os.geteuid()
            with RecoveryPermitAuthority(d,uid,uid) as a:
                token=permit_request(a.socket_path,'issue',scope='a',target_uid=uid)['permit']
                with self.assertRaises(AdmissionError): permit_request(a.socket_path,'consume',scope='b',permit=token)
                self.assertTrue(permit_request(a.socket_path,'consume',scope='a',permit=token)['consumed'])
    def test_uid_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            uid=os.geteuid()
            with RecoveryPermitAuthority(d,uid+1,uid) as a:
                with self.assertRaises(AdmissionError): permit_request(a.socket_path,'issue',scope='x',target_uid=uid)
    def test_restart_preserves_consumption(self):
        with tempfile.TemporaryDirectory() as d:
            uid=os.geteuid()
            with RecoveryPermitAuthority(d,uid,uid) as a:
                token=permit_request(a.socket_path,'issue',scope='x',target_uid=uid)['permit']
                permit_request(a.socket_path,'consume',scope='x',permit=token)
            with RecoveryPermitAuthority(d,uid,uid) as a:
                with self.assertRaises(AdmissionError): permit_request(a.socket_path,'consume',scope='x',permit=token)
