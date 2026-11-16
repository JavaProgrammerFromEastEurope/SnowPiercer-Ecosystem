# TrainOS v103 — reproducible developer verification

Run commands from the extracted `trainos/` directory using Python 3.13 and pytest with the project dependencies. Linux `PR_SET_CHILD_SUBREAPER` is used in the verification harness to compensate for test-container PID 1 behavior; it is not a production safety authority.

```sh
python -m scripts.ci.verify_v103 --case strict_full --iteration 1 --timeout 600
python -m scripts.ci.verify_v103 --case combined --iteration 1 --timeout 360
python -m scripts.ci.verify_v103 --case kernel_batch --iteration 1 --timeout 900
python -m scripts.ci.verify_v103 --case kernel_workers --iteration 1 --timeout 1200
python -m scripts.ci.verify_v103 --case kernel_default --iteration 1 --timeout 2400
```

The verification harness sets ResourceWarning and DeprecationWarning to errors and passes `pytest.PytestUnraisableExceptionWarning` through pytest's own `-W` filter. It configures `PYTEST_ADDOPTS=-c PROJECT/pytest.ini` so dynamically generated pytest files outside the repository still inherit necessary pytest-asyncio configuration; this does not disable warning checks.

Worker mode remains opt-in (`TRAINOS_KERNEL_WORKERS=4`) and differs from the strictly serial default's scheduling. Re-running a saved verification case with the same iteration will overwrite the local report; use a new iteration for independent runs.

To rebuild the cumulative ZIP with the predecessor ZIP accessible:

```sh
TRAINOS_V102_SOURCE=/path/to/TrainOS-v102-source.zip \
TRAINOS_V103_OUTPUT=/path/to/TrainOS-v103-source.zip \
python -m scripts.ci.build_v103_archive
```

The build tool hashes every packaged member except the self-referential manifest, checks that all v102 manifest members survive in v103, checks ZIP CRC and every SHA-256, validates restored executable bits and writes the ZIP SHA-256 checksum next to the archive.

**Development readiness status: BLOCKED / NO-GO.** Green verification does not establish SIGKILL containment of the Runner, production PID 1/cgroup semantics, cross-UID isolation or physical SnowPiercer integration readiness.
