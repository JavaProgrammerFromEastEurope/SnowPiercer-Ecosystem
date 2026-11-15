# LOG-CORE-012 architecture
`stage012.DeploymentPlan` validates immutable deployment layout.
`install_private_roots` is a root-only administrative primitive, not invoked by normal service startup. It opens each target directory with O_NOFOLLOW and changes owner/mode on the opened descriptor. Parent-directory trust and race-free creation are not fully established.
`require_production_entrypoint` checks preflight and a root-owned evidence file, then intentionally denies activation because a marker file cannot independently prove cross-UID isolation.
Legacy library APIs remain accessible for compatibility. Mandatory production admission is not complete.
