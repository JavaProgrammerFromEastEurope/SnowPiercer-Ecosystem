import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import tempfile
import unittest
from snowpiercer_logistics import SecureLogisticsService, AdmissionError, request


def contender(root, queue):
    try:
        with SecureLogisticsService(root,{os.getuid():'admin'}):
            queue.put('admitted')
    except AdmissionError:
        queue.put('denied')

class Stage004Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'secure'
        self.uid=os.getuid()
    def tearDown(self): self.tmp.cleanup()
    def test_cross_process_lock(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}):
            q=mp.Queue(); p=mp.Process(target=contender,args=(self.root,q))
            p.start();p.join(5)
            self.assertFalse(p.is_alive())
            self.assertEqual(q.get(timeout=2),'denied')
            q.close();q.join_thread()
    def test_phase_symlink_runtime_rejected(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}) as s:
            s.phase_path.symlink_to(s.anchor_path)
            result=request(s.socket_path,'add_location',{'key':'k','item':{'location_id':'a','kind':'w'}})
            self.assertFalse(result['ok'])
            self.assertEqual(result['error'],'AdmissionError')
    def test_anchor_tamper_detected(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}): pass
        (self.root/'checkpoint.json').write_text(json.dumps({'events':5,'head_hash':'bad'}))
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_lock_symlink_rejected(self):
        self.root.mkdir(mode=0o700)
        (self.root/'service.lock').symlink_to(self.root/'target')
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
    def test_phase_orphan_without_anchor(self):
        with SecureLogisticsService(self.root,{self.uid:'admin'}): pass
        (self.root/'checkpoint.json').unlink()
        (self.root/'phase.json').write_text('{}')
        with self.assertRaises(AdmissionError): SecureLogisticsService(self.root,{self.uid:'admin'}).start()
