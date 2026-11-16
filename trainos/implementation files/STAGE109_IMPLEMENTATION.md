# TrainOS Stage 109 — Backup Storage Failure Injection

## Scope

Added targeted failure-injection coverage for backup capture, candidate restore, and no-clobber publication. The tests model backup-verification errors, ENOSPC, interrupted writes, and a competing publisher that creates the destination before the hard-link publication.

## Safety properties tested

- A capture failure does not publish a backup and temporary files are cleaned up.
- An interrupted restore write does not publish a candidate and temporary files are cleaned up.
- `os.link` no-clobber behavior preserves an already-existing destination and never overwrites it.
- A backup-verification failure does not produce a trusted published backup.

## Limitations

These are deterministic injected failures, not physical disk-full tests or power-loss tests. They do not establish durability guarantees for every filesystem, mount configuration, or storage controller. TrainOS is not certified for real-world transport control.
