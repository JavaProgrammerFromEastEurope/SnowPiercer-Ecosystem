# LOG-CORE-015 Contracts
Authority actions: `issue_attested(scope,client_uid)` from operator UID -> `permit`; `attest(scope,permit)` from client UID -> `attested`; `consume_attested(scope,client_uid,permit)` from service UID -> `consumed`.
Token: 64 lowercase hexadecimal characters. Persist SHA256 digest, UID, scope, attested, used; never persist plaintext token.
Authority protocol is deliberately distinct from stage009 issue_client/consume_client; old classes remain unchanged.
Recovery returns `admission_only: true`; no ledger repair guarantee.
