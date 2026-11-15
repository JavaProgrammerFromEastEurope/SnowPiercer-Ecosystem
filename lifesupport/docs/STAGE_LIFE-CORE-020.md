# LIFE-CORE-020 — deployment and testing

The new `production_consolidation.install_profile(db, anchor=absolute_path, key_file=absolute_path)` is an explicit **offline** operation. The service UID must own the database directory with mode 0700. The profile is installed as 0600 and is not overwritten. `production_supervisor(registry, db, socket, allowed_uids={...})` builds a mandatory-ledger supervisor using the configured anchor and key file. Provision the protected SQLite database and external HMAC anchor independently, as specified in LIFE-CORE-019, before starting the service. Run the supervisor under the dedicated service UID; never as root.

Legacy `production_write_cli` and `reconciled_write_cli` reject a production-profiled database. This is not a universal block on importing and calling legacy Python APIs. The production profile is not an independent trust anchor. There is no proof of power-failure atomicity, physical exactly-once actuation, or security against service-UID/root compromise.

Test: `PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q`.
