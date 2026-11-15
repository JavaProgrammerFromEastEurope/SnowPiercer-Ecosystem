# LOG-CORE-017 safety case
Claim confirmed: opt-in service rejects tested divergent states and unsafe phase descriptors; existing tests pass.
Unconfirmed: production isolation, full four-UID E2E, rollback to genesis resistance, witness/SQLite atomicity, independent recovery permits across crashes, exhaustive SIGKILL boundaries, malicious filesystem substitution across all files, socket hijack, authority DB rollback, independent certification.
Threats: malicious privileged operator can rewrite all trust roots; TOCTOU exists in non-descriptor paths; a missing witness is not automatically an integrity proof; phase journal is unauthenticated; network filesystem semantics may differ.
The previous production and legacy APIs remain importable, so mandatory production fencing is NOT proven.
Decision: PARTIALLY VERIFIED / BLOCKED / NO-GO.
