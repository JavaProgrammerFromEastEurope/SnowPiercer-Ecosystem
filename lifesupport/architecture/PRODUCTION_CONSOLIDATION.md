# LIFE-CORE-020 — Production Interface Consolidation

The opt-in production profile is stored in the service-owned database directory as `.life-production-profile.json` (regular file 0600, directory 0700). `production_supervisor` only creates a mandatory-ledger supervisor when a valid profile is present. The previous write CLIs refuse startup when a profile is installed; Python library APIs are retained.

The mandatory-ledger service from Stage 019 performs HMAC authenticated recovery admission before read/write IPC. The supervisor from Stage 015 monitors the child and reconciles stale socket inodes. The Stage 020 profile is a deployment policy, not a kernel-enforced ban on direct SQLite writes; same-UID code and root can bypass it. Provisioning must be offline; no interprocess atomicity with running legacy processes is claimed. Profile removal/rollback by the owner remains possible. Cross-UID isolation still relies on DAC and SO_PEERCRED.
