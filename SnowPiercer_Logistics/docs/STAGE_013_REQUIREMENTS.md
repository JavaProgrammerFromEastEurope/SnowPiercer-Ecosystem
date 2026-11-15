# LOG-CORE-013 requirements and acceptance

R-013-01: preserve Stage 001–012 APIs and regression suite.
R-013-02: verify distinct service, witness, authority and client UIDs with real Linux kernel credentials.
R-013-03: test OS-enforced denial of direct legacy data access for non-service UIDs.
R-013-04: attest client UID on AF_UNIX connection using kernel credentials.
R-013-05: refuse production admission until independent end-to-end acceptance.
R-013-06: retain failed runs and execute three complete strict-warning regressions.

Acceptance: R-013-01,02,03,04,05 locally verified; R-013-06 results in evidence.
Outstanding: independent client-identity attestation to authority; four-service full E2E;
privileged service supervisor; all SIGKILL boundaries; anti-rollback independent trust;
OS-enforced mandatory fencing across all legacy entrypoints. BLOCKED / NO-GO.
