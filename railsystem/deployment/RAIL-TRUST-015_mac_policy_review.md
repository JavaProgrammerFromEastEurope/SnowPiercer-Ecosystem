# Operator MAC/LSM review checklist — not an installed policy

This is **NOT** an AppArmor/SELinux policy and must never be used as a substitute for one.

1. Independently provision a service UID whose unconfined processes cannot open the write-state database, admission lock or checkpoint/phase files. Separate a confined privileged write-broker subject from a generic legacy Python subject *even when the numeric UID is identical*.
2. Deny execution/subject transitions that would permit arbitrary same-UID Python, shell or plugin processes to impersonate the confined broker. Verify policy loaded and enforced by the kernel, including fork/exec, deleted sockets, symlinks, hardlinks, mmap, Unix domain sockets and fd passing.
3. Give the witness and consumed-permit service independent administrators/UIDs, an independently protected non-rollbackable storage domain and a pinned trust enrollment. Ordinary local SQLite is insufficient for whole-host rollback.
4. Require independent service-manager restart ownership, bounded recovery permits and operator reconciliation after SIGKILL; never automatically unlink stale sockets.
5. Prove both the permitted positive path and all denied negative paths under unconfined/same-UID and cross-UID processes. Preserve audit records and attest policy identity independently before changing BLOCKED.

Until all are independently verified, the shipped `require_production_isolation()` must deny every production launch. Do not introduce an env-var override or an unreviewed config toggle.
