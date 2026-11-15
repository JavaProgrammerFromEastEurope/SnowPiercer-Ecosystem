# Safety analysis

Confirmed: local tests reject legacy permit issuance via the new opt-in subclass; SIGKILL probe verifies a child is killed after fsync; three complete local regressions pass. Unconfirmed: actual four-UID distributed ledger transaction, client-to-authority-to-witness integration, TOCTOU-free access, privileged bypass exclusion, anchor anti-rollback, full crash consistency. Existing service permits a witness CAS -> local anchor update crash gap that quarantines on restart. Root can rewrite locally held state. No safety certification. BLOCKED/NO-GO.
