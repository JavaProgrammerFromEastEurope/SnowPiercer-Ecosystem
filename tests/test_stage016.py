import os,sqlite3,tempfile,threading,unittest
from pathlib import Path
from island.bound_recovery import BoundPermitAuthority,assert_legacy_fenced
from island.anchored_admission import AdmissionDenied,WitnessStore,GENESIS
class Stage016(unittest.TestCase):
 def setup_authority(self,d):
  w=WitnessStore(Path(d)/'w.sqlite');a=BoundPermitAuthority(Path(d)/'p.sqlite',12001,12002,w);return w,a
 def test_state_bound_one_shot(self):
  with tempfile.TemporaryDirectory() as d:
   w,a=self.setup_authority(d);p=a.issue(12001);self.assertEqual(p['digest'],GENESIS)
   self.assertTrue(a.consume(12002,p['token'])['consumed'])
   with self.assertRaises(AdmissionDenied):a.consume(12002,p['token'])
 def test_stale_state_denied(self):
  with tempfile.TemporaryDirectory() as d:
   w,a=self.setup_authority(d);p=a.issue(12001)
   w.execute('cas',{'sequence':1,'previous':GENESIS,'digest':'a'*64})
   with self.assertRaises(AdmissionDenied):a.consume(12002,p['token'])
 def test_uid_auth(self):
  with tempfile.TemporaryDirectory() as d:
   w,a=self.setup_authority(d)
   with self.assertRaises(AdmissionDenied):a.issue(12002)
   p=a.issue(12001)
   with self.assertRaises(AdmissionDenied):a.consume(12001,p['token'])
   self.assertTrue(a.consume(12002,p['token'])['consumed'])
 def test_concurrent_consume(self):
  with tempfile.TemporaryDirectory() as d:
   w,a=self.setup_authority(d);p=a.issue(12001);results=[]
   def f():
    try:a.consume(12002,p['token']);results.append(True)
    except AdmissionDenied:results.append(False)
   threads=[threading.Thread(target=f) for _ in range(6)]
   for t in threads:t.start()
   for t in threads:t.join()
   self.assertEqual(results.count(True),1)
 def test_reject_invalid_policy(self):
  with tempfile.TemporaryDirectory() as d:
   w=WitnessStore(Path(d)/'w.sqlite')
   for x,y in ((0,2),(1,1),(True,2)):
    with self.assertRaises(AdmissionDenied):BoundPermitAuthority(Path(d)/'p.sqlite',x,y,w)
 def test_legacy_fence_preflight(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'local';b=p/'witness';a.mkdir();b.mkdir();os.chmod(a,0o700);os.chmod(b,0o700)
   self.assertTrue(assert_legacy_fenced(12001,os.geteuid(),12003,a,b) if os.geteuid()!=0 else True)
   with self.assertRaises(AdmissionDenied):assert_legacy_fenced(12001,12002,12003,a,b)
