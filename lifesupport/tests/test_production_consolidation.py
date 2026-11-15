import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from lifesupport.core.production_consolidation import install_profile, read_profile, enforce_legacy_cli, production_supervisor
from lifesupport.core.service import ServiceError

class ProductionConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'storage';self.root.mkdir(mode=0o700)
        self.db=self.root/'db.sqlite'
    def provision(self):
        return install_profile(self.db,anchor='/trusted/anchor',key_file='/trusted/key')
    def test_legacy_before_provision(self): self.assertIsNone(enforce_legacy_cli(self.db))
    def test_provision_and_legacy_block(self):
        self.provision()
        with self.assertRaisesRegex(ServiceError,'legacy production IPC disabled'):enforce_legacy_cli(self.db)
    def test_profile_roundtrip(self):
        self.provision();self.assertEqual(read_profile(self.db)['mode'],'mandatory-ledger')
    def test_supervisor_uses_mandatory_cli(self):
        self.provision();s=production_supervisor('/r',self.db,'/s',allowed_uids={42})
        self.assertEqual(s.cli_module,'lifesupport.mandatory_ledger_cli')
        self.assertEqual(s.extra_args,('--anchor','/trusted/anchor','--key-file','/trusted/key'))
    def test_no_profile_denied(self):
        with self.assertRaises(ServiceError):production_supervisor('/r',self.db,'/s',allowed_uids={42})
    def test_no_overwrite(self):
        self.provision()
        with self.assertRaises(FileExistsError):self.provision()
    def test_symlink_profile_denied(self):
        (self.root/'.life-production-profile.json').symlink_to('/etc/passwd')
        with self.assertRaises(OSError):read_profile(self.db)
    def test_unsafe_mode_denied(self):
        path=self.provision();path.chmod(0o644)
        with self.assertRaises(ServiceError):read_profile(self.db)
    def test_tamper_denied(self):
        path=self.provision();path.write_text('{')
        with self.assertRaises(ServiceError):read_profile(self.db)
    def test_wrong_directory_denied(self):
        self.root.chmod(0o777)
        with self.assertRaises(ServiceError):self.provision()
    def test_relative_anchor_denied(self):
        with self.assertRaises(ServiceError):install_profile(self.db,anchor='relative',key_file='/key')
    def test_cli_refuses_legacy_with_profile(self):
        self.provision()
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        for mod in ('production_write_cli','reconciled_write_cli'):
            with self.subTest(mod=mod):
                p=subprocess.run([sys.executable,'-m','lifesupport.'+mod,'--registry','/nonexistent','--db',str(self.db),'--socket','/unused','--uids','42'],env=env,capture_output=True,text=True,timeout=8)
                self.assertNotEqual(p.returncode,0)
                self.assertIn('legacy production IPC disabled',p.stderr)
