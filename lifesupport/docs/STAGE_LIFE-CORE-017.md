# LIFE-CORE-017 — Supervised Production Writes & Crash-Safe Request Reconciliation

Linux only for real cross-UID operation. Provision protected v2 SQLite journal offline, a private DB directory owned by service UID with mode 0700, and a separate service-owned socket directory mode 0711. Run the supervisor under the already-provisioned dedicated non-root UID, NOT root:

```python
from lifesupport.core.reconciled_write import ProductionWriteSupervisor
s=ProductionWriteSupervisor('data/registry.json','/private/life.db','/public/life.sock',allowed_uids={65534})
s.run(max_restarts=None)
```

Authorized client sends newline-terminated JSON `{'op':'transition','request_id':'unique','component_id':'...','next_state':'INITIALIZING','event_id':'...','reason':'...'}`. On uncertain result, repeat the EXACT request_id and payload or query `{'op':'receipt','request_id':'unique'}`. Do not generate a new request_id for a retry. The same ID from another UID is rejected for writes and hidden from receipt queries.

Tests: `PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q`.

Limitations: crash before COMMIT leaves a lease that must expire (2s) before a new write; SQLite-only atomicity; no external physical effects; no power-loss certification; no root/service-UID defense; no guarantee against database rollback; supervisor itself needs OS supervision.
