# LIFE-CORE-018 Usage
```python
from lifesupport.core.request_ledger import RequestLedgerAnchor, LedgerAdmission
anchor = RequestLedgerAnchor('/trusted/receipts.anchor', key_from_separate_secure_source)
anchor.initialize(lifecycle.db)  # once, offline, after trusted provisioning
admission = LedgerAdmission(lifecycle, anchor)
admission.verify()  # mandatory before opt-in recovery or write
result = admission.apply(request, peer_uid)
```
A post-COMMIT crash requires separate evidence verification and explicit `anchor.reconcile(db, approved_snapshot=...)`; never automatically accept database state. Existing Stage 017 service does not yet use this adapter. Production requires mandatory service integration, independent key management, trusted checkpoint protocol, and OS isolation.
