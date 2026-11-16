# Stage 442 — Reject unsupported audit decisions

## Scope

Injects an audit decision outside the supported decision vocabulary and checks validation reports the invalid decision.

## Contract

Only explicitly supported reconciliation decisions are accepted.

## Verification

Automated test: `tests/stage442/`. The release manifest records the aggregate targeted and regression test results.
