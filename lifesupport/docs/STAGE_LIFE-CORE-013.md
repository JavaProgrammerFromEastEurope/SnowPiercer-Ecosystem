# LIFE-CORE-013

## Local offline supervisor

```sh
PYTHONPATH=src python -m lifesupport.supervisor_cli --registry data/registry.json --db /private/dir/life.db --socket /private/dir/life.sock
```

The socket parent must already exist, be owned by the running UID, and be mode 0700. The supervisor restarts the service on SIGKILL; terminate the supervisor to stop. The supervisor's own failure is not automatically recovered.

Production policy check: append `--production --client-uid <DIFFERENT_UID>`. This is a **fail-closed configuration gate**, not a proof of OS-level isolation or a cross-UID interface. It intentionally leaves all physical write operations unavailable. Do not use for life-critical actuation.

Run regression:

```sh
PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -v
```
