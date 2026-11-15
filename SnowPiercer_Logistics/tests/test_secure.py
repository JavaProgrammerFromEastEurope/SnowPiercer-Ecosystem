import multiprocessing as mp
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from snowpiercer_logistics import SecureLogisticsService, AdmissionError, request


def kill_after_commit(root):
    import os
    from snowpiercer_logistics import SecureLogisticsService
    s=SecureLogisticsService(root,{os.getuid():'admin'})
    s._admit()
    s._db.add_location(__import__('snowpiercer_logistics').Principal('uid:'+str(os.getuid()),'admin'),'k',__import__('snowpiercer_logistics').Location('L','warehouse'))
    os._exit(137)

class SecureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'private'
        self.uid=os.getuid()
    def tearDown(self): self.tmp.cleanup()
    def test_admission_replay_and_permissions(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as svc:
            path=svc.socket_path
            x=request(path,'add_container',{'key':'a','item':{'container_id':'box','capacity_kg':50}})
            self.assertTrue(x['ok'],x)
            self.assertEqual(x,request(path,'add_container',{'key':'a','item':{'container_id':'box','capacity_kg':50}}))
            self.assertFalse(request(path,'add_container',{'key':'a','item':{'container_id':'other','capacity_kg':50}})['ok'])
            self.assertEqual(request(path,'verify')['result']['events'],1)
        with SecureLogisticsService(self.root,{self.uid:'auditor'}) as svc:
            self.assertFalse(request(svc.socket_path,'add_location',{'key':'bad','item':{'location_id':'x','kind':'w'}})['ok'])
            self.assertTrue(request(svc.socket_path,'verify')['ok'])
    def test_permit_one_time(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as svc:
            token=request(svc.socket_path,'issue_permit',{'uid':self.uid})['result']['permit']
            self.assertTrue(request(svc.socket_path,'recover',{'permit':token})['ok'])
            self.assertFalse(request(svc.socket_path,'recover',{'permit':token})['ok'])
            self.assertFalse(request(svc.socket_path,'recover',{'permit':'wrong'})['ok'])
    def test_unmapped_uid_denied(self):
        with SecureLogisticsService(self.root,{self.uid+100000:'admin'}) as svc:
            self.assertFalse(request(svc.socket_path,'verify')['ok'])
    def test_second_server_denied(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}):
            with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_socket_substitution_denied(self):
        self.root.mkdir(mode=0o700)
        (self.root/'service.sock').write_text('not a socket')
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_symlink_db_denied(self):
        self.root.mkdir(mode=0o700)
        (self.root/'ledger.sqlite').symlink_to(self.root/'outside')
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_missing_anchor_denied(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as svc:
            self.assertTrue(request(svc.socket_path,'add_location',{'key':'a','item':{'location_id':'L','kind':'w'}})['ok'])
        (self.root/'checkpoint.json').unlink()
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_sigkill_commit_before_anchor(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}): pass
        p=mp.Process(target=kill_after_commit,args=(self.root,))
        p.start();p.join(10)
        self.assertEqual(p.exitcode,137)
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_rollback_detected(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as svc:
            self.assertTrue(request(svc.socket_path,'add_location',{'key':'a','item':{'location_id':'L','kind':'w'}})['ok'])
        from contextlib import closing
        with closing(sqlite3.connect(self.root/'ledger.sqlite')) as db:
            with db:
                db.execute('DELETE FROM events');db.execute('DELETE FROM commands');db.execute('DELETE FROM locations')
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()

if __name__=='__main__':unittest.main()
