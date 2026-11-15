# LOG-CORE-012 contracts
- `DeploymentPlan(layout).validate()` returns True or raises AdmissionError.
- `.installation_steps()` returns (absolute_root, UID, 0700) tuples.
- `install_private_roots(plan)` requires effective UID 0, refuses symlink targets and unexpected owners. No rollback of partial installation is promised.
- `require_production_entrypoint(layout, acceptance_file=...)` always denies production activation in Stage 012, including after valid preflight, pending independent attestation.
- No changes to pre-existing public function signatures.
