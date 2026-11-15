# LIFE-CORE-004 — Persistent Lifecycle & Recovery

Cumulative Stage: LIFE-CORE-002 registry, LIFE-CORE-003 lifecycle and LIFE-CORE-004 durable journal. No prior source modules or tests have been modified.

## Usage

```python
from lifesupport.core.persistence import PersistentLifecycle
from lifesupport.core.registry import Registry
import json
registry = Registry.from_dict(json.load(open('data/registry.json')))
with PersistentLifecycle(registry, 'lifesupport-journal.sqlite3') as journal:
    event = journal.transition('LIFE-CORE-001', 'INITIALIZING', event_id='unique-event-id', actor='operator', reason='simulation')
```

Replace the example component ID with a real ID in `data/registry.json`. The journal is an offline simulation; never connect it directly to actuators.

Run: `PYTHONPATH=src python -m unittest discover -s tests -v`.
