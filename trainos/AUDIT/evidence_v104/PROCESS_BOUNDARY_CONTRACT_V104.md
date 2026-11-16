# TrainOS v104 — additive process boundary contract

## Compatibility

Unchanged public interfaces: `KernelTestRunner.__init__`, `.run`,
`._run_test`, `._run_batch`, `._expand` and `tests.kernel_runner.__main__`.
`STAGES` remains functional-domain based; legacy test files and pinned
assignments are retained. Default remains ordered **one subprocess per file**,
with immediate fail-fast within a stage and before advancing to later stages.
`TRAINOS_KERNEL_WORKERS=4` opts into 4 concurrent per-file subprocesses;
`TRAINOS_KERNEL_BATCH=1` opts into a batch per stage. Neither is proof of the
strictly serial default.

## New opt-in interface

`python -m scripts.ci.process_supervisor_v104 [--report PATH] [--timeout SEC] [--grace SEC] [--poll SEC] -- COMMAND ...`

- Runs COMMAND as its own POSIX session and adopts orphaned descendants.
- Preserve COMMAND exit code unless leaked descendants make a successful exit
  fail closed with `125`.
- Wrapper signal SIGTERM/INT triggers bounded termination of COMMAND.
- Timeout is a distinct wrapper boundary with exit `124`.
- If COMMAND leader receives SIGKILL, wrapper returns `137` after attempting
  adopted-descendant cleanup; the attached report records its outcome.
- Malformed inputs or unsupported OS are denied with `125`.
- Report path must be owned and protected by the caller; no trusted attestation
  or cross-UID checks are claimed by this developer harness.

## Operational boundaries

Never treat the opt-in wrapper alone as mandatory production admission. An
independent, privileged production service manager with writable cgroup
containment and pinned process identity is a separate integration deliverable.
