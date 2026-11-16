# SnowPiercer — Integration & Operations (SP-OPS)

Foundation release **v0.1.0**, 15 November 2026. Extracted from `TrainOS_Workspace(5).zip`; no other module release was silently upgraded. This package implements an offline **NO-GO** inventory and dependency/evidence observer, not an independent permit authority, integration E2E environment or operational controller.

From the SnowPiercer workspace root:

```sh
python3 tools/run_ops_assessment.py
python3 -W error::ResourceWarning -W error::DeprecationWarning -m unittest discover -s subsystems/operations/tests -v
```

Default assessment: `verification/ops-assessment.json`. Exit 0 means all referenced local files are present and no digest mismatch was found; **it does not indicate GO**. Exit 2 means missing/mismatched/unsafe local evidence. Any assessment remains `decision: NO_GO` and `operationalReady: false`.

Canonical snapshot: `config/catalog.json`; interface proposals: `contracts/interfaces.json`; design and gates: `docs/`. The existing six independent integration probes remain in `integration/` unchanged. There is no external protected root, MAC validation, physical HIL, signed approval or certified production deployment.
