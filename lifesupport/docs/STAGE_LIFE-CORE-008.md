# LIFE-CORE-008

## Quick start

```python
from lifesupport.core.hardening import HardenedLifecycle

with HardenedLifecycle(registry, path) as life:
    token = life.acquire('recovery-coordinator', ttl_ns=1_000_000_000)
    life.protect(token)  # only if journal has not been protected yet
    life.harden(token)   # explicit v1 -> v2 upgrade
    print(life.verify_integrity())
```

Existing protected v1 journals can call `harden(token)` directly; an altered v1 journal is rejected rather than repaired. Test command: `PYTHONPATH=src python -m unittest discover -s tests -v`.

All examples are offline software-only; no real equipment may be controlled.
