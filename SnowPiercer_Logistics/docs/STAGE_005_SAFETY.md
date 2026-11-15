# LOG-CORE-005 safety analysis

**Confirmed locally:** witness rejects stale CAS, decreasing event count, non-genesis initialization and disallowed peer UID; service rejects missing checkpoint after initialization and unavailable witness. Regression coverage is local and same UID.

**Open hazards:** no real cross-UID end-to-end deployment; same-UID test harness can modify witness state; witness file itself may be rolled back by privileged actors; crash between witness CAS and local checkpoint leaves service unavailable; no exhaustive SIGKILL injection at SQLite/IPC/CAS boundaries; no OS-enforced legacy production fencing; malicious substitution of lock files, phase journal, SQLite WAL and sockets is not exhaustively verified; Unix socket 0600 blocks different UID clients absent a privileged proxy or ACL configuration. No hardware actuation safety case. Production remains BLOCKED/NO-GO.
