# TrainOS v105 — independent reproduction

Working directory: `trainos/` (the only project root inside ZIP). Use CPython >=3.11 with pytest and required test dependencies. Evidence below was generated on Linux Python 3.13.5. The available container has cgroup v2 read-only; the production gate is expected to refuse startup.

## Preflight

```sh
python -m pytest --version
python -m pytest -q -W error::ResourceWarning -W error::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning tests/domains/ci_release/test_v105_process_identity_and_admission.py tests/ledger_contract/test_financial_ledger_v105.py
python -m scripts.ci.process_supervisor_v105 --production -- python -c 'print("must not run")'
```

The `--production` command **must fail with code 125** until an OS-managed production cgroup authority is independently implemented and verified. Non-Linux platforms cannot claim pidfd/subreaper isolation.

## Verification matrix — never overwrite attempts

```sh
for n in 1 2 3; do python -m scripts.ci.verify_v105 --case strict_full --iteration "$n" --timeout 900; done
for n in 1 2 3; do python -m scripts.ci.verify_v105 --case combined --iteration "$n" --timeout 480; done
python -m scripts.ci.verify_v105 --case kernel_default --iteration 1 --timeout 3000
python -m scripts.ci.verify_v105 --case kernel_workers --iteration 1 --timeout 1800
python -m scripts.ci.verify_v105 --case kernel_batch --iteration 1 --timeout 1800
python -m scripts.ci.warning_probe_v105
python -m scripts.ci.probe_supervisor_selfkill_v105
python -m scripts.ci.process_boundary_probes_v105
PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning python -m scripts.ci.stress_financial_ledger_v105
```

Harness writes individual stdout/stderr, JSON, `.exitcode`, and supervisor reports to `AUDIT/evidence_v105/`. Successful strict cases require **exit 0 and complete output**. If a case fails, retain its files and choose the next unused attempt number on rerun. The `warning_probe` intentionally records pytest exit 1, requiring exactly two expected failures. Historical v104 evidence is not modified.

## Interpretation

A serial Kernel Runner PASS requires every configured file (one pytest process per file) and the `ALL CONFIGURED STAGES PASSED` marker. Worker mode requires a separate all-area PASS; batch mode is non-equivalent. `process_supervisor_v105` includes a per-run subreaper/pidfd cleanup but cannot enforce cleanup after *its own* SIGKILL without an independent OS authority. Production admission rejection is intentional and is **not** an accepted production start.
