# Stage 435: Serialize concurrent publication to one destination

## Contract

Concurrent attempts cannot overwrite one another; exactly one publishes.

## Verification

Covered by `tests/stage435/test_stage435_backup_recovery.py`.
