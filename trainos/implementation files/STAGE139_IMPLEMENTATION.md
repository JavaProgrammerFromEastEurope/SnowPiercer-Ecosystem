# Stage 139 — Lease renewal versus failure completion

Added a cross-process race test for `renew_lease` competing with `finish_failure` on the same fenced recovery attempt. Both workers use independent SQLite connections and synchronize at a multiprocessing barrier.

The test accepts either valid serialization order: renewal may commit before failure, or failure may win and renewal must be rejected. In all cases, failure completion is durable, the journal ends in `FAILED`, ownership and lease fields are cleared, the fencing token is unchanged, and a later renewal cannot resurrect the terminal attempt. The test is scoped to local SQLite transactional behavior and does not establish distributed or train-safety guarantees.

No production implementation changes were needed; the existing `BEGIN IMMEDIATE` transactions and owner/fencing checks enforce the tested invariant.
