# TrainOS v106 — reproduction commands

## Preparing v105 ZIP reproducibly

Extract into a new directory and **restore executable bits** encoded in Unix ZIP metadata. Standard Python `zipfile.extractall` does not restore them. Check all 4,971 v105 manifest hashes against the archived bytes before editing. Evidence of the initial mode-bit error is retained as `strict_full_1.*`.

Working directory is the extracted `trainos/`. Requires CPython >=3.11, pytest and the dependencies already used in the v105 workspace. On non-Linux systems subreaper/pidfd safety probes must not be marked PASS.

## Negative boundary checks

```sh
python -m scripts.ci.cgroup_authority_v106 --probe
python -m pytest -q -W error::ResourceWarning -W error::DeprecationWarning tests/domains/ci_release/test_cgroup_authority_v106.py
python -m scripts.ci.process_boundary_probes_v106
python -m scripts.ci.probe_doublefork_selfkill_v106
python -m scripts.ci.warning_probe_v106
python -m scripts.ci.cgroup_authority_v106 --production --delegated-root /sys/fs/cgroup/trainos-authority --service-uid 65534 --client-uid 65533 -- python -m scripts.ci.process_supervisor_v105 -- python -c 'print("MUST NOT RUN")'
```

The last command must return code 125 on this host. A successful `--probe` prints host facts only, **never** authorizes production. Negative-control pytest is expected to fail its two warning tests and is recorded separately from full regression.

## Strict matrix (new attempt number for each repetition)

```sh
for i in 1 2 3; do python -m scripts.ci.verify_v106 --case strict_full --iteration "$i" --timeout 1200; done
for i in 1 2 3; do python -m scripts.ci.verify_v106 --case combined --iteration "$i" --timeout 900; done
python -m scripts.ci.verify_v106 --case kernel_default --iteration 1 --timeout 3600
python -m scripts.ci.verify_v106 --case kernel_workers --iteration 1 --timeout 2400
python -m scripts.ci.verify_v106 --case kernel_batch --iteration 1 --timeout 1200
```

**Never overwrite failed attempts.** Case-specific stdout, stderr, exitcode, command, start time, timeout and source hashes are preserved; the archive builder will classify incomplete runs as not confirmed. `strict_full_1` failed in this container due to lost Unix execute mode, so a further new iteration is necessary for three successful runs. Run `python -m scripts.ci.build_v106_archive` only after collecting all currently running processes and final exit codes.

## Independent production certification

Do not simulate root delegation with `/tmp`. Provision a separate authorized Linux host with real writable cgroup v2 and a separate OS service manager. Test `SIGKILL` at every pre-exec cgroup attachment boundary, genuine cgroup.kill containment, authority restart after SIGKILL, cross-UID peer-authenticated IPC and explicit OS DAC legacy-state fencing. These must be documented independently before any GO.
