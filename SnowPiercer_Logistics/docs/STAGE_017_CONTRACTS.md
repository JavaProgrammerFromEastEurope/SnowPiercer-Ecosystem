# LOG-CORE-017 contracts
transaction_snapshot() -> TransactionSnapshot(state, ledger_events, witness_events, phase_present).
_assert_consistent() raises AdmissionError unless snapshot.state == COMMITTED.
_admit() rejects existing phase before inherited admission, and checks consistency afterward.
_dispatch(uid,req) rejects legacy issue_permit, rejects malformed requests and checks consistency before delegation.
production_admission() always raises AdmissionError. This is deliberate NO-GO.
Compatibility: existing APIs and tests are retained. New module is opt-in and not a safety certification.
