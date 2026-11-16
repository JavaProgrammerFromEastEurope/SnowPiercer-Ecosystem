"""ISLAND-GEO-021: signed direct-client broker admission, replay, privileges."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from island.anchored_admission import AdmissionDenied
from island.attested_broker import (sign_admission, verify_admission, AttestedWriteBroker,
                                   AttestedAdmissionFacade, SignedAdmissionClient,
                                   _read_private_file, ALL_CRASH_POINTS, _message)


def keys():
    sk = Ed25519PrivateKey.generate()
    private = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private, public


class AttestationTests(unittest.TestCase):
    def test_signed_canonical_success(self):
        private, public = keys()
        envelope = sign_admission(b'geotechnical measurement', private, 23001, 23003,
                                  nonce='a'*32)
        self.assertEqual(verify_admission(envelope, public, 23001, 23003),
                         (b'geotechnical measurement', 'a'*32))

    def test_tampered_payload_and_signature(self):
        private, public = keys()
        envelope = sign_admission(b'approved', private, 23001, 23003)
        for field, value in [('payload', '666f72676564'), ('broker_uid', 23002),
                             ('client_uid', 23004), ('nonce', 'b'*32), ('protocol', 'wrong')]:
            edited = json.loads(json.dumps(envelope))
            edited['message'][field] = value
            with self.assertRaises(AdmissionDenied, msg=field):
                verify_admission(edited, public, 23001, 23003)
        edited = json.loads(json.dumps(envelope))
        edited['signature'] = '0'*128
        with self.assertRaises(AdmissionDenied):
            verify_admission(edited, public, 23001, 23003)

    def test_wrong_signer_and_identity(self):
        private, public = keys()
        _, other_public = keys()
        envelope = sign_admission(b'measurement', private, 23001, 23003)
        for candidate, uid in [(public, 23004), (other_public, 23001)]:
            with self.assertRaises(AdmissionDenied):
                verify_admission(envelope, candidate, uid, 23003)

    def test_invalid_request_schemas(self):
        private, public = keys()
        envelope = sign_admission(b'ok', private, 23001, 23003)
        for candidate in [None, {}, {'message': envelope['message']},
                          {'message': envelope['message'], 'signature': envelope['signature'], 'extra': True}]:
            with self.assertRaises(AdmissionDenied):
                verify_admission(candidate, public, 23001, 23003)
        for payload in [b'', b'x'*4097, 'notbytes']:
            with self.assertRaises(AdmissionDenied):
                sign_admission(payload, private, 23001, 23003)
        with self.assertRaises(AdmissionDenied):
            _message(b'ok', 'wrong', 23001, 23003)
        with self.assertRaises(AdmissionDenied):
            AttestedWriteBroker('/tmp/sock','/tmp/db','/tmp/authority','/tmp/key',1,2,4,'invalid')

    def test_nonce_is_durable_before_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'ledger.db'
            with patch('island.write_broker.os.geteuid',return_value=23003):
                broker=AttestedWriteBroker('/x','/y','/z','/k',23001,23002,23004)
            broker.db=db
            env={'message':{'nonce':'c'*32}}
            broker._burn_nonce('c'*32,env)
            with self.assertRaises(AdmissionDenied):
                broker._burn_nonce('c'*32,env)
            with closing(sqlite3.connect(db)) as conn:
                row=conn.execute('SELECT nonce FROM signed_nonces').fetchone()
            self.assertEqual(row[0],'c'*32)

    def test_private_key_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'key'
            path.write_bytes(b'a'*32)
            os.chmod(path,0o600)
            self.assertEqual(_read_private_file(path,os.geteuid(),32),b'a'*32)
            os.chmod(path,0o644)
            with self.assertRaises(AdmissionDenied):
                _read_private_file(path,os.geteuid(),32)
            os.chmod(path,0o600)
            link=Path(tmp)/'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                _read_private_file(link,os.geteuid(),32)

    def test_four_uid_separation(self):
        with patch('island.attested_broker.os.geteuid',return_value=23002):
            with self.assertRaises(AdmissionDenied):
                AttestedAdmissionFacade('/a','/b',23001,23002,23004)

    def test_client_disallows_unsigned(self):
        with self.assertRaises((AdmissionDenied,OSError)):
            SignedAdmissionClient('/nonexistent/island.sock',23002).admit({'unsigned':1})

    def test_crash_point_registry(self):
        self.assertEqual(len(set(ALL_CRASH_POINTS)),len(ALL_CRASH_POINTS))
        self.assertIn('after_nonce_commit',ALL_CRASH_POINTS)
        self.assertIn('after_witness_cas',ALL_CRASH_POINTS)

if __name__=='__main__':unittest.main()
