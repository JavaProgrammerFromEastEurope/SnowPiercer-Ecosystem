# LIFE-CORE-005

## Run regression
```bash
cd lifesupport
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Offline usage
```python
import secrets
from lifesupport.core.persistence import PersistentLifecycle
from lifesupport.core.checkpoints import create_checkpoint, verify_checkpoint, create_backup, verify_backup, restore_backup
key = secrets.token_bytes(32)  # Store separately; retain securely for verification
with PersistentLifecycle(registry, 'journal.db') as store:
    create_checkpoint(store, 'anchor.json', key)
    verify_checkpoint(store, 'anchor.json', key)
    create_backup(store, 'backup.db', 'backup.manifest.json', key, 'anchor.json')
verify_backup(registry, 'backup.db', 'backup.manifest.json', key, 'anchor.json')
restore_backup(registry, 'backup.db', 'backup.manifest.json', 'recovered-new.db', key, 'anchor.json')
```

Never use example files or a demo key for production. This is an offline prototype, not a safety-rated controller.
