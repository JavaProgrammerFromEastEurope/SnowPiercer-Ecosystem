# Adapter compatibility test plan v1

- [x] Exact decimal-to-minor-unit conversion for an explicitly configured exponent.
- [x] Legacy source/destination balance semantics preserved.
- [x] Duplicate transaction ID retry is idempotent through ledger append.
- [x] Unknown currency mapping rejected.
- [x] Missing/equal accounts rejected rather than inferred.
- [x] Non-transfer transaction types rejected pending explicit semantic mappings.
- [x] Excess precision rejected without rounding.
- [ ] Contract review by TrainOS owner.
- [ ] Complete suite in CI and compatibility run against every supported legacy transaction type.
- [ ] Independent security/accounting review before any production payment use.
