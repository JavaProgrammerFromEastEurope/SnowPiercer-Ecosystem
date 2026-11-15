import os
import subprocess
import sys
import unittest
from pathlib import Path
from ai_cognition.production016 import cold_recover
from ai_cognition.lifecycle import RecoveryRequired
from test_production015 import Production015Tests, UID, CLIENT
from test_production013 import Production013Tests

ROOT = str(Path(__file__).resolve().parents[1])

class Production016Tests(unittest.TestCase):
    start = Production015Tests.start
    stop = Production013Tests.stop
    def setUp(self):
        Production013Tests.setUp(self)
        import json
        from ai_cognition.production014 import PhaseJournal
        self.cfg['phase_journal'] = str(self.private/'phase')
        self.cfg['phase_key'] = (b'g'*32).hex()
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('CLEAN',0,'0'*64)
        os.chown(self.cfg['phase_journal'],UID,UID)
        self.config.write_text(json.dumps(self.cfg))
        os.chown(self.config,UID,UID)
        os.chmod(self.config,0o600)
    def test_cold_recovery_after_prepare_no_commit(self):
        if os.geteuid() != 0: self.skipTest('requires root UID fixture')
        from ai_cognition.production014 import PhaseJournal
        from ai_cognition.isolation import recovery_permit
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('PREPARED',0,'0'*64)
        os.chown(self.cfg['phase_journal'], UID, UID)
        p = recovery_permit(b'f'*32, 'permit016', 0, '0'*64)
        script = 'import sys,json; from ai_cognition.production016 import cold_recover; print(cold_recover(sys.argv[1],json.loads(sys.argv[2]),operator_verified=True))'
        proc = subprocess.run([sys.executable,'-c',script,str(self.config),__import__('json').dumps(p)],user=UID,group=CLIENT,
            env={**os.environ,'PYTHONPATH':ROOT},capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn('(0,',proc.stdout)
        proc2 = subprocess.run([sys.executable,'-c',script,str(self.config),__import__('json').dumps(p)],user=UID,group=CLIENT,
            env={**os.environ,'PYTHONPATH':ROOT},capture_output=True,text=True,timeout=10)
        self.assertNotEqual(proc2.returncode,0)
        self.start()
        self.assertTrue(__import__('ai_cognition.isolation',fromlist=['ipc_request']).ipc_request(self.socket,{'op':'verify'})['ok'])

    def test_operator_gate(self):
        with self.assertRaises(RecoveryRequired):
            cold_recover(self.config, {}, operator_verified=False)

    def test_legacy_012_cli_fenced(self):
        p = subprocess.run([sys.executable,'-m','ai_cognition.production012','bogus:factory'],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('LEGACY_PRODUCTION_ENTRYPOINT_DISABLED',p.stderr)
