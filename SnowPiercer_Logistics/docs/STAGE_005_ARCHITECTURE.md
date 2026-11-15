# LOG-CORE-005 architecture

`WitnessAuthority` is a socket server with a separate monotonic.json file, protected by owner-only filesystem permissions and a lifetime flock. The kernel provides peer UID. `WitnessBackedLogisticsService` performs witness CAS before local checkpoint replacement. The CAS is serialized by the single-threaded witness server. An interrupted CAS-to-local-checkpoint window fails closed; it does not auto-repair. This architecture requires the operator to deploy the witness as a different UID with directory and socket access controls; the local tests do not establish that deployment.

The witness does not authenticate event hashes against an independently recomputed ledger, has no authenticated recovery broker, and is not protected against privileged host compromise or rollback of its own storage. `SecureLogisticsService` and `LogisticsLedger` remain importable, hence OS-enforced legacy fencing is not delivered.
