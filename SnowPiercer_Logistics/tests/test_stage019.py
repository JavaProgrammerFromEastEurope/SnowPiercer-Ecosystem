import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage019 import TransactionAdmissionService, _socket_inode, inspect_transaction, production_admission

A={'events':0,'head_hash':'a'*64}

class Stage019Tests(unittest.TestCase):
    def test_socket_type_and_symlink_fencing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sock'
            p.write_text('unsafe')
            with self.assertRaises(AdmissionError): _socket_inode(p)
            p.unlink()
            with socket.socket(socket.AF_UNIX) as s:
                s.bind(str(p)); os.chmod(p,0o600)
                self.assertEqual(_socket_inode(p)[2],os.geteuid())
                alias=Path(d)/'alias'; alias.symlink_to(p)
                with self.assertRaises(AdmissionError): _socket_inode(alias)
                os.chmod(p,0o666)
                with self.assertRaises(AdmissionError): _socket_inode(p)
    def test_distinct_endpoints(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[str(Path(d)/f'{i}.sock') for i in range(2)]
            with socket.socket(socket.AF_UNIX) as a, socket.socket(socket.AF_UNIX) as b:
                a.bind(paths[0]); b.bind(paths[1]); os.chmod(paths[0],0o600); os.chmod(paths[1],0o600)
                obj=object.__new__(TransactionAdmissionService)
                obj.witness_socket,obj.permit_socket=paths
                obj._assert_endpoints()
                obj.permit_socket=paths[0]
                with self.assertRaises(AdmissionError): obj._assert_endpoints()
    def test_read_only_snapshot(self):
        obj=Mock()
        obj.recovery_decision.return_value=Mock(state='COMMITTED',permitted=True,ledger=A,checkpoint=A,witness=A,phase_present=False)
        self.assertTrue(inspect_transaction(obj)['permitted'])
        obj.recovery_decision.assert_called_once_with()
    def test_legacy_and_production_denied(self):
        obj=object.__new__(TransactionAdmissionService)
        with self.assertRaises(AdmissionError): obj._dispatch(100,{'action':'issue_permit','args':{}})
        with self.assertRaises(AdmissionError): production_admission()
