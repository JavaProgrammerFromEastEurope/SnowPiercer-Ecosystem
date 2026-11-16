import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from island.anchored_admission import WitnessServer, AdmissionDenied
from island.production_admission import ProductionAdmissionServer, ProductionAdmissionClient, secure_directory, secure_regular, peer_uid

class Stage010(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name); self.p.chmod(0o700)
    def start_witness(self, limit):
        ready=threading.Event()
        srv=WitnessServer(self.p/'w.sock',self.p/'w.db',{os.getuid()})
        t=threading.Thread(target=srv.serve,kwargs={'ready':ready,'limit':limit})
        t.start(); self.assertTrue(ready.wait(3)); return t
    def test_end_to_end(self):
        wt=self.start_witness(5)
        ready=threading.Event()
        srv=ProductionAdmissionServer(self.p/'p.sock',self.p/'local.db',self.p/'w.sock',{os.getuid()})
        t=threading.Thread(target=srv.serve,kwargs={'ready':ready,'limit':2})
        t.start(); self.assertTrue(ready.wait(3))
        client=ProductionAdmissionClient(self.p/'p.sock')
        self.assertEqual(client.admit(b'a')['sequence'],1)
        self.assertEqual(client.admit(b'b')['sequence'],2)
        t.join(5);wt.join(5)
        self.assertFalse(t.is_alive());self.assertFalse(wt.is_alive())
    def test_denied_uid(self):
        wt=self.start_witness(2)
        ready=threading.Event()
        srv=ProductionAdmissionServer(self.p/'p.sock',self.p/'local.db',self.p/'w.sock',{os.getuid()+100000})
        t=threading.Thread(target=srv.serve,kwargs={'ready':ready,'limit':1});t.start();self.assertTrue(ready.wait(3))
        with self.assertRaises(AdmissionDenied):ProductionAdmissionClient(self.p/'p.sock').admit(b'a')
        from island.anchored_admission import WitnessClient
        WitnessClient(self.p/'w.sock').execute('read')
        t.join(5);wt.join(5)
    def test_symlink_and_permissions(self):
        d=self.p/'unsafe';d.mkdir(mode=0o777);d.chmod(0o777)
        with self.assertRaises(AdmissionDenied):secure_directory(d)
        f=self.p/'real';f.write_bytes(b'x');f.chmod(0o600)
        (self.p/'link').symlink_to(f)
        with self.assertRaises(AdmissionDenied):secure_regular(self.p/'link')
        secure_regular(f)
    def test_startup_fails_without_witness(self):
        srv=ProductionAdmissionServer(self.p/'p.sock',self.p/'local.db',self.p/'missing.sock',{os.getuid()})
        with self.assertRaises(AdmissionDenied):srv.serve(limit=0)
        self.assertFalse((self.p/'p.sock').exists())
    def test_wrong_witness_owner(self):
        path=self.p/'w.sock'
        fake=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            fake.bind(str(path))
            srv=ProductionAdmissionServer(self.p/'p.sock',self.p/'local.db',path,{os.getuid()},witness_uid=os.getuid()+1)
            with self.assertRaises(AdmissionDenied):srv.serve(limit=0)
        finally:
            fake.close()
            if path.exists():path.unlink()
    def test_client_rejects_invalid(self):
        c=ProductionAdmissionClient(self.p/'none')
        for value in ('x',b'x'*4097):
            with self.assertRaises(AdmissionDenied):c.admit(value)
    def test_peercred(self):
        a,b=socket.socketpair()
        try:self.assertEqual(peer_uid(a),os.getuid())
        finally:a.close();b.close()
