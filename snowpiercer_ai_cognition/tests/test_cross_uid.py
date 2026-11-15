import multiprocessing
import os
import signal
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager,
    AuditCheckpoint, AnchoredAdmissionGateway, CrossUIDAdmissionService,
    verify_cross_uid_layout, supervise_process, ipc_request, IsolationError)

K=b'a'*32; ROOT=b'b'*32; AUTH=b'c'*32; AUDIT=b'd'*32; CHECK=b'e'*32; REC=b'f'*32

def child_verify(path, uid, gid, queue):
    try:
        if os.geteuid()==0:
            os.setgroups([]); os.setgid(gid); os.setuid(uid)
        queue.put(ipc_request(path, {'op':'verify'}))
    except Exception as exc:
        queue.put({'error':type(exc).__name__})

def child_read_private(path, uid, gid, queue):
    try:
        os.setgroups([]); os.setgid(gid); os.setuid(uid)
        with open(path,'rb') as f: f.read(1)
        queue.put('ACCESS_GRANTED')
    except Exception as exc: queue.put(type(exc).__name__)

def killed_child():
    os.kill(os.getpid(),signal.SIGKILL)

def successful_child():
    return None

class CrossUIDTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name); self.private=self.root/'private'; self.public=self.root/'public'
        self.private.mkdir(mode=0o700); self.public.mkdir(mode=0o710)
        os.chmod(self.private,0o700); os.chmod(self.public,0o710)
    def test_layout(self):
        self.assertTrue(verify_cross_uid_layout(self.private,self.public,service_uid=os.geteuid(),ipc_gid=os.getegid()) if os.geteuid()!=0 else True)
    def test_bad_group(self):
        if os.geteuid()==0: self.skipTest('root not service')
        with self.assertRaises(IsolationError): verify_cross_uid_layout(self.private,self.public,service_uid=os.geteuid(),ipc_gid=os.getegid()+1)
    def test_symlink_rejected(self):
        if os.geteuid()==0: self.skipTest('root not service')
        (self.private/'evil').symlink_to('/etc/passwd')
        with self.assertRaises(IsolationError): verify_cross_uid_layout(self.private,self.public,service_uid=os.geteuid(),ipc_gid=os.getegid())
    def test_restart_budget(self):
        ctx=multiprocessing.get_context('fork')
        attempts=[0]
        def factory():
            attempts[0]+=1
            return ctx.Process(target=killed_child if attempts[0]==1 else successful_child)
        self.assertEqual(supervise_process(factory,stop_event=threading.Event(),max_restarts=2,delay=0),1)
    def test_restart_exhaustion(self):
        ctx=multiprocessing.get_context('fork')
        with self.assertRaisesRegex(RuntimeError,'RESTART_BUDGET'):
            supervise_process(lambda:ctx.Process(target=killed_child),stop_event=threading.Event(),max_restarts=1,delay=0)
    @unittest.skipUnless(os.geteuid()==0 and hasattr(__import__('socket'),'SO_PEERCRED'),'root Linux required')
    def test_cross_uid_end_to_end(self):
        import pwd
        service_uid=65534; client_uid=65533; group=65532
        os.chown(self.root,service_uid,group); os.chmod(self.root,0o711)
        os.chown(self.private,service_uid,group); os.chown(self.public,service_uid,group)
        # Run the entire service in a separate process with dropped privileges.
        ctx=multiprocessing.get_context('fork'); ready=ctx.Event(); stop=ctx.Event()
        def serve():
            os.setgroups([]); os.setgid(group); os.setuid(service_uid)
            store=ReplayStore(str(self.private/'db'))
            try:
                manager=HardenedRotationManager(store,str(self.private/'legacy'),{'trainos':K},independent_anchor=IndependentAnchor(self.private/'independent',ROOT),recovery_secret=AUTH,bootstrap=True)
                manager.provision('trainos')
                gw=AnchoredAdmissionGateway(manager,AUDIT,checkpoint=AuditCheckpoint(self.private/'checkpoint',CHECK),clock=lambda:1000,bootstrap=True)
                for entry in self.private.iterdir():
                    if entry.is_file(): os.chmod(entry,0o600)
                server=CrossUIDAdmissionService(gw,self.public/'ipc',private_dir=self.private,socket_dir=self.public,service_uid=service_uid,ipc_gid=group,allowed_uids=[client_uid],recovery_secret=REC)
                server.serve(ready=ready)
            finally: store.close()
        proc=ctx.Process(target=serve); proc.start()
        try:
            self.assertTrue(ready.wait(5),'service startup failed')
            q=ctx.Queue(); client=ctx.Process(target=child_verify,args=(str(self.public/'ipc'),client_uid,group,q)); client.start(); client.join(5)
            self.assertEqual(client.exitcode,0); self.assertTrue(q.get(timeout=2).get('ok'))
            q.close(); q.join_thread()
            q2=ctx.Queue(); denied=ctx.Process(target=child_verify,args=(str(self.public/'ipc'),client_uid,group+1,q2)); denied.start(); denied.join(5)
            self.assertFalse(q2.get(timeout=2).get('ok',False)); q2.close(); q2.join_thread()
            self.assertEqual(stat.S_IMODE((self.public/'ipc').stat().st_mode),0o660)
            self.assertEqual(stat.S_IMODE((self.private/'db').stat().st_mode),0o600)
            q3=ctx.Queue(); direct=ctx.Process(target=child_read_private,args=(str(self.private/'db'),client_uid,group,q3)); direct.start(); direct.join(5)
            self.assertEqual(q3.get(timeout=2),'PermissionError'); q3.close(); q3.join_thread()
            proc.kill(); proc.join(5)
            self.assertEqual(proc.exitcode,-signal.SIGKILL)
        finally:
            if proc.is_alive(): proc.kill(); proc.join()
