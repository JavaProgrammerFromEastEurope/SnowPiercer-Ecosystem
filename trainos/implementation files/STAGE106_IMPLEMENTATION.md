# Stage 106 — Recovery ownership race regression

## Scope

Stage 106 adds deterministic regression coverage around three critical ownership
boundaries in the recovery-attempt journal:

1. A stale owner cannot finish an attempt after an explicitly authorized retry
   has acquired a new `owner_run_id` and monotonically incremented fencing token.
2. Lease renewal and terminal completion issued concurrently through independent
   SQLite connections serialize safely. Completion can win, after which renewal
   must be rejected; if renewal wins first, completion may then succeed.
3. A still-live owner cannot mark an attempt successful after its lease has expired.

## Verification

Run focused tests with:

```bash
PYTHONPATH=. pytest -q tests/stage106 tests/stage105 tests/stage104
```

Then run the full project suite, Python compilation, and an AST parse audit.

## Limitations

These tests validate local SQLite state transitions, not distributed locking,
remote hosts, PID namespace identity, or enforcement of fencing tokens by external
resources. A successful journal transition cannot by itself fence side effects in
systems that do not validate the token.
