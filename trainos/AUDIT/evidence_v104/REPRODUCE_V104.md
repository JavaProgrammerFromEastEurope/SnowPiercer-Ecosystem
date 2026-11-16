# TrainOS v104 — evidence reproduction

Run from the `trainos/` source root, using Python 3.13 with project requirements
installed. On Linux, `/proc` and `prctl(PR_SET_CHILD_SUBREAPER)` are mandatory for
the external supervisor. The tool does **not** require writable cgroups to run;
this is a limitation, not a production security guarantee.

```sh
# Independent Linux supervisor; default still sequential and per-file
PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning \
 PYTEST_ADDOPTS="-c $PWD/pytest.ini" \
 python -m scripts.ci.process_supervisor_v104 \
    --report /tmp/trainos-v104-supervised.json -- \
    python -m tests.kernel_runner

# Unique-numbered, bounded verification evidence
python -m scripts.ci.verify_v104 --case focused --iteration 100 --timeout 180
python -m scripts.ci.verify_v104 --case combined --iteration 100 --timeout 480
python -m scripts.ci.verify_v104 --case strict_full --iteration 100 --timeout 900
python -m scripts.ci.verify_v104 --case kernel_default --iteration 100 --timeout 5400
python -m scripts.ci.verify_v104 --case kernel_workers --iteration 100 --timeout 1800
python -m scripts.ci.verify_v104 --case kernel_batch --iteration 100 --timeout 900
```

The 24-stage registry is defined in `tests/kernel_runner/config.py`. The three
`strict_full` attempts, three `combined` attempts, and serial/worker/batch
attempts are independent cases, not aliases. `combined` targets recovery,
ci_release and pytest_diagnostics. Do not overwrite attempt IDs, treat
interrupted runs as PASS, or disable ResourceWarning / DeprecationWarning.

For isolation in environments where PID 1 does not reap orphans, broad pytest
regressions use the existing v103 `run_with_subreaper.py` harness. Kernel Runner
cases use the new v104 external **active-kill** supervisor. The distinction is
recorded in each command and report.

After successful reproducibility review, build with:

```sh
TRAINOS_V103_SOURCE=/path/to/TrainOS-v103-source.zip \
 TRAINOS_V104_OUTPUT=/path/to/TrainOS-v104-source.zip \
 python -m scripts.ci.build_v104_archive
```

Exit-code policy: `0` = all validations passed; `124` = deadline; `125` =
residual/orphan or unverified cleanup; `128+signal` = interrupted/killed
runner. Nonzero results MUST remain visible in the evidence.
