import os
import tempfile
import threading
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager, AuditCheckpoint,
    AnchoredAdmissionGateway, AdmissionIPCServer, ipc_request, recovery_permit, signed_envelope, RecoveryRequired)
K=b'a'*32; ROOT=b'b'*32; AUTH=b'c'*32; AUDIT=b'd'*32; CHECK=b'e'*32; REC=b'f'*32
OBS={'event_id':'event001','source':'trainos','severity':'warning','description':'ok'}

@unittest.skipUnless(hasattr(__import__('socket'),'SO_PEERCRED'),'Linux SO_PEERCRED required')
class IsolationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root=Path(temp.name); self.store=ReplayStore(str(root/'db')); self.addCleanup(self.store.close)
        manager=HardenedRotationManager(self.store,str(root/'legacy'),{'trainos':K},independent_anchor=IndependentAnchor(root/'independent',ROOT),recovery_secret=AUTH,bootstrap=True)
        manager.provision('trainos')
        self.gw=AnchoredAdmissionGateway(manager,AUDIT,checkpoint=AuditCheckpoint(root/'checkpoint',CHECK),clock=lambda:1000,bootstrap=True)
        self.path=root/'ipc'; self.server=AdmissionIPCServer(self.gw,self.path,allowed_uids=[os.getuid()],recovery_secret=REC,recovery_uids=[os.getuid()])
        ready=threading.Event(); thread=threading.Thread(target=self.server.serve,kwargs={'ready':ready},daemon=True); thread.start()
        self.assertTrue(ready.wait(3))
        self.addCleanup(lambda: (self.server.stop(),thread.join(3)))
    def env(self,nonce='a'*16): return signed_envelope(dict(OBS),1000,nonce,K)
    def test_ipc_admission_and_replay(self):
        self.assertTrue(ipc_request(self.path,{'op':'admit','envelope':self.env()})['ok'])
        self.assertFalse(ipc_request(self.path,{'op':'admit','envelope':self.env()})['ok'])
        self.assertEqual(ipc_request(self.path,{'op':'verify'})['seq'],1)
    def test_denied_uid(self):
        self.server.allowed_uids=frozenset([os.getuid()+100000])
        self.assertFalse(ipc_request(self.path,{'op':'verify'})['ok'])
    def test_denied_recovery_uid(self):
        self.server.recovery_uids=frozenset()
        self.assertFalse(ipc_request(self.path,{'op':'recover','permit':{}})['ok'])
    def test_malformed_and_unsupported(self):
        self.assertFalse(ipc_request(self.path,{'op':'delete'})['ok'])
        self.assertFalse(ipc_request(self.path,{'op':'admit','envelope':{}})['ok'])
    def test_recovery_permit_single_use(self):
        with self.assertRaises(RuntimeError): self.gw.admit(self.env(),fault='after_commit')
        permit=recovery_permit(REC,'recovery-0001',0,'0'*64)
        self.assertTrue(ipc_request(self.path,{'op':'recover','permit':permit})['ok'])
        self.assertFalse(ipc_request(self.path,{'op':'recover','permit':permit})['ok'])
    def test_recovery_invalid_mac(self):
        permit=recovery_permit(REC,'recovery-0002',0,'0'*64); permit['mac']='0'*64
        self.assertFalse(ipc_request(self.path,{'op':'recover','permit':permit})['ok'])
    def test_concurrent_replay(self):
        results=[]
        def attempt(): results.append(ipc_request(self.path,{'op':'admit','envelope':self.env()})['ok'])
        threads=[threading.Thread(target=attempt) for _ in range(8)]
        for t in threads:t.start()
        for t in threads:t.join(5)
        self.assertEqual(results.count(True),1)
    def test_socket_mode(self): self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

def _client_child(path, queue):
    try: queue.put(ipc_request(path,{'op':'verify'}))
    except Exception as exc: queue.put({'error':type(exc).__name__})

def _test_real_child_process_ipc(self):
    import multiprocessing
    ctx=multiprocessing.get_context('spawn'); q=ctx.Queue()
    proc=ctx.Process(target=_client_child,args=(str(self.path),q)); proc.start(); proc.join(10)
    try:
        self.assertEqual(proc.exitcode,0)
        self.assertTrue(q.get(timeout=3)['ok'])
    finally: q.close(); q.join_thread()

IsolationTests.test_real_child_process_ipc = _test_real_child_process_ipc
