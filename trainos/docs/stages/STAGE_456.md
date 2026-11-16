# Stage 456: Restored Audit Persists After Reopen

## Contract

This stage adds a focused regression contract for restored audit persists after reopen. The test uses a temporary SQLite database and checks safe failure or preservation behavior without contacting an external provider.

## Verification

Run: `python -m pytest tests/stage456 -q`

## Boundary

This is a local SQLite behavior check, not a distributed-storage guarantee or payment-provider certification.
