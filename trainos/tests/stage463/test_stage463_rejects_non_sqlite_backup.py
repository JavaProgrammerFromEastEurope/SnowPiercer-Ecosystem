from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_non_sqlite_file_is_rejected(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite database")
    findings = CommandIdempotencyStore.validate_backup(path)
    assert findings
    assert any("cannot validate SQLite database" in item for item in findings)
