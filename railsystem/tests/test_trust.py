import base64
import copy
import unittest
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from railsystem.provenance import candidate_baseline
from railsystem.trust import canonical, verify_attestation, evaluate_trusted, TrustError
ROOT = Path(__file__).resolve().parents[1]
class TrustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = Ed25519PrivateKey.generate()
        pub = cls.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        cls.trust = {'schema_version':1,'keys':{'release-a':{'public_key':base64.b64encode(pub).decode(),'revoked':False}}}
        cls.base = candidate_baseline(ROOT,'rail-11')
        cls.state = {'schema_version':1,'minimum_sequence':0,'used_nonces':[]}
    def signed(self):
        payload = {'domain':'snowpiercer.railsystem.release.v1','baseline_id':self.base['baseline_id'],'manifest_digest':self.base['manifest_digest'],'key_id':'release-a','sequence':1,'nonce':'uniquenonce00000001'}
        return {'schema_version':1,'payload':payload,'signature':base64.b64encode(self.key.sign(canonical(payload))).decode()}
    def verify(self, **kw):
        return verify_attestation(ROOT, kw.get('base',self.base),kw.get('att',self.signed()),kw.get('trust',self.trust),kw.get('state',self.state))
    def test_valid(self): self.assertEqual(self.verify()['status'],'PASS')
    def test_next_state(self): self.assertEqual(self.verify()['next_state']['minimum_sequence'],1)
    def test_replay(self):
        with self.assertRaises(TrustError): self.verify(state=self.verify()['next_state'])
    def test_rollback(self):
        state=copy.deepcopy(self.state);state['minimum_sequence']=2
        with self.assertRaises(TrustError): self.verify(state=state)
    def test_revoked(self):
        t=copy.deepcopy(self.trust);t['keys']['release-a']['revoked']=True
        with self.assertRaises(TrustError): self.verify(trust=t)
    def test_unknown_signer(self):
        t=copy.deepcopy(self.trust);t['keys']={'other':t['keys']['release-a']}
        with self.assertRaises(TrustError): self.verify(trust=t)
    def test_signature_tampered(self):
        a=self.signed();a['signature']=base64.b64encode(bytes(64)).decode()
        with self.assertRaises(TrustError): self.verify(att=a)
    def test_payload_tampered(self):
        a=self.signed();a['payload']['sequence']=3
        with self.assertRaises(TrustError): self.verify(att=a)
    def test_domain_separation(self):
        a=self.signed();a['payload']['domain']='other'
        with self.assertRaises(TrustError): self.verify(att=a)
    def test_baseline_mismatch(self):
        b=copy.deepcopy(self.base);b['baseline_id']='other'
        with self.assertRaises(TrustError): self.verify(base=b)
    def test_manifest_mismatch(self):
        b=copy.deepcopy(self.base);b['manifest']['files']['fake']='0'*64
        with self.assertRaises(TrustError): self.verify(base=b)
    def test_missing_trust_blocks(self):
        self.assertEqual(evaluate_trusted(ROOT,regression={'tests_run':1,'successful':True,'failures':[],'errors':[],'skipped':0})['status'],'BLOCKED')
    def test_trusted_gate_pass(self):
        r=evaluate_trusted(ROOT,baseline=self.base,attestation=self.signed(),trust=self.trust,state=self.state,regression={'tests_run':1,'successful':True,'failures':[],'errors':[],'skipped':0})
        self.assertEqual(r['status'],'PASS')
    def test_trusted_gate_rejects_revocation(self):
        t=copy.deepcopy(self.trust);t['keys']['release-a']['revoked']=True
        r=evaluate_trusted(ROOT,baseline=self.base,attestation=self.signed(),trust=t,state=self.state,regression={'tests_run':1,'successful':True,'failures':[],'errors':[],'skipped':0})
        self.assertEqual(r['status'],'FAIL')
    def test_no_implicit_state_mutation(self):
        state=copy.deepcopy(self.state);self.verify(state=state);self.assertEqual(state,self.state)
    def test_bool_sequence_rejected(self):
        a=self.signed();a['payload']['sequence']=True
        with self.assertRaises(TrustError): self.verify(att=a)
