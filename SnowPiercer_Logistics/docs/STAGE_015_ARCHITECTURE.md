# LOG-CORE-015 Architecture
Optional `DirectAttestationAuthority` extends stage009 broker without changing its legacy API.
Operator --issue_attested--> authority; client --attest--> authority; service --consume_attested--> authority.
Each connection obtains the immediate peer UID from SO_PEERCRED/getpeereid; service obtains client UID from its own peer. Authority SQLite performs conditional UPDATE on used=0 in BEGIN IMMEDIATE.
`AttestedLogisticsService` is opt-in; its recover endpoint checks local/witness agreement and no phase before permit consumption. It does not repair state.
The independent client attestation prevents service-only minting of client consent but permits bearer-token transfer and does not bind a specific Logistics transaction.
