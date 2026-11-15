"""Stage 017: atomic receipts, cross-UID IPC and real SIGKILL fault injection."""
import json,os,pathlib,signal,socket,sqlite3,subprocess,sys,time,unittest
from lifesupport.core.reconciled_write import apply_request,ProductionWriteSupervisor
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.registry import Registry
from lifesupport.core.service import ServiceError
from test_production_write import ProductionWriteIntegration, ROOT

class ReconciliationUnit(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=pathlib.Path(self.temp.name)/'test.db'
        self.registry=Registry.load(ROOT/'data/registry.json')
        self.cid=next(iter(self.registry.components))
        self.life=HardenedLifecycle(self.registry,self.path);self.addCleanup(self.life.close)
        t=self.life.acquire('setup',ttl_ns=10_000_000_000)
        self.life.protect(t);self.life.harden(t);self.life.release(t)
    def req(self,rid='request-1',event='evt-1',state='INITIALIZING'):
        return dict(op='transition',request_id=rid,component_id=self.cid,next_state=state,event_id=event,reason='test')
    def test_retry_same_request_one_event(self):
        a=apply_request(self.life,self.req(),42);b=apply_request(self.life,self.req(),42)
        self.assertFalse(a['replayed']);self.assertTrue(b['replayed'])
        self.assertEqual(a['sequence'],b['sequence'])
        self.assertEqual(self.life.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
    def test_conflicting_payload_rejected(self):
        apply_request(self.life,self.req(),42)
        with self.assertRaises(ServiceError):apply_request(self.life,self.req(event='different'),42)
    def test_cross_uid_receipt_conflict(self):
        apply_request(self.life,self.req(),42)
        with self.assertRaises(ServiceError):apply_request(self.life,self.req(),43)
    def test_before_commit_fault_rolls_back(self):
        def fault(phase):
            if phase=='before_commit': raise RuntimeError('injected crash')
        with self.assertRaises(RuntimeError):apply_request(self.life,self.req(),42,fault=fault)
        self.assertEqual(self.life.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
        self.assertTrue(apply_request(self.life,self.req(),42)['ok'])
    def test_after_commit_fault_reconciles(self):
        def fault(phase):
            if phase=='after_commit': raise RuntimeError('lost response')
        with self.assertRaises(RuntimeError):apply_request(self.life,self.req(),42,fault=fault)
        self.assertTrue(apply_request(self.life,self.req(),42)['replayed'])
    def test_sigkill_during_atomic_event_receipt(self):
        code="""import json,os,signal,sys
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.reconciled_write import apply_request
r=Registry.load(sys.argv[1]);l=HardenedLifecycle(r,sys.argv[2])
try:
 def fault(phase):
  if phase==sys.argv[3]:os.kill(os.getpid(),signal.SIGKILL)
 apply_request(l,json.loads(sys.argv[4]),42,fault=fault)
finally:l.close()
"""
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        for phase,expected in [('before_commit',0),('after_commit',1)]:
            db_path=pathlib.Path(self.temp.name)/(phase+'.db')
            with HardenedLifecycle(self.registry,db_path) as life:
                token=life.acquire('setup',ttl_ns=10_000_000_000)
                life.protect(token);life.harden(token);life.release(token)
            request=self.req(rid='kill-'+phase,event='event-'+phase)
            p=subprocess.run([sys.executable,'-c',code,str(ROOT/'data/registry.json'),str(db_path),phase,json.dumps(request)],env=env,capture_output=True,timeout=8)
            self.assertEqual(p.returncode,-signal.SIGKILL,p.stderr.decode())
            with HardenedLifecycle(self.registry,db_path) as life:
                self.assertEqual(life.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],expected)
                if phase=='before_commit': time.sleep(2.1)  # crashed lease expires
                result=apply_request(life,request,42)
                self.assertEqual(result['replayed'],bool(expected))
                self.assertEqual(life.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

    def test_invalid_request_no_receipt(self):
        with self.assertRaises(ServiceError):apply_request(self.life,{'op':'transition'},42)
        with self.assertRaises(ServiceError):apply_request(self.life,self.req(),0)
    def test_reopen_reconcile(self):
        apply_request(self.life,self.req(),42);self.life.close()
        self.life=HardenedLifecycle(self.registry,self.path)
        self.assertTrue(apply_request(self.life,self.req(),42)['replayed'])

@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'requires Linux root for real UID split')
class ReconciliationIntegration(unittest.TestCase):
    setUp=ProductionWriteIntegration.setUp
    client=ProductionWriteIntegration.client
    # Inherit the Stage 016 integration fixtures but not its test methods.
    __test__=False
    def start(self):
        cmd=[sys.executable,'-m','lifesupport.reconciled_write_cli','--registry',str(self.registry),'--db',str(self.db),'--socket',str(self.sock),'--uids','65534']
        self.proc=subprocess.Popen(cmd,preexec_fn=lambda:(os.setgid(65533),os.setuid(65533)),env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        self.addCleanup(self.stop)
        for _ in range(200):
            if self.proc.poll() is not None:self.fail(self.proc.stderr.read().decode())
            if self.sock.is_socket():
                r=self.client({'op':'health'})
                if r.returncode==0 and json.loads(r.stdout).get('ok'):return
            time.sleep(.02)
        self.fail('not ready')
    def stop(self):
        if self.proc:
            if self.proc.poll() is None:self.proc.terminate();self.proc.wait(timeout=5)
            self.proc.stderr.close();self.proc=None
    def transition(self,event_id='evt1',state='INITIALIZING'):
        return dict(op='transition',component_id=self.cid,next_state=state,event_id=event_id,reason='offline test',request_id='req-'+event_id)
    def test_supervised_sigkill_and_replay(self):
        # supervisor runs as the service UID; use setuid child, not root supervisor
        code='''import sys
from lifesupport.core.reconciled_write import ProductionWriteSupervisor
s=ProductionWriteSupervisor(sys.argv[1],sys.argv[2],sys.argv[3],allowed_uids={65534})
s.run(max_restarts=1,poll=.02)
'''
        p=subprocess.Popen([sys.executable,'-c',code,str(self.registry),str(self.db),str(self.sock)],preexec_fn=lambda:(os.setgid(65533),os.setuid(65533)),env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if p.poll() is not None:self.fail('supervisor stopped: '+p.stderr.read().decode())
                r=self.client({'op':'health'}) if self.sock.is_socket() else None
                if r and r.returncode==0 and json.loads(r.stdout).get('ok'):break
                time.sleep(.02)
            else:self.fail('supervisor did not start')
            a=json.loads(self.client(self.transition()).stdout);self.assertTrue(a['ok'],a)
            # discover supervised child via kernel /proc, not untrusted socket pathname
            children=subprocess.check_output(['ps','-o','pid=','--ppid',str(p.pid)],text=True).split()
            self.assertEqual(len(children),1)
            os.kill(int(children[0]),signal.SIGKILL)
            for _ in range(300):
                r=self.client({'op':'health'}) if self.sock.is_socket() else None
                if r and r.returncode==0 and json.loads(r.stdout).get('ok'):
                    children2=subprocess.check_output(['ps','-o','pid=','--ppid',str(p.pid)],text=True).split()
                    if children2 and children2[0]!=children[0]:break
                time.sleep(.03)
            else:self.fail('supervisor failed recovery')
            b=json.loads(self.client(self.transition()).stdout)
            self.assertTrue(b['replayed'],b)
            receipt=json.loads(self.client({'op':'receipt','request_id':'req-evt1'}).stdout)
            self.assertTrue(receipt['found'])
            self.assertEqual(a['sequence'],b['sequence'])
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=5)
            p.stderr.close()
    def test_real_sigkill_before_after_commit(self):
        # Separate SQLite writers are killed at deterministic transaction barriers.
        code='''import os,sqlite3,sys,signal
c=sqlite3.connect(sys.argv[1],isolation_level=None)
c.execute('BEGIN IMMEDIATE')
c.execute('CREATE TABLE IF NOT EXISTS crash_probe (v INTEGER)')
c.execute('INSERT INTO crash_probe VALUES (1)')
if sys.argv[2]=='after':c.execute('COMMIT')
os.kill(os.getpid(),signal.SIGKILL)
'''
        for phase in ('before','after'):
            p=subprocess.run([sys.executable,'-c',code,str(self.db),phase],preexec_fn=lambda:(os.setgid(65533),os.setuid(65533)),capture_output=True,timeout=5)
            self.assertEqual(p.returncode,-signal.SIGKILL)
        db=sqlite3.connect(self.db)
        try:
            self.assertEqual(db.execute('SELECT count(*) FROM crash_probe').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        finally:db.close()
