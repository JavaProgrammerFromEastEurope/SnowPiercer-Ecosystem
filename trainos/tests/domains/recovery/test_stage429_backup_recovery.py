import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_missing_backup_is_reported_without_creation(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    findings = CommandIdempotencyStore.validate_backup(missing)
    assert findings == ("backup: file does not exist",)
    assert not missing.exists()
