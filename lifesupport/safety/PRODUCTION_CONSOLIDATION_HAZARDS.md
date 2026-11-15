# Preliminary hazard analysis — LIFE-CORE-020

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Legacy CLI bypasses ledger | CLI preflight checks production profile | Direct library access bypasses check |
| Profile deletion/rollback | Owner-only DAC; offline provisioning | Same UID/root can remove profile |
| Malicious symlink | O_NOFOLLOW and regular-file checks | Directory replacement by privileged actor |
| Incorrect key or anchor | MandatoryLedgerService preflight | Key custody not proven |
| Socket replacement | Supervisor inode and peer checks from prior Stages | Privileged tampering remains possible |
| Crash during SQLite/anchor update | Stage 019 pending intent reconciliation | Power-loss durability unproven |
| Live service during provisioning | Offline-only requirement | No live migration lock |
| Repeated recovery crashes | Supervisor restart controls | Availability not guaranteed |

Status: NO-GO for physical life-support actuation.
