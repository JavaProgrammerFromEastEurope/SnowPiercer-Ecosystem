# Architecture

ConsistencyGatedLogisticsService subclasses AttestedLogisticsService. Before recover/verify/get_cargo it validates owned files, absent phase journal and equality of witness-backed anchor and SQLite checkpoint. It does not reconcile or modify state. The existing write path remains unchanged and is NOT production-certified. The SIGKILL probe uses an isolated subprocess and a fsynced marker; it is not a transactional crash test.
