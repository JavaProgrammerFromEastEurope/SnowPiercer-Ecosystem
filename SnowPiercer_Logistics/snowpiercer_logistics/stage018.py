"""LOG-CORE-018: opt-in fail-closed witness recovery decision protocol.

No automatic witness CAS, ledger rewrite or recovery permit consumption occurs.
The result is an evidence-bearing decision, NOT a distributed atomic commit.
"""
from dataclasses import dataclass
import os
from .secure import AdmissionError, SecureLogisticsService
from .stage017 import QuarantinedTransactionService, _safe_json_file

@dataclass(frozen=True)
class RecoveryDecision:
    state: str
    ledger: dict
    checkpoint: dict
    witness: dict
    phase_present: bool
    permitted: bool = False


def classify_recovery(ledger, checkpoint, witness, phase=None):
    """Classify only well-formed, bounded, deterministic transaction states.

    All unresolved transitions are quarantined. No state authorizes mutation.
    """
    def valid(x):
        return isinstance(x, dict) and set(x) == {'events', 'head_hash'} and type(x['events']) is int and x['events'] >= 0 and isinstance(x['head_hash'], str) and len(x['head_hash']) == 64 and all(c in '0123456789abcdef' for c in x['head_hash'])
    if not all(valid(x) for x in (ledger, checkpoint, witness)):
        raise AdmissionError('invalid transaction anchor shape')
    if phase is not None:
        if not isinstance(phase, dict) or set(phase) != {'before', 'key', 'uid'} or not valid(phase['before']) or not isinstance(phase['key'], str) or not phase['key'] or type(phase['uid']) is not int:
            raise AdmissionError('invalid transaction phase')
        if checkpoint != phase['before']:
            state = 'QUARANTINED_PHASE_ANCHOR'
        elif ledger == checkpoint and witness == checkpoint:
            state = 'QUARANTINED_UNCOMMITTED_PHASE'
        elif ledger != checkpoint and witness == checkpoint:
            state = 'QUARANTINED_SQLITE_COMMITTED'
        elif ledger == witness and ledger != checkpoint:
            state = 'QUARANTINED_WITNESS_ADVANCED'
        else:
            state = 'QUARANTINED_SPLIT_BRAIN'
    elif ledger == checkpoint == witness:
        state = 'COMMITTED'
    else:
        state = 'QUARANTINED_DIVERGENCE'
    return RecoveryDecision(state, dict(ledger), dict(checkpoint), dict(witness), phase is not None, state == 'COMMITTED')


class EvidenceGatedLogisticsService(QuarantinedTransactionService):
    """Opt-in service: reject startup/requests on any incomplete transition.

    Inherited APIs remain available for nonproduction use; production admission
    is separately and unconditionally denied until independent E2E certification.
    """
    def recovery_decision(self):
        self._check_files()
        ledger = self._checkpoint()
        checkpoint = SecureLogisticsService._read_anchor(self)
        witness = self._read_witness()
        phase = None
        if self.phase_path.exists() or self.phase_path.is_symlink():
            phase = _safe_json_file(self.phase_path, os.geteuid())
        return classify_recovery(ledger, checkpoint, witness, phase)

    def _assert_consistent(self):
        decision = self.recovery_decision()
        if not decision.permitted:
            raise AdmissionError('recovery quarantined: ' + decision.state)

    def _admit(self):
        # Do not allow inherited startup reconciliation to mutate unresolved state.
        self._assert_consistent()
        super()._admit()
        self._assert_consistent()


def production_admission(*args, **kwargs):
    raise AdmissionError('LOG-CORE-018 NO-GO: mandatory four-UID E2E and crash-point evidence incomplete')
