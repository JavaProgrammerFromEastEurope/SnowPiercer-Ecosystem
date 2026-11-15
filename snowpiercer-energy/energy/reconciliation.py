"""CORE-016: explicit evidence-gated reconciliation of completed witness CAS.

Never replays a transaction, rewrites local state, or advances the witness.
A caller-supplied verifier is NOT intrinsically independent: deployment must
establish its authority and protect its evidence channel.
"""
import json
import os
import stat
from dataclasses import dataclass
from .trust import AdmissionDenied
from .trust_boundary import WitnessRecord, WitnessUnavailable
from .witness_protocol import JournaledWitnessEnergyService, PendingWitnessTransaction

@dataclass(frozen=True)
class ReconciliationEvidence:
    transaction_action: str
    previous: WitnessRecord
    observed: WitnessRecord
    witness_identity: str
    authorization_id: str

class EvidenceReconciledEnergyService(JournaledWitnessEnergyService):
    """Opt-in, fail-closed, evidence-gated cleanup of a *completed* transaction.

    Only a witness record with exactly one higher revision and an exact match
    against the local ledger/permit state can be accepted. Ambiguous local-only
    commits and failed witness CAS stay quarantined. A verifier must validate
    evidence out-of-band; no automatic success path is provided.
    """
    def reconcile_completed(self, evidence, verifier):
        self._check_pid()
        if not isinstance(evidence, ReconciliationEvidence) or not callable(verifier):
            raise AdmissionDenied('independent evidence verifier required')
        with self._mutex, self.admission.locked(), self._checkpoint_locked():
            try:
                fd = os.open(self.phase_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            except (FileNotFoundError, OSError) as exc:
                raise PendingWitnessTransaction('phase missing or inaccessible') from exc
            try:
                st = os.fstat(fd)
                if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                        or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > 4096):
                    raise PendingWitnessTransaction('unsafe phase')
                with os.fdopen(fd, 'rb') as stream:
                    fd = -1
                    phase = json.loads(stream.read().decode('utf-8'))
            finally:
                if fd >= 0:
                    os.close(fd)
            if not isinstance(phase, dict) or phase.get('version') != 1 or phase.get('action') not in ('issue', 'recover', 'simulate'):
                raise PendingWitnessTransaction('invalid phase')
            old = WitnessRecord(phase['revision'], phase['sequence'], phase['digest'], phase['permit_fingerprint'])
            if old != evidence.previous or evidence.transaction_action != phase['action']:
                raise PendingWitnessTransaction('evidence does not bind phase')
            try:
                current = self.witness.read()
            except Exception as exc:
                raise WitnessUnavailable('witness unavailable') from exc
            if (not isinstance(current, WitnessRecord) or current != evidence.observed
                    or current.revision != old.revision + 1 or current == old):
                raise PendingWitnessTransaction('witness did not durably advance as expected')
            if self._local_record(current.revision) != current:
                raise PendingWitnessTransaction('local state differs from witness')
            try:
                approved = verifier(evidence)
            except Exception as exc:
                raise PendingWitnessTransaction('independent evidence verification failed') from exc
            if approved is not True:
                raise PendingWitnessTransaction('independent evidence rejected')
            # Re-check after verifier may have blocked; no silent acceptance of drift.
            if self.witness.read() != current or self._local_record(current.revision) != current:
                raise PendingWitnessTransaction('state changed during evidence verification')
            self._phase_clear()
            return current
