import hashlib
import hmac
import os
import pytest
from energy.production_boundary import AttestedProductionEnergyService, WitnessAttestation
from energy.reconciliation import ReconciliationEvidence
from energy.trust_boundary import WitnessRecord
from energy.witness_protocol import PendingWitnessTransaction
from energy.trust import AdmissionDenied
from test_stage014 import setup
from energy.permit_anchor import AnchoredDurableEnergyService

KEY = b'external-test-verifier-key-not-production'
def verifier(issuer, payload, signature):
    return issuer == 'independent-test-only' and hmac.compare_digest(hmac.digest(KEY,payload,'sha256'),signature)

def make(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    return AttestedProductionEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp,w,verifier),w,cp

def pending(tmp_path):
    s,w,cp=make(tmp_path)
    before=w.read()
    s._phase_write(before,'issue')
    AnchoredDurableEnergyService.issue(s,os.geteuid())
    s._publish(before)
    evidence=ReconciliationEvidence('issue',before,w.read(),'test-witness','authorization-1')
    sig=hmac.digest(KEY,s.canonical_payload(evidence),'sha256')
    return s,w,cp,WitnessAttestation(evidence,'independent-test-only',sig)

def test_attested_reconciliation(tmp_path):
    s,w,cp,a=pending(tmp_path)
    assert s.reconcile_attested(a)==w.read()
    assert not (cp/'witness.phase').exists()

def test_bad_signature_fails_closed(tmp_path):
    s,w,cp,a=pending(tmp_path)
    with pytest.raises(PendingWitnessTransaction):s.reconcile_attested(WitnessAttestation(a.evidence,a.issuer,b'0'*32))
    assert (cp/'witness.phase').exists()

def test_wrong_issuer_fails_closed(tmp_path):
    s,w,cp,a=pending(tmp_path)
    with pytest.raises(PendingWitnessTransaction):s.reconcile_attested(WitnessAttestation(a.evidence,'untrusted',a.signature))

def test_modified_evidence_fails_closed(tmp_path):
    s,w,cp,a=pending(tmp_path)
    e=ReconciliationEvidence('recover',a.evidence.previous,a.evidence.observed,'test-witness','authorization-1')
    with pytest.raises(PendingWitnessTransaction):s.reconcile_attested(WitnessAttestation(e,a.issuer,a.signature))

def test_private_directory_enforced(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    p.chmod(0o755)
    with pytest.raises(AdmissionDenied):AttestedProductionEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp,w,verifier)

def test_verifier_required(tmp_path):
    adm,p,cp,w=setup(tmp_path)
    with pytest.raises(AdmissionDenied):AttestedProductionEnergyService(adm,p/'sock',[os.geteuid()],p/'permits.db',cp,w,None)
