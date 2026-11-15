# LIFE-CORE-012 — Service Isolation & Crash Recovery Enforcement

Start in a dedicated private directory owned by the service UID, mode 0700:

```bash
PYTHONPATH=src python -m lifesupport.service_cli --registry data/registry.json --db /private/life.db --socket /private/service.sock
```

The service exposes read-only `health` and `snapshot`. To test:

```bash
PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -v
```

After SIGKILL, verify that the service is stopped and the socket path is not replaced before deleting the stale socket inode. Restart the service to reopen and replay SQLite. Do not deploy this prototype for production life-support control.
