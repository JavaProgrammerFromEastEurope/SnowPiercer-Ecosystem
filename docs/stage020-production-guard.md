# ISLAND-GEO-019 — Architecture and safety case (partial)

Production entrypoint: `python -m island.guarded_runtime`. This opt-in entrypoint subclasses the isolated service, adds private SQLite and sidecar checks, witness endpoint inode inspection, SO_PEERCRED verification and an exclusive service-lifetime startup lease. Startup consumes a state-bound permit and reconciles SQLite/phase/witness before publishing the service socket.

Trust model: Linux UID DAC protects separate service/witness private directories; root remains fully trusted. Sticky root-owned IPC directory prevents cross-UID unlink but does not protect against root or same-UID substitution. Kernel peer UID is checked on a live connection. The local file preflight is subject to TOCTOU; no immutable handle to the path is retained.

Safety decision: BLOCKED/NO-GO for production security and physical construction. The service UID can still import the legacy library and write to its own SQLite, so mandatory OS-enforced legacy fencing is NOT IMPLEMENTED. No exhaustive SIGKILL matrix or independent witness rollback-resistant anchor has been proven.

Reproduction: `PYTHONPATH=. python -W error::ResourceWarning -W error::DeprecationWarning -m unittest discover -s tests -p 'test_stage*.py'`; privileged disposable Linux harness: `python tests/stage020_multiuid.py`. Never run the UID harness on a production host.
