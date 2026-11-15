import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage017 import QuarantinedTransactionService, _safe_json_file, production_admission

class Stage017Tests(unittest.TestCase):
    def test_reject_unsafe_phase_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'phase.json'; target=Path(d)/'target'; target.write_text('{}'); p.symlink_to(target)
            with self.assertRaises(OSError): _safe_json_file(p,os.geteuid())
    def test_reject_unsafe_phase_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'phase.json'; p.write_text('{}'); p.chmod(0o644)
            with self.assertRaises(AdmissionError): _safe_json_file(p,os.geteuid())
    def test_quarantine_divergence_and_phase(self):
        with tempfile.TemporaryDirectory() as d:
            s=object.__new__(QuarantinedTransactionService)
            s.phase_path=Path(d)/'phase.json'; s._check_files=Mock(); s._checkpoint=Mock(return_value={'events':1,'head_hash':'a'})
            s._read_witness=Mock(return_value={'events':2,'head_hash':'b'})
            # Explicitly override parent anchor lookup with a mock of the base method.
            from snowpiercer_logistics.secure import SecureLogisticsService
            from unittest.mock import patch
            with patch.object(SecureLogisticsService,'_read_anchor',return_value={'events':1,'head_hash':'a'}):
                self.assertEqual(s.transaction_snapshot().state,'QUARANTINED_DIVERGENCE')
                with self.assertRaises(AdmissionError): s._assert_consistent()
                s.phase_path.write_text('{}'); s.phase_path.chmod(0o600)
                self.assertEqual(s.transaction_snapshot().state,'QUARANTINED_PHASE')
    def test_production_gate_closed(self):
        with self.assertRaises(AdmissionError): production_admission()
