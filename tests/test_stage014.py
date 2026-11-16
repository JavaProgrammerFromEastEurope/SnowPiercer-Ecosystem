import unittest,tempfile,pathlib,subprocess,sys,os
from island.crash_protocol import POINTS,killpoint,CrashInstrumentedAdmission
from island.anchored_admission import AdmissionDenied,WitnessStore
class Stage013Tests(unittest.TestCase):
 def test_points_unique(self):self.assertEqual(len(POINTS),len(set(POINTS)))
 def test_unknown_point_rejected(self):
  with self.assertRaises(AdmissionDenied):killpoint('a','not-a-point')
 def test_invalid_crash_at_rejected_before_io(self):
  with tempfile.TemporaryDirectory() as d:
   a=CrashInstrumentedAdmission(pathlib.Path(d)/'a.db',WitnessStore(pathlib.Path(d)/'w.db'))
   with self.assertRaises(AdmissionDenied):a.admit(b'data',crash_at='invalid')
 def test_legacy_api_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   from island.anchored_admission import AnchoredAdmission
   a=AnchoredAdmission(pathlib.Path(d)/'a.db',WitnessStore(pathlib.Path(d)/'w.db'))
   self.assertEqual(a.admit(b'legacy')['sequence'],1)
   self.assertEqual(a.recover()['sequence'],1)
 def test_readiness_no_go(self):
  with tempfile.TemporaryDirectory() as d:
   a=CrashInstrumentedAdmission(pathlib.Path(d)/'a.db',WitnessStore(pathlib.Path(d)/'w.db'))
   self.assertEqual(a.admit(b'data')['engineering_approval'],'BLOCKED/NO-GO')
if __name__=='__main__':unittest.main()
