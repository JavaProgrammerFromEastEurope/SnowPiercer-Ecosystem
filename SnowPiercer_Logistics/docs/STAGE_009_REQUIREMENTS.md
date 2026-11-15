# LOG-CORE-009 Requirements
R009-01 Preserve all previous public library APIs and regression tests.
R009-02 Bind recovery permits to original kernel-derived client UID and scope.
R009-03 Atomically consume permits once; reject replay, wrong UID, wrong scope.
R009-04 Deny legacy permit protocol in the new opt-in authority and IPC.
R009-05 Reject untrusted roles and inconsistent checkpoint/phase state.
R009-06 Require separate service, authority, witness and client OS identities and OS-enforced filesystem isolation for production. NOT VERIFIED.
R009-07 Verify cross-UID E2E, tampering and exhaustive SIGKILL points. NOT VERIFIED.
R009-08 Keep production BLOCKED/NO-GO pending independent evidence.
