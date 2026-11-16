# TrainOS v107 — verification runbook (non-production host)

The source ZIP contains cumulative tests and evidence. These commands are
**development verification only** and never grant production admission.

From extracted `trainos/` using Python >=3.13 and pytest:

```sh
python -m scripts.ci.cgroup_watchdog_v107 --probe
python -m pytest -q -W error::ResourceWarning -W error::DeprecationWarning \
  -W error::pytest.PytestUnraisableExceptionWarning \
  tests/domains/ci_release/test_production_watchdog_v107.py \
  tests/domains/ci_release/test_uid_broker_v107.py
python -m scripts.ci.process_boundary_probes_v107
python -m scripts.ci.probe_doublefork_selfkill_v107
python -m scripts.ci.probe_runner_signals_v107
python -m scripts.ci.warning_probe_v107
```

Three independent strict full runs and three independent joint runs require
fresh iteration IDs; verification refuses to overwrite an existing attempt:

```sh
python -m scripts.ci.verify_v107 --case strict_full --iteration 20 --timeout 1500
python -m scripts.ci.verify_v107 --case combined --iteration 20 --timeout 1500
```

The three Kernel Runner modes use different contracts: serial per-file,
4-worker per-file with stage barriers, and batch per-domain. They cannot be
substituted for each other. The evidence JSON requires a supervisor report
with no remaining running descendants.

Never attempt to remount or emulate `/sys/fs/cgroup` for a positive production
result. A host without root-owned writable cgroup2 delegation and an OS manager
must produce a denial. The systemd service template is intentionally
non-runnable until separately configured and certified.

After all requested runs finish, build a cumulative archive with:

```sh
python -m scripts.ci.build_v107_archive
```

The build fails if active stdout logs are still being written. It then checks
preservation of every v106 file, ZIP CRC and all SHA-256 records. Retain all
failure logs; never erase incomplete attempts to manufacture a green matrix.
