import json
import os
from pathlib import Path
import tempfile
import unittest
from snowpiercer_logistics import SecureLogisticsService, AdmissionError, request

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)/'secure'
        self.uid = os.getuid()
    def tearDown(self): self.t.cleanup()
    def test_phase_rollforward_committed_event(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            before=s._checkpoint()
            s._atomic_json(s.phase_path, {'before':before,'key':'p1','uid':self.uid})
            from snowpiercer_logistics import Principal, Location
            s._db.add_location(Principal('uid:'+str(self.uid),'admin'),'p1',Location('L','warehouse'))
            # Simulated crash window: DB committed, checkpoint not updated.
            s.phase_path.unlink(missing_ok=True) if False else None
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            self.assertEqual(request(s.socket_path,'verify')['result']['events'],1)
            self.assertFalse(s.phase_path.exists())
    def test_phase_uncommitted_discard(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            s._atomic_json(s.phase_path, {'before':s._checkpoint(),'key':'unused','uid':self.uid})
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            self.assertFalse(s.phase_path.exists())
    def test_mismatched_phase_rejected(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            s._atomic_json(s.phase_path, {'before':{'events':42,'head_hash':'bad'},'key':'x','uid':self.uid})
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_bad_command_clears_phase(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            self.assertFalse(request(s.socket_path,'add_container',{'key':'x','item':{'container_id':'x','capacity_kg':-1}})['ok'])
            self.assertFalse(s.phase_path.exists())
            self.assertTrue(request(s.socket_path,'add_container',{'key':'x','item':{'container_id':'x','capacity_kg':10}})['ok'])
if __name__=='__main__': unittest.main()

# OS-level kill after durable commit, before external checkpoint publication.
def _kill_after_commit(root, uid):
    import signal
    from snowpiercer_logistics import Principal, Location
    s = SecureLogisticsService(root,{uid:'admin'})
    s._admit()
    s._atomic_json(s.phase_path, {'before':s._checkpoint(),'key':'kill','uid':uid})
    s._db.add_location(Principal('uid:'+str(uid),'admin'),'kill',Location('K','warehouse'))
    os.kill(os.getpid(),signal.SIGKILL)

class SigkillTests(unittest.TestCase):
    def test_sigkill_postcommit_recovery(self):
        import multiprocessing as mp
        import signal
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'private'
            uid=os.getuid()
            with SecureLogisticsService(root,{uid:'admin'}): pass
            p=mp.Process(target=_kill_after_commit,args=(root,uid))
            p.start(); p.join(8)
            if p.is_alive(): p.kill();p.join();self.fail('child hung')
            self.assertEqual(p.exitcode,-signal.SIGKILL)
            with SecureLogisticsService(root,{uid:'admin'}) as s:
                self.assertEqual(request(s.socket_path,'verify')['result']['events'],1)
