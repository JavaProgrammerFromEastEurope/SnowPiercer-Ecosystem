# Stage 173 — reconciliation restart windows

This stage adds regression coverage for process-restart windows around explicit `not_executed` reconciliation.

- Verifies that a reconciliation decision and its evidence persist if the process closes before a fresh dispatch reservation.
- Verifies same-evidence reconciliation remains idempotent after restart and that a conflicting later claim is rejected without mutating the saved decision.
- Verifies reconciliation of one command does not mutate an independent command and both can be reserved independently after explicit resolution.

These tests validate the local SQLite state machine only. They do not independently establish the truth of external evidence, make an external side effect atomic with SQLite, or certify safety for physical systems.
