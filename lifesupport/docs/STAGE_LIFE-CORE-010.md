# LIFE-CORE-010 — Operator Notes

Python >=3.11; no external runtime dependencies. Do not store secrets in source control.

Run full regression from `lifesupport/`:

```bash
PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -v
```

Rotation API (only for offline test journals):

1. Create a `RotatingLifecycle` with the current key; acquire a valid fencing lease.
2. `prepare_rotation(token, new_key)`.
3. `finalize_rotation(token, new_key)`.
4. Close the instance; reopen with the new key and verify the anchor.

If interrupted, **do not remove the pending file automatically**. Call `inspect_interrupted_rotation(anchor_path, old_key, new_key)` for read-only diagnosis. Preserve both files, the SQLite database, and both keys. Manual reconciliation requires separate review; no recovery command is supplied.

Legacy `TrustedLifecycle` does not enforce rotation pending records. This prototype is not a mandatory enforcement boundary.
