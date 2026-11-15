"""Real SIGKILL tests, intentionally run only with a privileged UID fixture."""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from ai_cognition.crash018 import CrashInjector, POINTS
from ai_cognition.production014 import PhaseJournal
from ai_cognition.isolation import recovery_permit, ipc_request
from test_production015 import Production015Tests, UID, CLIENT, K, signed_envelope
from test_production013 import Production013Tests

ROOT = str(Path(__file__).resolve().parents[1])

class Crash018Tests(unittest.TestCase):
    def setUp(self):
        Production013Tests.setUp(self)
        self.cfg['phase_journal'] = str(self.private/'phase')
        self.cfg['phase_key'] = (b'g'*32).hex()
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('CLEAN',0,'0'*64)
        os.chown(self.cfg['phase_journal'], UID, UID)
        self.config.write_text(json.dumps(self.cfg))
        os.chown(self.config, UID, UID)
        os.chmod(self.config, 0o600)
    stop = Production013Tests.stop
    start = Production015Tests.start

    def test_injector_requires_explicit_opt_in(self):
        with self.assertRaises(PermissionError): CrashInjector('after_prepare')
        with self.assertRaises(ValueError): CrashInjector('bogus', enabled=True)

    def test_sigkill_matrix_and_cold_recovery(self):
        if os.geteuid() != 0: self.skipTest('requires root fixture for cross-UID subprocess')
        for index, point in enumerate(sorted(POINTS)):
            with self.subTest(point=point):
                # Use a fresh independent fixture for each crash point.
                if index:
                    self.tearDown()
                    self.setUp()
                env = signed_envelope({'event_id':'crash018'+str(index),'source':'trainos',
                    'severity':'warning','description':'ok'},int(time.time()),str(index+1)*16,K)
                script = '''import json,sys
from ai_cognition.production015 import create_service
from ai_cognition.crash018 import CrashInjector,inject_admission
service,store=create_service(sys.argv[1])
try: inject_admission(service.gateway,json.loads(sys.argv[2]),CrashInjector(sys.argv[3],enabled=True))
finally: store.close()
'''
                proc = subprocess.run([sys.executable,'-c',script,str(self.config),json.dumps(env),point],
                    user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':ROOT},capture_output=True,text=True,timeout=8)
                self.assertEqual(proc.returncode,-9,proc.stderr)
                journal = PhaseJournal(self.cfg['phase_journal'],b'g'*32)
                self.assertEqual(journal.read()['phase'],'PREPARED')
                self.assertFalse(self.socket.exists())
                # Service cannot publish a socket while PREPARED.
                attempt = subprocess.run([sys.executable,'-c',
                    'import sys; from ai_cognition.production015 import create_service; create_service(sys.argv[1])',
                    str(self.config)],user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':ROOT},
                    capture_output=True,text=True,timeout=8)
                self.assertNotEqual(attempt.returncode,0)
                permit = recovery_permit(b'f'*32,'crash018permit'+str(index),0,'0'*64)
                recovery = subprocess.run([sys.executable,'-c',
                    'import sys,json; from ai_cognition.production016 import cold_recover; print(cold_recover(sys.argv[1],json.loads(sys.argv[2]),operator_verified=True))',
                    str(self.config),json.dumps(permit)],user=UID,group=CLIENT,
                    env={**os.environ,'PYTHONPATH':ROOT},capture_output=True,text=True,timeout=8)
                self.assertEqual(recovery.returncode,0,recovery.stderr)
                self.start()
                self.assertTrue(ipc_request(self.socket,{'op':'verify'})['ok'])
                # Replay is rejected only when the original transaction committed.
                response = ipc_request(self.socket,{'op':'admit','envelope':env})
                committed = point in ('after_sqlite_commit','before_checkpoint','after_checkpoint','before_clean')
                self.assertEqual(response['ok'],not committed)
                if not committed:
                    self.assertFalse(ipc_request(self.socket,{'op':'admit','envelope':env})['ok'])
                self.child.kill(); self.child.wait(timeout=5); self.child.stderr.close(); self.child=None
