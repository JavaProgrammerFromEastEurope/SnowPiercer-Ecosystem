# SnowPiercer Life Support — LIFE-CORE-002

Offline engineering prototype. Requires Python 3.11+. No third-party runtime dependencies.

```bash
cd lifesupport
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m lifesupport.cli data/registry.json
PYTHONPATH=src python -m lifesupport.cli data/registry.json --trace LIFE-CONTROL-001
```

The JSON schema describes a transport envelope, not validated domain-specific payloads. The runtime validator intentionally refuses `LifeCommand`.
Do not connect this prototype to life-critical equipment.

## Files
- `data/registry.json`: 20 domain reference components, 24 registry-level requirements
- `src/lifesupport/core/registry.py`: consistency and graph validation
- `src/lifesupport/core/contracts.py`: message envelope validation, commands disabled
- `contracts/envelope.schema.json`: schema draft
- `tests/`: offline unit tests
- `evidence/`: test and checksum evidence

## LIFE-CORE-003
See `docs/STAGE_LIFE-CORE-003.md`, `architecture/LIFECYCLE.md`, `requirements/LIFECYCLE_REQUIREMENTS.md`, `contracts/lifecycle-*.schema.json` and `evidence/LIFE-CORE-003_TEST_RESULTS.txt`. The lifecycle model is offline only.

## Current cumulative stage: LIFE-CORE-021

Package version 0.21.0 adds strict read-only telemetry admission for integration.
See `docs/STAGE_LIFE-CORE-021.md`, `requirements/TELEMETRY_REQUIREMENTS.md`,
`contracts/telemetry-admission.schema.json`, and `integration_probe.py`.
The historical registry baseline remains unchanged. No physical or clinical
readiness is asserted; operation remains NO-GO.
