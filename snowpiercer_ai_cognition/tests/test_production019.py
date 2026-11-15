"""AI-CORE-019: independent-process recovery contention and fail-closed checks."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
import test_production016 as p016
import test_production013 as p013
UID, CLIENT, ROOT = p016.UID, p016.CLIENT, p016.ROOT
from ai_cognition.production014 import PhaseJournal
from ai_cognition.isolation import recovery_permit, ipc_request


class Recovery019Tests(unittest.TestCase):
    setUp = p016.Production016Tests.setUp
    stop = p013.Production013Tests.stop
    start = p016.Production016Tests.start

    def _recover(self, permit, timeout=8):
        code = 'import json,sys; from ai_cognition.production016 import cold_recover; print(cold_recover(sys.argv[1],json.loads(sys.argv[2]),operator_verified=True))'
        return subprocess.run([sys.executable, '-c', code, str(self.config), json.dumps(permit)],
            user=UID, group=CLIENT, env={**os.environ,'PYTHONPATH':ROOT},
            capture_output=True, text=True, timeout=timeout)

    def test_parallel_recovery_lock_contention(self):
        if os.geteuid() != 0: self.skipTest('requires root Linux UID fixture')
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('PREPARED',0,'0'*64)
        os.chown(self.cfg['phase_journal'], UID, UID)
        permit = recovery_permit(b'f'*32, 'permit019-lock', 0, '0'*64)
        # Another independent process holds the exact lock; recovery must not wait.
        code = '''import os,fcntl,sys,time
fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT,0o600)
fcntl.flock(fd,fcntl.LOCK_EX)
print('LOCKED',flush=True)
time.sleep(8)'''
        proc = subprocess.Popen([sys.executable,'-c',code,str(self.private/'recovery016.lock')],
            user=UID, group=CLIENT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), 'LOCKED')
            refused=self._recover(permit)
            self.assertNotEqual(refused.returncode,0)
            self.assertIn('RECOVERY_ALREADY_IN_PROGRESS',refused.stderr)
        finally:
            proc.kill(); proc.communicate(timeout=4)
        recovered=self._recover(permit)
        self.assertEqual(recovered.returncode,0,recovered.stderr)
        self.assertNotEqual(self._recover(permit).returncode,0)
        self.start()
        self.assertTrue(ipc_request(self.socket,{'op':'verify'})['ok'])

    def test_invalid_permit_does_not_clear_phase(self):
        if os.geteuid() != 0: self.skipTest('requires root Linux UID fixture')
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('PREPARED',0,'0'*64)
        os.chown(self.cfg['phase_journal'], UID, UID)
        bad=recovery_permit(b'x'*32,'permit019-bad',0,'0'*64)
        self.assertNotEqual(self._recover(bad).returncode,0)
        self.assertEqual(PhaseJournal(self.cfg['phase_journal'],b'g'*32).read()['phase'],'PREPARED')
        good=recovery_permit(b'f'*32,'permit019-good',0,'0'*64)
        self.assertEqual(self._recover(good).returncode,0)

    def test_symlink_lock_rejected(self):
        if os.geteuid() != 0: self.skipTest('requires root Linux UID fixture')
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('PREPARED',0,'0'*64)
        os.chown(self.cfg['phase_journal'], UID, UID)
        (self.private/'recovery016.lock').symlink_to(self.cfg['db'])
        permit=recovery_permit(b'f'*32,'permit019-link',0,'0'*64)
        self.assertNotEqual(self._recover(permit).returncode,0)
        self.assertEqual(PhaseJournal(self.cfg['phase_journal'],b'g'*32).read()['phase'],'PREPARED')
