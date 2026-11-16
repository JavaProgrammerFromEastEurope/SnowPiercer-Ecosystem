import os, tempfile, unittest, threading
from pathlib import Path
from island.anchored_admission import AdmissionDenied, WitnessStore, GENESIS
from island.bound_recovery import BoundPermitAuthority
from island.bound_ipc import BoundAuthorityServer, PinnedBoundAuthorityClient, BoundProductionServer

class Stage017(unittest.TestCase):
 def test_authority_uid_policy(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(AdmissionDenied): BoundAuthorityServer(Path(d)/'s',Path(d)/'w',Path(d)/'p',1,1)
 def test_state_binding_replay(self):
  with tempfile.TemporaryDirectory() as d:
   w=WitnessStore(Path(d)/'w'); a=BoundPermitAuthority(Path(d)/'p',101,102,w)
   p=a.issue(101);self.assertEqual(p['digest'],GENESIS)
   self.assertTrue(a.consume(102,p['token'])['consumed'])
   with self.assertRaises(AdmissionDenied): a.consume(102,p['token'])
 def test_stale_head_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   w=WitnessStore(Path(d)/'w');a=BoundPermitAuthority(Path(d)/'p',101,102,w);p=a.issue(101)
   w.execute('cas',{'sequence':1,'previous':GENESIS,'digest':'f'*64})
   with self.assertRaises(AdmissionDenied):a.consume(102,p['token'])
 def test_missing_permit_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   server=BoundProductionServer(Path(d)/'service.sock',Path(d)/'local.db',Path(d)/'witness.sock',101,103)
   with self.assertRaises(AdmissionDenied):server.serve(limit=0)
 def test_peer_pin_rejects_missing_socket(self):
  with tempfile.TemporaryDirectory() as d:
   c=PinnedBoundAuthorityClient(Path(d)/'missing.sock',101)
   with self.assertRaises(OSError):c.execute('issue')
