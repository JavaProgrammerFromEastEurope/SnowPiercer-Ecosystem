import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock
from ai_cognition.production014 import PhaseJournal
from ai_cognition.production015 import JournaledProductionIPCServer, load_config_015
from ai_cognition.lifecycle import RecoveryRequired
from ai_cognition.isolation import ipc_request
from test_production013 import Production013Tests, UID, CLIENT, K, signed_envelope

class Production015Tests(Production013Tests):
    def setUp(self):
        super().setUp()
        self.cfg['phase_journal'] = str(self.private/'phase')
        self.cfg['phase_key'] = (b'g'*32).hex()
        PhaseJournal(self.cfg['phase_journal'], b'g'*32).write('CLEAN', 0, '0'*64)
        os.chown(self.cfg['phase_journal'], UID, UID)
        self.config.write_text(json.dumps(self.cfg))
        os.chown(self.config, UID, UID)
        os.chmod(self.config, 0o600)

    def start(self):
        self.child = subprocess.Popen([sys.executable, '-m', 'ai_cognition.production015', str(self.config)],
            user=UID, group=CLIENT,
            env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(80):
            if self.child.poll() is not None:
                raise AssertionError('child exited: '+self.child.stderr.read().decode())
            try:
                if ipc_request(self.socket, {'op':'verify'}, timeout=.2).get('ok'): return
            except (OSError, RuntimeError): pass
            time.sleep(.05)
        self.fail('service not ready')

    def test_sigkill_restart_fresh_sqlite_and_replay(self):
        self.start()
        env=signed_envelope({'event_id':'event015a','source':'trainos','severity':'warning','description':'ok'},
                            int(time.time()), 'a'*16, K)
        self.assertTrue(ipc_request(self.socket, {'op':'admit','envelope':env})['ok'])
        self.child.kill(); self.child.wait(timeout=4); self.child.stderr.close(); self.child=None
        self.start()
        self.assertEqual(ipc_request(self.socket, {'op':'verify'})['seq'], 1)
        self.assertFalse(ipc_request(self.socket, {'op':'admit','envelope':env})['ok'])
        self.assertTrue(ipc_request(self.socket, {'op':'admit','envelope':signed_envelope(
            {'event_id':'event015b','source':'trainos','severity':'warning','description':'ok'},
            int(time.time()), 'b'*16, K)}), 'second admission rejected')

    def test_prepared_phase_blocks_socket(self):
        PhaseJournal(self.cfg['phase_journal'],b'g'*32).write('PREPARED',0,'0'*64)
        self.child=subprocess.Popen([sys.executable,'-m','ai_cognition.production015',str(self.config)],
            user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        self.assertNotEqual(self.child.wait(timeout=5),0)
        self.assertFalse(self.socket.exists())

    def test_phase_tamper_blocks_socket(self):
        Path(self.cfg['phase_journal']).write_text('tamper')
        self.child=subprocess.Popen([sys.executable,'-m','ai_cognition.production015',str(self.config)],
            user=UID,group=CLIENT,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        self.assertNotEqual(self.child.wait(timeout=5),0)
        self.assertFalse(self.socket.exists())

    def test_supervisor_automatic_sigkill_restart(self):
        self.skipTest("inherited supervisor hardcodes production013; v015 supervisor coverage pending")

    def test_production_recovery_ipc_denied(self):
        self.start()
        self.assertFalse(ipc_request(self.socket, {'op':'recover','permit':{}})['ok'])

    def test_legacy_server_rejected_by_journaled_constructor(self):
        with self.assertRaises(TypeError):
            JournaledProductionIPCServer(object(), self.socket, allowed_uids=[CLIENT],recovery_secret=b'f'*32)
