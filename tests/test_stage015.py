import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from island.authorized_production import PermitAuthority, AuthorityServer, AuthorityClient, AuthorizedProductionServer, IPC_POINTS
from island.anchored_admission import AdmissionDenied

class Stage015(unittest.TestCase):
    def test_permit_single_use(self):
        with tempfile.TemporaryDirectory() as t:
            a=PermitAuthority(Path(t)/'permits.sqlite',1001,1002)
            token=a.execute(1001,'issue')['token']
            self.assertEqual(len(token),64)
            self.assertTrue(a.execute(1002,'consume',token)['consumed'])
            with self.assertRaises(AdmissionDenied): a.execute(1002,'consume',token)
    def test_unauthorized_issue_and_consume(self):
        with tempfile.TemporaryDirectory() as t:
            a=PermitAuthority(Path(t)/'permits.sqlite',1001,1002)
            with self.assertRaises(AdmissionDenied): a.execute(1002,'issue')
            token=a.execute(1001,'issue')['token']
            with self.assertRaises(AdmissionDenied): a.execute(1001,'consume',token)
            with self.assertRaises(AdmissionDenied): a.execute(1002,'consume','x')
    def test_invalid_same_uid(self):
        with self.assertRaises(AdmissionDenied): PermitAuthority('x',1001,1001)
    def test_unknown_operation(self):
        with tempfile.TemporaryDirectory() as t:
            a=PermitAuthority(Path(t)/'permits.sqlite',1001,1002)
            with self.assertRaises(AdmissionDenied): a.execute(1001,'reset')
    def test_crash_points(self):
        self.assertEqual(len(IPC_POINTS),19)
        self.assertIn('after_ipc_write',IPC_POINTS)
    def test_fail_closed_uid(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'sockdir').mkdir()
            s=AuthorizedProductionServer(p/'sockdir'/'service.sock',p/'local.sqlite',p/'missing.sock',os.geteuid(),os.geteuid())
            with self.assertRaises(AdmissionDenied): s.serve(limit=0)
    def test_reject_invalid_crash_point(self):
        with self.assertRaises(AdmissionDenied): AuthorizedProductionServer('s','d','w',1001,1002,'invalid')
    def test_permit_concurrent_consumption(self):
        with tempfile.TemporaryDirectory() as t:
            a=PermitAuthority(Path(t)/'permits.sqlite',1001,1002)
            token=a.execute(1001,'issue')['token']; results=[]
            def consume():
                try: a.execute(1002,'consume',token); results.append(True)
                except AdmissionDenied: results.append(False)
            threads=[threading.Thread(target=consume) for _ in range(8)]
            for th in threads: th.start()
            for th in threads: th.join()
            self.assertEqual(results.count(True),1)
