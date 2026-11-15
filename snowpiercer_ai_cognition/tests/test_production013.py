import json
import os
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager,
    AnchoredAdmissionGateway, AuditCheckpoint, signed_envelope)
from ai_cognition.isolation import ipc_request
from ai_cognition.production013 import create_service, load_config
from ai_cognition.service_identity import IsolationError

UID=65533
CLIENT=65534
K=b'a'*32

@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0, 'requires root Linux setuid fixture')
class Production013Tests(unittest.TestCase):
    def setUp(self):
        # Some later TestCases reuse this fixture directly rather than inheriting
        # its class decorator. Reject the unsupported fixture before any chown.
        if not (sys.platform.startswith('linux') and os.geteuid() == 0):
            self.skipTest('requires root Linux setuid fixture')
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); os.chmod(self.root,0o755)
        self.private=self.root/'private'; self.private.mkdir(); os.chown(self.private,UID,UID); os.chmod(self.private,0o700)
        self.ipc=self.root/'ipc'; self.ipc.mkdir(); os.chown(self.ipc,UID,CLIENT); os.chmod(self.ipc,0o710)
        self.socket=self.ipc/'service.sock'
        self.config=self.private/'config.json'
        self.cfg={'private_dir':str(self.private),'socket_dir':str(self.ipc),'socket_path':str(self.socket),
            'db':str(self.private/'db'),'legacy_anchor':str(self.private/'legacy'),
            'independent_anchor':str(self.private/'independent'),'checkpoint':str(self.private/'checkpoint'),
            'source_keys':{'trainos':K.hex()},'root_key':(b'b'*32).hex(),
            'rotation_secret':(b'c'*32).hex(),'audit_key':(b'd'*32).hex(),
            'checkpoint_key':(b'e'*32).hex(),'recovery_secret':(b'f'*32).hex(),
            'allowed_uids':[CLIENT,0],'recovery_uids':[],'ipc_gid':CLIENT}
        store=ReplayStore(self.cfg['db'])
        try:
            manager=HardenedRotationManager(store,self.cfg['legacy_anchor'],{'trainos':K},
                independent_anchor=IndependentAnchor(self.cfg['independent_anchor'],b'b'*32),
                recovery_secret=b'c'*32,bootstrap=True)
            manager.provision('trainos')
            AnchoredAdmissionGateway(manager,b'd'*32,
                checkpoint=AuditCheckpoint(self.cfg['checkpoint'],b'e'*32),bootstrap=True)
        finally: store.close()
        for f in self.private.iterdir():
            if f.is_file(): os.chown(f,UID,UID); os.chmod(f,0o600)
        from ai_cognition.production014 import PhaseJournal
        self.cfg['phase_journal'] = str(self.private/'phase')
        self.cfg['phase_key'] = (b'g'*32).hex()
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('CLEAN',0,'0'*64)
        os.chown(self.cfg['phase_journal'],UID,UID)
        self.config.write_text(json.dumps(self.cfg)); os.chown(self.config,UID,UID); os.chmod(self.config,0o600)
        self.child=None
        self.addCleanup(self.stop)
    def stop(self):
        if self.child is not None:
            if self.child.poll() is None: self.child.kill()
            self.child.wait(timeout=4)
            if self.child.stderr is not None: self.child.stderr.close()
            self.child=None
    def start(self):
        self.child=subprocess.Popen([sys.executable,'-m','ai_cognition.production015',str(self.config)],
            user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(80):
            if self.child.poll() is not None:
                raise AssertionError('child exited: '+self.child.stderr.read().decode())
            try:
                if ipc_request(self.socket,{'op':'verify'},timeout=.2).get('ok'): return
            except (OSError,RuntimeError): pass
            time.sleep(.05)
        self.fail('service not ready')
    def test_sigkill_restart_fresh_sqlite_and_replay(self):
        self.start()
        envelope=signed_envelope({'event_id':'event001','source':'trainos','severity':'warning','description':'ok'},
                                 int(time.time()),'a'*16,K)
        self.assertTrue(ipc_request(self.socket,{'op':'admit','envelope':envelope})['ok'])
        self.child.kill(); self.child.wait(timeout=4); self.child.stderr.close(); self.child=None
        self.start()
        self.assertEqual(ipc_request(self.socket,{'op':'verify'})['seq'],1)
        self.assertFalse(ipc_request(self.socket,{'op':'admit','envelope':envelope})['ok'])
        envelope2=signed_envelope({'event_id':'event002','source':'trainos','severity':'warning','description':'ok'},
                                 int(time.time()),'b'*16,K)
        self.assertTrue((response := ipc_request(self.socket,{'op':'admit','envelope':envelope2}))['ok'], response)
    def test_fenced_checkpoint_refuses_socket_publication(self):
        Path(self.cfg['checkpoint']).write_text('tamper')
        self.child=subprocess.Popen([sys.executable,'-m','ai_cognition.production015',str(self.config)],
            user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.assertNotEqual(self.child.wait(timeout=4),0)
        self.assertFalse(self.socket.exists())
    def test_config_permissions_and_symlink_refused(self):
        os.chmod(self.config,0o644)
        with self.assertRaises(IsolationError): load_config(self.config)
        os.chmod(self.config,0o600)
        alias=self.private/'alias'; alias.symlink_to(self.config)
        with self.assertRaises(IsolationError): load_config(alias)
    def test_socket_replacement_refused(self):
        self.socket.write_text('fake')
        self.child=subprocess.Popen([sys.executable,'-m','ai_cognition.production015',str(self.config)],
            user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.assertNotEqual(self.child.wait(timeout=4),0)
        self.assertEqual(self.socket.read_text(),'fake')
    def test_cross_uid_access_and_file_denial(self):
        self.start()
        script='''import os,sys\nfrom ai_cognition.isolation import ipc_request\nprint(ipc_request(sys.argv[1],{'op':'verify'})['ok'])\ntry: open(sys.argv[2],'rb'); print('LEAK')\nexcept PermissionError: print('DENIED')'''
        result=subprocess.run([sys.executable,'-c',script,str(self.socket),self.cfg['db']],
            user=CLIENT,group=CLIENT,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])},
            capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.splitlines(),['True','DENIED'])

    def test_supervisor_automatic_sigkill_restart(self):
        import threading
        from ai_cognition.orchestration import AdmissionSupervisor
        stop=threading.Event()
        supervisor=AdmissionSupervisor([sys.executable,'-m','ai_cognition.production015',str(self.config)],
            self.socket,service_uid=UID,service_gid=CLIENT,max_restarts=2,startup_timeout=4,
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])})
        failures=[]
        def worker():
            try: supervisor.run(stop_event=stop)
            except BaseException as exc: failures.append(exc)
        thread=threading.Thread(target=worker); thread.start()
        try:
            for _ in range(100):
                if supervisor.ready: break
                time.sleep(.05)
            self.assertTrue(supervisor.ready,failures)
            first=supervisor.process.pid
            os.kill(first,signal.SIGKILL)
            for _ in range(100):
                if supervisor.ready and supervisor.process and supervisor.process.pid!=first: break
                time.sleep(.05)
            self.assertTrue(supervisor.ready,failures)
            self.assertNotEqual(supervisor.process.pid,first)
            self.assertTrue(ipc_request(self.socket,{'op':'verify'})['ok'])
        finally:
            stop.set(); thread.join(timeout=8)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures,failures)
