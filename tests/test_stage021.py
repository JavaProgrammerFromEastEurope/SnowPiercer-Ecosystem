import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from island.anchored_admission import AdmissionDenied
from island.write_broker import _identities,WriteBroker,BrokerClient,AdmissionFacade

class BrokerTests(unittest.TestCase):
    def test_distinct_nonroot(self):
        self.assertEqual(_identities(1,2,3,4),(1,2,3,4))
        for args in ((1,2,2,4),(0,2,3,4),(-1,2,3,4),(1,2,3,True)):
            with self.assertRaises(AdmissionDenied):_identities(*args)
    def test_broker_missing_permit(self):
        with patch('island.write_broker.os.geteuid',return_value=3):
            broker=WriteBroker('/missing/broker','/missing/db','/missing/authority',1,2,4)
            with self.assertRaises(AdmissionDenied):broker.serve(None)
    def test_broker_preflight_missing_witness(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('island.write_broker.os.geteuid',return_value=3):
                broker=WriteBroker(str(Path(d)/'broker'),str(Path(d)/'db'),str(Path(d)/'authority'),1,2,4)
            with self.assertRaises(AdmissionDenied):broker.preflight()
    def test_client_rejects_invalid_payload(self):
        client=BrokerClient('/missing',3)
        for value in ('notbytes',b'x'*4097):
            with self.assertRaises(AdmissionDenied):client.admit(value)
    def test_facade_requires_distinct_roles(self):
        with patch('island.write_broker.os.geteuid',return_value=2):
            with self.assertRaises(AdmissionDenied):AdmissionFacade('/a','/b',1,2,4)
