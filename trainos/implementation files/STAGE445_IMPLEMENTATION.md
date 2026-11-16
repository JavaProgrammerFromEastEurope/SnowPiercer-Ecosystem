# Stage 445 — Clean temporary files after publish failure

## Scope

Simulates an operating-system hard-link publication failure and verifies the error propagates while neither destination nor temporary file remains.

## Contract

Failed publication is visible to the caller and cleans up the temporary snapshot.

## Verification

Automated test: `tests/stage445/`. The release manifest records the aggregate targeted and regression test results.
