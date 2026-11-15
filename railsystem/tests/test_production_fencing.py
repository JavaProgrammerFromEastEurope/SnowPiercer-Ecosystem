import base64
import os
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from railsystem.anchored_admission import initialize, _connect
from railsystem.production_fencing import inspect_fence, recover_with_attestation, IndependentAnchorUnavailable
from railsystem.trust import canonical
from railsystem.trusted_admission import AdmissionError

class Anchor:
    def __init__(self, seq=0, nonce=''): self.value = (seq, nonce)
    def read(self): return self.value

class ProductionFencingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'state'
        self.root.mkdir(mode=0o700)
        initialize(self.root)
        self.key = Ed25519PrivateKey.generate()
        self.pub = base64.b64encode(self.key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)).decode()
    def permit(self, seq=1, action='reconcile', pid='a'*24):
        payload = {'domain':'snowpiercer.railsystem.recovery.v1','sequence':seq,'action':action,'permit_id':pid}
        return {'payload':payload,'signature':base64.b64encode(self.key.sign(canonical(payload))).decode()}
    def prepare(self):
        c = _connect(self.root)
        try:
            c.execute('BEGIN IMMEDIATE')
            c.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='nonce1' WHERE id=1")
            c.execute('COMMIT')
        finally: c.close()
    def test_default_denies(self):
        with self.assertRaises(IndependentAnchorUnavailable): inspect_fence(self.root)
    def test_matching_external(self): self.assertEqual(inspect_fence(self.root, Anchor())['status'], 'CONSISTENT')
    def test_external_rollback_or_advance_denied(self):
        for a in (Anchor(1,'nonce1'), Anchor(-1,'')):
            with self.assertRaises(AdmissionError): inspect_fence(self.root,a)
    def test_prepared_denied(self):
        self.prepare()
        with self.assertRaises(AdmissionError): inspect_fence(self.root,Anchor())
    def test_signed_recovery_and_replay(self):
        self.prepare()
        self.assertEqual(recover_with_attestation(self.root,provider=Anchor(),permit=self.permit(),recovery_public_key=self.pub)['status'],'RECOVERED')
        self.prepare()
        with self.assertRaises(AdmissionError): recover_with_attestation(self.root,provider=Anchor(),permit=self.permit(),recovery_public_key=self.pub)
    def test_forged_permit_denied(self):
        self.prepare(); p=self.permit(); p['payload']['permit_id']='b'*24
        with self.assertRaises(AdmissionError): recover_with_attestation(self.root,provider=Anchor(),permit=p,recovery_public_key=self.pub)
    def test_wrong_scope_denied(self):
        self.prepare()
        with self.assertRaises(AdmissionError): recover_with_attestation(self.root,provider=Anchor(),permit=self.permit(action='release'),recovery_public_key=self.pub)
    def test_missing_external_denied(self):
        self.prepare()
        with self.assertRaises(IndependentAnchorUnavailable): recover_with_attestation(self.root,permit=self.permit(),recovery_public_key=self.pub)
    def test_symlink_denied(self):
        link=Path(self.tmp.name)/'link'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(AdmissionError): inspect_fence(link,Anchor())
