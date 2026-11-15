"""RAIL-TRUST-012: OS-kernel peer authentication against volatile test providers."""
import os
import signal
import socket
import tempfile
import unittest
from pathlib import Path
from railsystem.provider_ipc import UnixAnchorClient, UnixPermitLedgerClient, RemoteProviderUnavailable
from helpers_012 import GID, CLIENT, SERVICE, WITNESS, RECOVERY, launch_provider, stop_provider

@unittest.skipUnless(os.geteuid() == 0 and hasattr(socket,'SO_PEERCRED'), 'needs root Linux host')
class ProviderIPC012Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o755)
        self.pids=[]
        self.addCleanup(self.stop)
        pid, path = launch_provider(self.root, WITNESS, 'anchor'); self.pids.append(pid)
        self.anchor_path=path
        pid, path = launch_provider(self.root, RECOVERY, 'permit'); self.pids.append(pid)
        self.permit_path=path
    def stop(self):
        for pid in self.pids: stop_provider(pid)
        self.pids=[]
    def clients(self):
        return (UnixAnchorClient(self.anchor_path,expected_uid=WITNESS,expected_gid=GID),
                UnixPermitLedgerClient(self.permit_path,expected_uid=RECOVERY,expected_gid=GID))
    def test_release_manifest_covers_os_boundary_artifacts(self):
        from railsystem.verification import manifest
        root=Path(__file__).resolve().parents[1]
        files=manifest(root)['files']
        for path in ('railsystem/provider_ipc.py','railsystem/os_boundary.py',
                     'railsystem/service_runtime.py',
                     'systemd/railsystem-recovery.service.example',
                     'systemd/railsystem-witness.service.example',
                     'systemd/railsystem-permits.service.example',
                     'deployment/roles.example.json'):
            self.assertIn(path,files)

    def test_production_cli_missing_witness_classified_blocked(self):
        import json
        from unittest.mock import patch
        from railsystem.release_cli import main
        from railsystem.production_fencing import IndependentAnchorUnavailable
        import sys
        out=self.root/'release-result.json'
        argv=['railsystem.release_cli','--state-dir',str(self.root),
              '--baseline',str(out),'--attestation',str(out),'--trust',str(out),
              '--output',str(out)]
        with patch.object(sys,'argv',argv), \
             patch('railsystem.release_cli.read_protected_json',return_value={}), \
             patch('railsystem.release_cli.admit_unified',side_effect=IndependentAnchorUnavailable('offline')):
            self.assertEqual(main(),2)
        self.assertEqual(json.loads(out.read_text())['status'],'BLOCKED')

    def test_cas_success_and_rollback_rejected(self):
        anchor,_=self.clients()
        self.assertEqual(anchor.read(),(0,''))
        self.assertTrue(anchor.advance((0,''),(1,'n1')))
        self.assertFalse(anchor.advance((0,''),(2,'n2')))
        self.assertEqual(anchor.read(),(1,'n1'))
        with self.assertRaises(RemoteProviderUnavailable): anchor.advance((1,'n1'),(0,''))
    def test_ledger_replay(self):
        _,ledger=self.clients()
        self.assertTrue(ledger.check_ready())
        self.assertTrue(ledger.consume_once('a'*64,sequence=1,action='reconcile'))
        self.assertFalse(ledger.consume_once('a'*64,sequence=1,action='reconcile'))
    def test_wrong_peer_uid_denied(self):
        with self.assertRaises(RemoteProviderUnavailable):
            UnixAnchorClient(self.anchor_path,expected_uid=RECOVERY,expected_gid=GID).read()
    def test_unsafe_path_and_symlink_denied(self):
        client,_=self.clients()
        os.chmod(self.anchor_path,0o666)
        with self.assertRaises(RemoteProviderUnavailable):client.read()
        os.chmod(self.anchor_path,0o660)
        other = self.root/'alias';other.symlink_to(self.anchor_path)
        with self.assertRaises(RemoteProviderUnavailable):
            UnixAnchorClient(other,expected_uid=WITNESS,expected_gid=GID).read()
    def test_unavailable_provider_fails_closed(self):
        client,ledger=self.clients()
        self.stop()
        with self.assertRaises(RemoteProviderUnavailable):client.read()
        with self.assertRaises(RemoteProviderUnavailable):ledger.check_ready()
    def test_invalid_contract_denied(self):
        with self.assertRaises(RemoteProviderUnavailable):
            UnixAnchorClient(self.anchor_path,expected_uid=0,expected_gid=GID)
        _,ledger=self.clients()
        with self.assertRaises(RemoteProviderUnavailable):
            ledger.consume_once('xyz',sequence=1,action='reconcile')
        with self.assertRaises(RemoteProviderUnavailable):
            ledger.consume_once('a'*64,sequence=0,action='reconcile')
