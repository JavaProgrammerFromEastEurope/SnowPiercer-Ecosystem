# ENERGY-CORE-003 — Power Demand & Supply Accounting
Version: v0.3.0; status: simulation PASS / physical NO-GO.

## Requirements and traceability
- REQ-003-01: typed dispatch and immutable ledger -> `StorageDispatch`, `PowerLedger`; test_storage_discharge_and_charge.
- REQ-003-02: deterministic critical-first allocation -> `account`; test_priority_and_balance, test_permutation_invariance.
- REQ-003-03: power balance including reserve, charging and curtailment -> `account`; test_exhaustive_small_domain (375 valid cases).
- REQ-003-04: finite nonnegative parameters, bounded rated output and storage energy -> `account`; invalid_* tests.
- REQ-003-05: simulation-only admission -> `account`; test_mode_fence.
- REQ-003-06: preserve v0.1/v0.2 API -> existing test_domain and test_state_machine.

## Architecture and contracts
`account(EnergySystem, requests, *, duration_h, dispatch=(), reserve_kw=0)` is pure and read-only; `PowerLedger` captures a single-step accounting result. Power is in kW, energy in kWh, time in hours. `StorageDispatch.discharge_kw` is bus-side output and `charge_kw` bus-side input. Battery efficiency is applied once on each direction. Generation is the sum of rated source power, an optimistic simulation assumption. Reserve is withheld available power, not delivered or consumed. Converter behavior, line losses, battery aging, ramp limits, actual measurements and grid stability are not modeled. The ledger does not update stored energy: caller must explicitly carry `storage_after` to a new snapshot.

## Safety analysis
- Excess consumer request / duplicate ID -> reject.
- Over-rating / storage overcharge or depletion -> reject.
- Invalid nonfinite quantities -> reject.
- No source or inadequate supply -> critical-first partial allocation, unserved accounting.
- Reserve exceeds supply -> reject (fail closed).
- No persistence, cross-process fencing, authenticated commands, real-world measurement or independent safety controller. Float arithmetic is not suitable for metrology or high-assurance control. No equipment connection.

## Integration boundaries
TrainOS consumes simulation-only ledger status; AI may propose requests but cannot actuate; Rail sends simulated traction demand; LifeSupport declares critical consumers; Security receives externally forwarded safety events. These are design contracts, not implemented IPC adapters. Legacy `EnergySystem.simulate_allocation` is preserved unchanged and is NOT routed through the new reserve/storage accounting API; therefore new invariants cannot be claimed for legacy callers.

## Verification scope
Three full repository test runs, warning-as-error for ResourceWarning and DeprecationWarning; external pytest plugin autoload disabled. Exhaustive bounded enumeration of 4 dimensions 0..4 (625 combinations, 375 valid), plus deterministic permutation test. No Hypothesis dependency or unconstrained mathematical proof. Physical deployment: NO-GO.
