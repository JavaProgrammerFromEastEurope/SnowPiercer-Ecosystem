# LIFE-CORE-007

## Installation and verification
From `lifesupport/`: `PYTHONPATH=src python -m unittest discover -s tests -v`.

## Usage
```python
from lifesupport.core.admission import AdmittedLifecycle
with AdmittedLifecycle(registry, 'journal.sqlite') as store:
    token = store.acquire('instance-A', ttl_ns=5_000_000_000)
    store.protect(token)  # explicit irreversible opt-in migration
    store.transition(component_id, 'INITIALIZING', event_id='evt-1', reason='startup', actor='test', token=token)
```

Do not treat this as production-ready: no real hardware control, no OS-level privilege separation, and no tamper-resistant trust anchor.
