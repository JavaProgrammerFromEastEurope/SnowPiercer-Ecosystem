"""ENERGY-CORE-014: externally supplied monotonic witness contract.

This module supplies *no* independent trust root. A deployment must provide a
separately administered witness with monotonic, durable compare-and-swap.
"""
from dataclasses import dataclass
import os
from .permit_anchor import AnchoredDurableEnergyService
from .trust import AdmissionDenied

@dataclass(frozen=True)
class WitnessRecord:
    revision: int
    sequence: int
    digest: str
    permit_fingerprint: str

class WitnessUnavailable(AdmissionDenied):
    pass

class WitnessedEnergyService(AnchoredDurableEnergyService):
    """Opt-in service. Fail closed if the witness is missing, stale or divergent.

    A witness implementation MUST persist compare_and_swap durably and reject
    revision regression. This cannot be established by this library alone.
    """
    def __init__(self, admission, path, allowed_uids, permit_db, checkpoint_dir, witness):
        if witness is None or not callable(getattr(witness, 'read', None)) or not callable(getattr(witness, 'compare_and_swap', None)):
            raise WitnessUnavailable('external witness required')
        self.witness = witness
        super().__init__(admission, path, allowed_uids, permit_db, checkpoint_dir)
        with self._mutex:
            self._verify_witness()

    def _local_record(self, revision):
        seq, digest, _ = self.admission.gateway.snapshot()
        self._verify()
        return WitnessRecord(revision, seq, digest, self._fingerprint())

    def _verify_witness(self):
        try:
            record = self.witness.read()
        except Exception as exc:
            raise WitnessUnavailable('witness read failed') from exc
        if not isinstance(record, WitnessRecord) or record.revision < 0:
            raise WitnessUnavailable('invalid witness record')
        if record != self._local_record(record.revision):
            raise AdmissionDenied('witness divergence: possible rollback or crash window')
        return record

    def _publish(self, previous):
        updated = self._local_record(previous.revision + 1)
        try:
            accepted = self.witness.compare_and_swap(previous, updated)
        except Exception as exc:
            raise WitnessUnavailable('witness update failed; manual reconciliation required') from exc
        if accepted is not True:
            raise WitnessUnavailable('witness CAS rejected; manual reconciliation required')
        self._verify_witness()

    def issue(self, uid):
        with self._mutex:
            before = self._verify_witness()
            result = super().issue(uid)
            self._publish(before)
            return result

    def recover(self, uid, token):
        with self._mutex:
            before = self._verify_witness()
            try:
                result = super().recover(uid, token)
            except AdmissionDenied:
                # A failed recovery can still consume a permit; reconcile only
                # when local state changed and the witness is still available.
                if self._local_record(before.revision) != before:
                    self._publish(before)
                raise
            self._publish(before)
            return result

    def dispatch(self, uid, req):
        if isinstance(req, dict) and req.get('action') == 'simulate':
            with self._mutex:
                before = self._verify_witness()
                result = super().dispatch(uid, req)
                self._publish(before)
                return result
        return super().dispatch(uid, req)

    def __enter__(self):
        with self._mutex:
            self._verify_witness()
            return super().__enter__()
