# Stage 440

## Contract

    Assert CommandIdempotencyStore.validate_backup(backup)==()

## Verification

Run the stage test with `pytest tests/stage440`. The test is a local SQLite contract and does not establish distributed execution guarantees or disaster-recovery RPO/RTO.
