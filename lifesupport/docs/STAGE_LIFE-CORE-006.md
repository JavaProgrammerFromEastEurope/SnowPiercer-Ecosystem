# LIFE-CORE-006 — Recovery Coordination & Integrity Fencing

## Quick start

```python
from lifesupport.core.coordination import FencedLifecycle
with FencedLifecycle(registry, 'journal.sqlite') as store:
    token = store.acquire('worker-A', ttl_ns=5_000_000_000)
    store.recover(token=token)
    # use store.transition(..., token=token) for validated logical transitions
    store.release(token)
```

## Test
`PYTHONPATH=src python -m unittest discover -s tests -v`

## Limitations
This is an offline software prototype. Legacy `PersistentLifecycle` remains unfenced, and existing backup/checkpoint APIs are not fenced. Do not connect to hardware or deploy as a life-safety mechanism. Review `architecture/COORDINATION.md` and `safety/COORDINATION_HAZARDS.md`.
