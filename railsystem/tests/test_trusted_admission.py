import base64
import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from railsystem.provenance import candidate_baseline
from railsystem.trust import canonical
from railsystem.trusted_admission import admit, assess_admission, read_protected_json, AdmissionError
ROOT = Path(__file__).resolve().parents[1]
class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=Ed25519PrivateKey.generate()
        pub=cls.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        cls.trust={'schema_version':1,'keys':{'a':{'public_key':base64.b64encode(pub).decode(),'revoked':False}}}
        cls.baseline=candidate_baseline(ROOT,'rail-12')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'replay.sqlite'
    def signed(self,seq=1,nonce='nonce000000000001'):
        p={'domain':'snowpiercer.railsystem.release.v1','baseline_id':self.baseline['baseline_id'],'manifest_digest':self.baseline['manifest_digest'],'key_id':'a','sequence':seq,'nonce':nonce}
        return {'schema_version':1,'payload':p,'signature':base64.b64encode(self.key.sign(canonical(p))).decode()}
    def admit(self,att=None,trust=None):
        with patch('railsystem.trusted_admission.evaluate',return_value={'status':'PASS'}):
            return admit(ROOT,baseline=self.baseline,attestation=att or self.signed(),trust=trust or self.trust,db_path=self.db)
    def test_missing_inputs_blocked(self):
        self.assertEqual(assess_admission(ROOT)['status'],'BLOCKED')
    def test_first_commit(self):
        self.assertEqual(self.admit()['status'],'PASS')
        c=sqlite3.connect(self.db)
        try: self.assertEqual(c.execute('SELECT sequence FROM replay_state').fetchone()[0],1)
        finally: c.close()
    def test_replay_fails(self):
        self.admit()
        with self.assertRaises(ValueError): self.admit()
    def test_higher_sequence_passes(self):
        self.admit()
        self.assertEqual(self.admit(self.signed(2,'nonce000000000002'))['sequence'],2)
    def test_rollback_fails(self):
        self.admit(self.signed(3,'nonce000000000003'))
        with self.assertRaises(ValueError): self.admit(self.signed(2,'nonce000000000002'))
    def test_revoked_fails(self):
        t=copy.deepcopy(self.trust);t['keys']['a']['revoked']=True
        with self.assertRaises(ValueError): self.admit(trust=t)
    def test_tamper_fails(self):
        a=self.signed();a['payload']['sequence']=9
        with self.assertRaises(ValueError): self.admit(a)
    def test_db_symlink_rejected(self):
        target=Path(self.tmp.name)/'other';target.touch();self.db.symlink_to(target)
        with self.assertRaises(AdmissionError): self.admit()
    def test_protected_json_symlink_rejected(self):
        target=Path(self.tmp.name)/'data.json';target.write_text('{}')
        link=Path(self.tmp.name)/'link';link.symlink_to(target)
        with self.assertRaises(AdmissionError):read_protected_json(link)
    def test_failed_gate_does_not_advance(self):
        with patch('railsystem.trusted_admission.evaluate',return_value={'status':'FAIL'}):
            with self.assertRaises(AdmissionError): admit(ROOT,baseline=self.baseline,attestation=self.signed(),trust=self.trust,db_path=self.db)
        self.assertEqual(self.admit()['status'],'PASS')
    def test_cli_missing_trust_blocks(self):
        out=Path(self.tmp.name)/'report.json'
        p=subprocess.run([sys.executable,'-m','railsystem.release_cli','--output',str(out)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        self.assertEqual(json.loads(out.read_text())['status'],'BLOCKED')
    def test_sigkill_rollback(self):
        if not hasattr(os,'fork'):self.skipTest('POSIX only')
        pid=os.fork()
        if pid==0:
            with patch('railsystem.trusted_admission.evaluate',return_value={'status':'PASS'}):
                admit(ROOT,baseline=self.baseline,attestation=self.signed(),trust=self.trust,db_path=self.db,fault='after_write')
            os._exit(99)
        _,status=os.waitpid(pid,0)
        self.assertEqual(os.waitstatus_to_exitcode(status),88)
        self.assertEqual(self.admit()['status'],'PASS')
    def test_concurrent_same_attestation_one_wins(self):
        if not hasattr(os,'fork'):self.skipTest('POSIX only')
        children=[]
        for _ in range(2):
            pid=os.fork()
            if pid==0:
                try:
                    with patch('railsystem.trusted_admission.evaluate',return_value={'status':'PASS'}):
                        admit(ROOT,baseline=self.baseline,attestation=self.signed(),trust=self.trust,db_path=self.db)
                    os._exit(0)
                except Exception:os._exit(1)
            children.append(pid)
        codes=[os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]) for pid in children]
        self.assertEqual(sorted(codes),[0,1])
