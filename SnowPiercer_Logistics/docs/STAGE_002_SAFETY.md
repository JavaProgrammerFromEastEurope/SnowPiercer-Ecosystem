# Safety Analysis and Limitations
| Threat | Mitigation | Residual risk |
|---|---|---|
| Spoofed IPC principal | Kernel peer UID; client role ignored | Same-UID processes indistinguishable |
| Duplicate command | Transactional command key | Caller may use different keys |
| Concurrent startup | flock + active socket probe | Startup lock not held throughout lifetime; socket unlink/replacement by owner possible |
| Kill after SQLite commit, before checkpoint | Fail-closed mismatch at restart | Availability loss; no offline reconciliation |
| Replay permit | Atomic UPDATE used=0 -> used=1 | Token disclosure before consumption; permits not bound to request payload |
| Rollback SQLite | Compare external checkpoint | Owner/privileged adversary can roll back both |
| Symlink substitution | lstat and O_NOFOLLOW on lock | TOCTOU and same-UID file substitution not comprehensively eliminated |
| Legacy bypass | Documentation restriction only | Production fencing not enforced by OS |
| IPC DoS | Timeouts and max message length | Single-threaded handler can stall up to timeout per connection |
| Physical actuation | None | No real robot/drone/rail safety evidence |

No claim of fully crash-consistent reconciliation, complete SIGKILL boundary coverage, cross-UID isolation, cryptographic anti-rollback, or production suitability is made. NO-GO.
