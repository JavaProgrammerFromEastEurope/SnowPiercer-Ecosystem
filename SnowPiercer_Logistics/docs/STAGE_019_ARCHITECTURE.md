# LOG-CORE-019 Architecture

Opt-in TransactionAdmissionService extends EvidenceGatedLogisticsService, which extends the direct-client-attested service and witness-backed ledger. It validates Unix socket filesystem types and checks transaction consistency on every request. No production activation is exposed. The checks are path-based and retain TOCTOU exposure; do not treat them as a kernel-enforced capability or authentication proof. Existing production_admission functions remain closed. No auto-reconciliation of SQLite/witness divergence is performed.
