# LIFE-CORE-014

New opt-in module: `lifesupport.core.cross_uid`. Provision a dedicated unprivileged service UID and a distinct client UID. Place SQLite in a service-owned `0700` directory, create a separate service-owned `0711` socket directory, and explicitly configure `allowed_uids={client_uid}`. Invoke `AuthorizedLifecycleService(...).serve()` as the service UID. `cross_uid_request` provides a simple read-only client; it does not authenticate the server, so use only within a trusted local deployment. `transition` and other write operations are unavailable.

Run full regression: `PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q`.

Known limitation: no supervised production service, no authenticated server endpoint, no remote write capability, no proof against service-UID/root bypass, no power-loss testing.
