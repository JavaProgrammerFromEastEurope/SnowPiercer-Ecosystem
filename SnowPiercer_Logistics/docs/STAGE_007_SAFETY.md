# LOG-CORE-007 Safety analysis
Verified locally: UID gate against current UID, permit replay denial, scope mismatch denial, persistence over broker restart, inherited 37 tests.
Not verified: cross-UID deployment, attacker controlled socket path, rollback-resistant authority, simultaneous multiple consumer processes, SIGKILL at each SQLite/CAS/IPC boundary, end-to-end physical actuation, independent external audit.
Hazards: token theft; authority DB rollback restoring used=0; post-consume crash losing permit; direct legacy recovery bypass; directory or socket substitution by privileged adversary; permissive filesystem ACLs. Controls needed: separate OS principals and protected directories, trusted anchor, mandatory production interface, comprehensive fault injection.
Decision: BLOCKED / NO-GO.
