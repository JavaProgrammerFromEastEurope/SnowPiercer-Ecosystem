"""ENERGY-CORE-017 opt-in production boundary and attestation verification.

This is a *software policy boundary*, not an OS-enforced separation from
legacy modules. The verifier must be independently administered and trusted.
"""
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from .reconciliation import EvidenceReconciledEnergyService, ReconciliationEvidence
from .trust import AdmissionDenied
from .witness_protocol import PendingWitnessTransaction

@dataclass(frozen=True)
class WitnessAttestation:
    evidence: ReconciliationEvidence
    issuer: str
    signature: bytes

class AttestedProductionEnergyService(EvidenceReconciledEnergyService):
    """Opt-in production interface requiring externally verified attestations.

    Caller supplies verifier(issuer, canonical_payload, signature) -> bool.
    No embedded signing key, self-approval or permissive fallback.
    """
    def __init__(self, admission, path, allowed_uids, permit_db, checkpoint_dir,
                 witness, verifier):
        if not callable(verifier):
            raise AdmissionDenied('independent attestation verifier required')
        self._attestation_verifier = verifier
        self._check_private_path(Path(path).parent)
        self._check_private_path(Path(checkpoint_dir))
        super().__init__(admission, path, allowed_uids, permit_db, checkpoint_dir, witness)

    @staticmethod
    def _check_private_path(path):
        st = path.lstat()
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_mode & 0o077):
            raise AdmissionDenied('private production directory required')

    @staticmethod
    def canonical_payload(evidence):
        if not isinstance(evidence, ReconciliationEvidence):
            raise AdmissionDenied('invalid evidence')
        import json
        from dataclasses import asdict
        return json.dumps(asdict(evidence), sort_keys=True,
                          separators=(',', ':'), ensure_ascii=True).encode('ascii')

    def reconcile_attested(self, attestation):
        if (not isinstance(attestation, WitnessAttestation)
                or not attestation.issuer or type(attestation.signature) is not bytes
                or len(attestation.signature) < 16):
            raise PendingWitnessTransaction('invalid attestation')
        payload = self.canonical_payload(attestation.evidence)
        def verify(evidence):
            if evidence != attestation.evidence:
                return False
            try:
                return self._attestation_verifier(attestation.issuer, payload,
                                                  attestation.signature) is True
            except Exception:
                return False
        return self.reconcile_completed(attestation.evidence, verify)
