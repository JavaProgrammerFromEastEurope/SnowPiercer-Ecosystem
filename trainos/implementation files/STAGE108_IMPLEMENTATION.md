# TrainOS Stage 108 — Durable Backup Publication

## Scope

Harden the final publication boundary for verified SQLite backup and recovery files.

## Changes

- Flush the completed temporary SQLite file with `fsync` before publication.
- Publish with the existing atomic no-clobber hard-link operation.
- Flush the containing directory after linking and after removing the temporary name.
- If directory durability fails after linking, surface the error but preserve the target so startup reconciliation can independently verify it.
- Add fault-injection coverage for file flush failure, directory flush failure after publication, and source mutation during candidate copying.

## Validation

Run focused Stage 108 and backup/recovery regressions, the full pytest suite, Python compile checks, AST parsing, and ZIP integrity checks. Results are recorded in the Stage 108 completion report.

## Limitations

`fsync` durability depends on operating system, filesystem, mount options, and storage hardware. These tests simulate syscall failures; they do not prove behavior under every power-loss or device-failure mode. Hard-link publication intentionally fails closed on filesystems that do not support it.
