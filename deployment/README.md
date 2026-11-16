# ISLAND-GEO-022 deployment policy requirements (NOT INSTALLED)

**No executable production deployment is certified.** This directory is an architectural specification, not an active enforcement policy. A unit file or UID table is not proof of MAC confinement.

- Privileged orchestrator must provision and supervise distinct unprivileged identities: client, facade, broker, witness, recovery authority, independent root (six UID, minimum).
- Only broker may write its SQLite ledger; only witness UID writes witness DB; only recovery authority UID writes permit DB; only the monotonic provider controls its root. Each stores its own private keys. Root-owned sticky IPC namespace is a lab mechanism; pin peer credential + socket inode.
- Mandatory LSM mediation **must** prevent broker UID code from starting arbitrary Python or loading legacy production entrypoints; filesystem DAC by itself **cannot** achieve this. Merely setting `NoNewPrivileges=yes`, `AppArmorProfile=...`, or `SELinuxContext=...` without verified policy does not demonstrate confinement.
- A hardware-backed monotonic resource (e.g. TPM NV counter with measured and attested policy) needs real anti-rollback evidence. A signed SQLite root, even on a sixth UID, is not equivalent.
- Service-manager must enforce pre-exec policy, restart broker/witness/permit independently, manage residual sockets and prevent concurrent startup. The host in which tests ran has PID1 `supervisord`, not systemd. No unit is active.
- Strict broker entrypoint **always denies in this release** because no certified root verifier, MAC assessment and lifecycle attestor are implemented. It does so prior to startup lease/permit consumption/IPC bind.
- Recovery after root-witness split CAS failure requires an audited out-of-band recovery procedure; never automatically force local or root state to match.
- `lab-root` and `lab-broker` are TEST ONLY. They do not enable production. Root test orchestrator can reset or replace all file systems and UIDs.

**Production Security: BLOCKED/NO-GO. Physical construction and operations: BLOCKED/NO-GO.**
