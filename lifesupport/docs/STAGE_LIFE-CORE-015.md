# LIFE-CORE-015 — Supervised Cross-UID IPC & Transactional Fault-Injection Expansion

## API

```python
from lifesupport.core.supervised_cross_uid import CrossUIDSupervisor, verified_request
supervisor = CrossUIDSupervisor(registry, db, socket_path, allowed_uids={client_uid})
supervisor.run(max_restarts=3)
# Client: verified_request(socket_path, 'health', expected_uid=service_uid)
```

The supervisor must be launched as the provisioned service UID; it does **not** switch UID itself. Separate private DB directory (0700) and public IPC directory (0711), both owned by the service UID, are mandatory. Clients must be in `allowed_uids`; the service UID is excluded. The interface is read-only. See architecture and safety documents.

## Regression

`PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q`

Tests run against Linux container; results are not hardware certification.
