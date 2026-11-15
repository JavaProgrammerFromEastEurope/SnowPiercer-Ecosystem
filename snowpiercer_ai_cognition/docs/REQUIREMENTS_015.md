# AI-CORE-015 — requirements and evidence

Status: PARTIAL. Safety-critical: NO-GO.

- R015-01: The new production015 entrypoint MUST use JournaledAdmissionGateway for all admission requests. Implemented; cross-UID IPC exercised.
- R015-02: A PREPARED or invalid phase journal MUST prevent socket publication. Implemented; tested with subprocesses.
- R015-03: Recovery MUST NOT be available over the production IPC endpoint. Implemented; tested.
- R015-04: A restart after SIGKILL in a clean state MUST retain replay protection. Implemented; tested.
- R015-05: Prior library APIs MUST remain importable. Implemented; legacy regression executed.
- R015-06: Every historical production entrypoint MUST be unable to bypass the phase journal. NOT MET: production012/013 remain runnable.
- R015-07: Real SIGKILL at each commit/checkpoint boundary, followed by authorized cold recovery, MUST be demonstrated. NOT MET.
- R015-08: A recovery permit MUST be single-use and durable. Inherited from production012, but not verified end-to-end for cold recovery in this Stage.
- R015-09: Concurrent multi-process admissions and coherent rollback of DB/checkpoint/journal MUST be independently tested. NOT MET for the new production015 entrypoint.

## Interface contract

Entrypoint: `python -m ai_cognition.production015 /secure/config.json`.
Configuration extends v013 with `phase_journal` (pre-provisioned regular 0600 file) and `phase_key` (32-byte hex secret).
`admit` and `verify` use existing newline-delimited JSON Unix socket protocol.
`recover` is denied for every UID; recovery is offline only.
A CLEAN phase and verified anchor are mandatory before socket publication.

## Safety analysis

The journal and SQLite/checkpoint remain separate durability domains. A PREPARED journal fences startup. The currently existing anchored gateway constructor requires checkpoint agreement, which prevents constructing the full recovery stack in some committed-but-unanchored crash states. Offline cold recovery requires redesign and independent evidence. File-based anchors do not defend against privileged coordinated rollback. Legacy entrypoints and direct privileged Python/SQLite calls remain bypasses. No hardware trust root, fsync power-loss test, or systemd production deployment was demonstrated.

## Test evidence

`evidence/stage015_run1.txt` and `evidence/stage015_run2.txt`: 135 passed, 4 skipped, 26 subtests passed. ResourceWarning and DeprecationWarning treated as errors. One of the four skips is the new inherited supervisor test which hardcodes the old production013 entrypoint. A separate earlier full run also passed. Cross-UID tests require privileged Linux fixture. No claim of full crash recovery or universal legacy fencing.
