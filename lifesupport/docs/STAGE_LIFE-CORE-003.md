# LIFE-CORE-003 — System State Model & Lifecycle Management

## Installation and tests
Python 3.11+ recommended. Standard library only.

```bash
cd lifesupport
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Example (offline only)
```python
from lifesupport.core.registry import Registry
from lifesupport.core.lifecycle import Lifecycle, State
registry = Registry.load('data/registry.json')
engine = Lifecycle(registry)
engine.transition('LIFE-CORE-001', State.INITIALIZING,
                  event_id='example-1', reason='offline example', actor='simulation')
assert engine.verify_audit()
```

## Compatibility
Existing files and APIs from LIFE-CORE-002 retained unchanged. New lifecycle functionality is additive. Tests are local and do not prove TrainOS integration.

## Out of scope
Hardware actuation, real-time control, alarm escalation, persistence, secure signatures, access control, physical safety certification, distributed transactions.
