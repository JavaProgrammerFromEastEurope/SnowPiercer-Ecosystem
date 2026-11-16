# ISLAND-GEO-017 — Architecture and safety

Root-owned sticky 01777 IPC directory permits nonroot witness and service to bind sockets, while Linux sticky-bit semantics prohibit other nonowner UIDs from unlinking endpoints. Both socket files use mode 0660; actual access depends on supplementary groups. Peer UID is verified via SO_PEERCRED. The service and witness databases remain in distinct UID-owned 0700 directories.

The client issues a state-bound recovery permit directly to the authority; the service consumes the permit before reconciliation. The client subsequently submits an admission via the service IPC. Local accepted and phase tables reconcile with witness CAS.

**Trust boundaries:** a privileged root process can replace all state. A service process may import the legacy library, so OS-enforced legacy production fencing is **not** proven. Witness rollback to genesis is detected only while newer local history survives. The SQLite witness is not an independent monotonic hardware anchor. The sticky IPC directory is not equivalent to protected bind mounts or socket activation.

**Safety decision:** software test candidate only. Production security and physical construction/operations remain BLOCKED/NO-GO. No independent engineering review or site investigation exists.
