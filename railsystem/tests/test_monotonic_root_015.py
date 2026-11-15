"""RAIL-TRUST-015: independent-root quotation protocol; not a production root."""
import base64
import copy
import unittest
from unittest import mock
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from railsystem.monotonic_root import (DOMAIN, RootQuoteDenied, new_challenge,
    require_independent_root, verify_root_quote)
from railsystem.trust import canonical


class RootProtocolTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        raw = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        self.pub = base64.b64encode(raw).decode('ascii')
        self.challenge = new_challenge()
        self.payload = {'domain': DOMAIN, 'root_id': 'remote-hsm-1', 'key_id': 'device-01',
                        'challenge': self.challenge, 'sequence': 42, 'nonce': 'bound-to-state',
                        'schema_version': 1}

    def quote(self, payload=None):
        p = copy.deepcopy(self.payload) if payload is None else payload
        return {'payload': p, 'signature': base64.b64encode(self.private.sign(canonical(p))).decode('ascii')}

    def verify(self, quote=None, **overrides):
        args = dict(public_key=self.pub, key_id='device-01', root_id='remote-hsm-1',
                    challenge=self.challenge, minimum_sequence=41)
        args.update(overrides)
        return verify_root_quote(self.quote() if quote is None else quote, **args)

    def test_valid_signature_only_proves_cryptography(self):
        v = self.verify()
        self.assertEqual(v['status'], 'CRYPTOGRAPHIC_PROTOCOL_ONLY')
        self.assertFalse(v['independent_custody_verified'])
        self.assertFalse(v['production_authorized'])
        self.assertFalse(v['physical_operations_authorized'])

    def test_unique_unpredictable_challenges(self):
        self.assertEqual(len(bytes.fromhex(new_challenge())), 32)
        self.assertNotEqual(self.challenge, new_challenge())

    def test_challenge_replay_rejected(self):
        with self.assertRaises(RootQuoteDenied):
            self.verify(challenge=new_challenge())

    def test_policy_rollback_floor_rejected(self):
        with self.assertRaises(RootQuoteDenied):
            self.verify(minimum_sequence=43)

    def test_exact_floor_accepted_but_not_independently_durable(self):
        self.assertEqual(self.verify(minimum_sequence=42)['sequence'], 42)

    def test_revoked_pinned_key_rejected(self):
        with self.assertRaises(RootQuoteDenied):
            self.verify(revoked_keys={'device-01'})

    def test_wrong_root_rejected(self):
        with self.assertRaises(RootQuoteDenied):
            self.verify(root_id='different-root')

    def test_wrong_key_id_rejected(self):
        with self.assertRaises(RootQuoteDenied):
            self.verify(key_id='attacker')

    def test_tampered_signed_fields_rejected(self):
        q = self.quote()
        q['payload']['sequence'] += 1
        with self.assertRaises(RootQuoteDenied):
            self.verify(q)

    def test_unpinned_signer_rejected(self):
        foreign = Ed25519PrivateKey.generate()
        q = self.quote()
        q['signature'] = base64.b64encode(foreign.sign(canonical(q['payload']))).decode('ascii')
        with self.assertRaises(RootQuoteDenied):
            self.verify(q)

    def test_extra_fields_and_downgrade_rejected(self):
        for field, value in (('unknown', 'x'), ('schema_version', 0), ('domain', 'other')):
            p = copy.deepcopy(self.payload)
            p[field] = value
            with self.subTest(field=field), self.assertRaises(RootQuoteDenied):
                self.verify(self.quote(p))

    def test_invalid_sequence_and_nonce_rejected(self):
        for field, value in (('sequence', True), ('sequence', -1), ('nonce', 'x'*129)):
            p = copy.deepcopy(self.payload)
            p[field] = value
            with self.subTest(field=field), self.assertRaises(RootQuoteDenied):
                self.verify(self.quote(p))

    def test_malformed_base64_rejected(self):
        q = self.quote()
        q['signature'] = 'not@@base64'
        with self.assertRaises(RootQuoteDenied): self.verify(q)
        with self.assertRaises(RootQuoteDenied): self.verify(public_key='invalid')

    def test_even_a_valid_quote_cannot_enable_production(self):
        self.verify()
        with self.assertRaises(RootQuoteDenied): require_independent_root(self.quote())
        with mock.patch.dict('os.environ', {'RAIL_ALLOW_PRODUCTION': '1'}):
            with self.assertRaises(RootQuoteDenied): require_independent_root()

    def test_invalid_policy_values_rejected(self):
        for opts in ({'minimum_sequence': True}, {'challenge': 'a'*64},
                     {'key_id': ''}, {'revoked_keys': ['device-01']}):
            with self.subTest(opts=opts), self.assertRaises(RootQuoteDenied):
                self.verify(**opts)
