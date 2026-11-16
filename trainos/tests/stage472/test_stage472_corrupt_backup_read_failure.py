from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_corrupt_backup_returns_validation_finding(tmp_path):
    backup = tmp_path / "corrupt.db"
    backup.write_bytes(b"not a sqlite database")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert findings
    assert any("cannot validate SQLite database" in item or "sqlite:" in item.lower() for item in findings)
