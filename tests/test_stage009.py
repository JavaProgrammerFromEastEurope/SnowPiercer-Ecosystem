import os,sys,tempfile,threading,subprocess,unittest,random,sqlite3,socket,time
from pathlib import Path
from island.anchored_admission import WitnessStore,WitnessServer,WitnessClient,AnchoredAdmission,AdmissionDenied,chain,digest,GENESIS

class Stage009(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.store=WitnessStore(self.base/'witness.db')
        self.client=self.store
        self.admission=AnchoredAdmission(self.base/'local.db',self.client)
    def test_witness_cas(self):
        self.assertEqual(self.store.execute('read')['sequence'],0)
        h=chain(GENESIS,1,digest(b'one'))
        self.store.execute('cas',{'sequence':1,'previous':GENESIS,'digest':h})
        self.assertEqual(self.store.execute('read')['sequence'],1)
        self.store.execute('cas',{'sequence':1,'previous':GENESIS,'digest':h})
        with self.assertRaises(AdmissionDenied): self.store.execute('cas',{'sequence':1,'previous':GENESIS,'digest':'f'*64})
    def test_replay(self):
        a=self.admission.admit(b'one'); b=self.admission.admit(b'one')
        self.assertNotEqual(a['digest'],b['digest']); self.assertEqual(b['sequence'],2)
    def test_rollback(self):
        self.admission.admit(b'a')
        (self.base/'local.db').unlink()
        with self.assertRaises(AdmissionDenied): self.admission.recover()
    def test_witness_rollback(self):
        self.admission.admit(b'a'); (self.base/'witness.db').unlink()
        with self.assertRaises(AdmissionDenied): self.admission.recover()
    def test_tamper(self):
        self.admission.admit(b'a')
        db=sqlite3.connect(self.base/'local.db')
        try:
            db.execute("UPDATE accepted SET digest=?",('f'*64,)); db.commit()
        finally: db.close()
        with self.assertRaises(AdmissionDenied): self.admission.recover()
    def test_concurrency(self):
        errors=[]; seq=[]
        def worker(i):
            try: seq.append(self.admission.admit(str(i).encode())['sequence'])
            except Exception as e: errors.append(repr(e))
        threads=[threading.Thread(target=worker,args=(i,)) for i in range(12)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(errors,[]); self.assertEqual(sorted(seq),list(range(1,13)))
    def test_crash_recovery(self):
        for crash,code in [('phase',91),('witness',92),('local',93)]:
            script='import sys; from island.anchored_admission import *; AnchoredAdmission(sys.argv[1],WitnessStore(sys.argv[2])).admit(b"test",crash_at=sys.argv[3])'
            p=subprocess.run([sys.executable,'-c',script,str(self.base/'local.db'),str(self.base/'witness.db'),crash],capture_output=True)
            self.assertEqual(p.returncode,code,p.stderr)
            state=self.admission.recover()
            self.assertEqual(state,self.store.execute('read'))
    def test_ipc(self):
        path=self.base/'w.sock'; server=WitnessServer(path,self.base/'remote.db',{os.getuid()}); ready=threading.Event()
        t=threading.Thread(target=server.serve,kwargs={'ready':ready,'limit':2});t.start();self.assertTrue(ready.wait(3))
        try:
            client=WitnessClient(path);self.assertEqual(client.execute('read')['sequence'],0)
            h=chain(GENESIS,1,digest(b'x'))
            self.assertEqual(client.execute('cas',{'sequence':1,'previous':GENESIS,'digest':h})['sequence'],1)
        finally:t.join(5)
        self.assertFalse(t.is_alive())
    def test_uid_rejection(self):
        path=self.base/'deny.sock';server=WitnessServer(path,self.base/'deny.db',set()); ready=threading.Event()
        t=threading.Thread(target=server.serve,kwargs={'ready':ready,'limit':1});t.start();self.assertTrue(ready.wait(3))
        try:
            with self.assertRaises(AdmissionDenied):WitnessClient(path).execute('read')
        finally:t.join(5)
    def test_property_chain(self):
        rng=random.Random(8008)
        for i in range(1000):
            h=digest(rng.randbytes(12));prev=digest(rng.randbytes(8))
            self.assertEqual(len(chain(prev,i+1,h)),64)
            self.assertNotEqual(chain(prev,i+1,h),chain(prev,i+2,h))
    def test_no_go(self):
        self.assertEqual(self.admission.admit(b'x')['engineering_approval'],'BLOCKED/NO-GO')
