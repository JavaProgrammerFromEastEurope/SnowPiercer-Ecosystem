# LIFE-CORE-016 — Operation (offline prototype)

1. On Linux, provision two distinct unprivileged UIDs: a service UID and client UID. Do **not** run the production write service as root.
2. Provision a service-owned SQLite directory (`0700`) and a separate service-owned socket directory (`0711`). The parent of both must be traversable by the client for the socket only.
3. Offline, create a `HardenedLifecycle` database, `acquire()` a fence, `protect(token)`, `harden(token)`, `release(token)`, and close. Chown the DB and its WAL/SHM files to the service UID; mode `0600`.
4. Run as the service UID:

```sh
PYTHONPATH=src python -m lifesupport.production_write_cli --registry data/registry.json --db /private/life.db --socket /ipc/life.sock --uids 65534
```

5. Client JSON lines: `{"op":"health"}`, `{"op":"snapshot"}`, or `{"op":"transition","component_id":"...","next_state":"INITIALIZING","event_id":"...","reason":"..."}`. Use `verified_request` to authenticate the connected server for health/snapshot; write-capable clients must also verify server UID/PID on the connected socket before sending requests.
6. Run regression: `PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q`.

The CLI does not switch UID. Root/service-UID access, untrusted provisioning, hardware actuation and autonomous write-service recovery are not covered.
