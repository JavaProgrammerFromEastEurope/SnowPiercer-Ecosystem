"""Stage ISLAND-GEO-022: deny-by-default trust boundary tests."""
import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from island.anchored_admission import AdmissionDenied, GENESIS
from island.host_security import (observe_host_security, require_production_security,
                                  require_separated_roles)
from island.monotonic_root import prove, verify_proof, _head, RootClient
from island.secure_runtime import StrictSplitBroker
from island.split_authorities import SplitAttestedWriteBroker, SplitWitnessServer, SplitPermitServer


class IndependentRootTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.pub = self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.head = {'sequence': 0, 'digest': GENESIS}
        self.challenge = secrets.token_hex(16)

    def test_signed_challenge_roundtrip(self):
        proof = prove(self.head,self.challenge,self.key)
        self.assertEqual(verify_proof(proof,self.challenge,self.pub),self.head)

    def test_stale_challenge_denied(self):
        proof=prove(self.head,self.challenge,self.key)
        with self.assertRaises(AdmissionDenied):
            verify_proof(proof,secrets.token_hex(16),self.pub)

    def test_wrong_trust_anchor_denied(self):
        proof=prove(self.head,self.challenge,self.key)
        bad=Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        with self.assertRaises(AdmissionDenied):
            verify_proof(proof,self.challenge,bad)

    def test_mutation_denied(self):
        proof=prove(self.head,self.challenge,self.key)
        proof['body']['head']={'sequence':1,'digest':'a'*64}
        with self.assertRaises(AdmissionDenied):
            verify_proof(proof,self.challenge,self.pub)

    def test_missing_signature_denied(self):
        with self.assertRaises(AdmissionDenied):
            verify_proof({'body':{}},self.challenge,self.pub)

    def test_invalid_heads_denied(self):
        for head in ({'sequence':-1,'digest':GENESIS},
                     {'sequence':0,'digest':'b'*64},
                     {'sequence':True,'digest':GENESIS},
                     {'sequence':1,'digest':'g'*64}):
            with self.subTest(head=head), self.assertRaises(AdmissionDenied):
                _head(head)

    def test_transport_does_not_allow_invalid_operations(self):
        client=RootClient('/nonexistent',25006,self.pub)
        with self.assertRaises(AdmissionDenied):
            client.execute('delete')
        with self.assertRaises(AdmissionDenied):
            RootClient('/none',0,self.pub)

    def test_root_rollback_mismatch(self):
        client=RootClient('/nonexistent',25006,self.pub)
        with patch.object(client,'execute',return_value=self.head):
            with self.assertRaisesRegex(AdmissionDenied,'divergence'):
                client.require_head({'sequence':1,'digest':'a'*64})

    def test_fixture_is_not_hardware_root(self):
        from island.monotonic_root import SoftwareRootServer
        self.assertIn('roll back',SoftwareRootServer.__doc__)


class ProductionGateTests(unittest.TestCase):
    def test_six_roles_distinct(self):
        self.assertEqual(len(require_separated_roles(25001,25002,25003,25004,25005,25006)),6)
        for values in ((25001,25002,25002,25004,25005,25006),
                       (25001,25002,25003,25004,25005,0),
                       (25001,25002,25003,25004,25005,True)):
            with self.subTest(values=values),self.assertRaises(AdmissionDenied):
                require_separated_roles(*values)

    def test_root_is_not_accepted(self):
        with patch('island.host_security.os.geteuid',return_value=0):
            observed=observe_host_security()
            self.assertFalse(observed.production_go)
            self.assertIn('privileged service UID', observed.reasons)

    def test_missing_verified_hw_attestation_denied(self):
        with patch('island.host_security.os.geteuid',return_value=25003):
            observed=observe_host_security()
            self.assertFalse(observed.verified_hardware_monotonic_root)
            self.assertFalse(observed.verified_same_uid_mac_fence)
            with self.assertRaisesRegex(AdmissionDenied,'BLOCKED/NO-GO'):
                require_production_security()

    def test_forged_environment_cannot_grant_go(self):
        with patch.dict(os.environ,{'INVOCATION_ID':'x'*32,'NOTIFY_SOCKET':'/run/fake',
                                   'ISLAND_PRODUCTION_GO':'yes','ISLAND_ROOT_VERIFIED':'true'}):
            with self.assertRaises(AdmissionDenied):
                require_production_security()

    def test_strict_broker_denies_before_touching_lock(self):
        with tempfile.TemporaryDirectory() as td:
            broker=object.__new__(StrictSplitBroker)
            broker.db=Path(td)/'broker.sqlite'
            with self.assertRaises(AdmissionDenied):
                broker.serve('nonempty-token')
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_ipc_identity_separation(self):
        with patch('island.split_authorities.os.geteuid',return_value=25004):
            with self.assertRaises(AdmissionDenied):
                SplitWitnessServer('/tmp/w.sock','/tmp/w.db','/tmp/r.sock',25004,self.pub_dummy(),25003,25005)
        with patch('island.split_authorities.os.geteuid',return_value=25005):
            with self.assertRaises(AdmissionDenied):
                SplitPermitServer('/tmp/p.sock','/tmp/p.db','/tmp/w.sock',25004,25005,25001)

    @staticmethod
    def pub_dummy(): return bytes(32)

    def test_broker_rejects_same_uid_authority(self):
        with patch('island.split_authorities.os.geteuid',return_value=25003),\
             patch('island.write_broker.os.geteuid',return_value=25003):
            with self.assertRaises(AdmissionDenied):
                SplitAttestedWriteBroker('/tmp/b.sock','/tmp/b.db','/tmp/w.sock',
                                          '/tmp/p.sock','/tmp/client.pub',25001,25002,25004,25003)


if __name__=='__main__': unittest.main()
