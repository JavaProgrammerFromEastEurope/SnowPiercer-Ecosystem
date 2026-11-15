import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from snowpiercer_logistics.secure import AdmissionError, SecureLogisticsService
from snowpiercer_logistics.stage018 import classify_recovery, EvidenceGatedLogisticsService, production_admission

A={'events':0,'head_hash':'a'*64}
B={'events':1,'head_hash':'b'*64}
C={'events':2,'head_hash':'c'*64}
P={'before':A,'key':'command-1','uid':123}

class Stage018Tests(unittest.TestCase):
    def test_committed_and_divergent(self):
        self.assertTrue(classify_recovery(A,A,A).permitted)
        self.assertEqual(classify_recovery(B,A,A).state,'QUARANTINED_DIVERGENCE')
        self.assertFalse(classify_recovery(B,A,A).permitted)
    def test_phase_boundary_matrix(self):
        cases=[(A,A,A,'QUARANTINED_UNCOMMITTED_PHASE'),
               (B,A,A,'QUARANTINED_SQLITE_COMMITTED'),
               (B,A,B,'QUARANTINED_WITNESS_ADVANCED'),
               (B,A,C,'QUARANTINED_SPLIT_BRAIN'),
               (B,B,B,'QUARANTINED_PHASE_ANCHOR')]
        for ledger,local,witness,state in cases:
            with self.subTest(state=state):
                result=classify_recovery(ledger,local,witness,P)
                self.assertEqual(result.state,state)
                self.assertFalse(result.permitted)
    def test_reject_invalid_anchor_and_phase(self):
        for bad in (None,{}, {'events':True,'head_hash':'a'*64}, {'events':0,'head_hash':'BAD'}):
            with self.subTest(bad=bad), self.assertRaises(AdmissionError):
                classify_recovery(bad,A,A)
        with self.assertRaises(AdmissionError):
            classify_recovery(A,A,A,{'before':A,'key':'x'})
    def test_service_quarantine_phase(self):
        with tempfile.TemporaryDirectory() as d:
            service=object.__new__(EvidenceGatedLogisticsService)
            service.phase_path=Path(d)/'phase.json'
            service._check_files=Mock()
            service._checkpoint=Mock(return_value=A)
            service._read_witness=Mock(return_value=A)
            with patch.object(SecureLogisticsService,'_read_anchor',return_value=A):
                self.assertTrue(service.recovery_decision().permitted)
                service.phase_path.write_text('{"before":{"events":0,"head_hash":"'+ 'a'*64 +'"},"key":"x","uid":1}')
                service.phase_path.chmod(0o600)
                with self.assertRaises(AdmissionError): service._assert_consistent()
    def test_production_gate_closed(self):
        with self.assertRaises(AdmissionError): production_admission()
