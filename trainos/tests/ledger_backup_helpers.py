"""Shared fixtures for backup validation stages 488–497."""
from pathlib import Path
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def make_multi_audit_backup(tmp_path: Path, count: int = 2) -> Path:
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    for index in range(count):
        key = f"key-{index + 1}"
        store.claim(key, "charge", {"cents": 250 + index})
        store.mark_unknown(key, reason="provider response missing")
        store.reconcile_completed(
            key,
            {"provider_ref": f"ref-{index + 1}"},
            evidence=f"provider lookup confirmed completion {index + 1}",
        )
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    return backup


def make_two_generation_backup(tmp_path: Path) -> Path:
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("key-1", "charge", {"cents": 250}, execution_id="exec-1")
    assert store.reserve_dispatch("key-1")
    store.mark_unknown("key-1", reason="first provider response missing")
    store.reconcile_not_executed(
        "key-1", evidence="provider ledger confirms no first execution", execution_id="exec-1"
    )
    assert store.reserve_dispatch("key-1")
    store.mark_unknown("key-1", reason="second provider response missing")
    store.reconcile_not_executed(
        "key-1", evidence="provider ledger confirms no second execution", execution_id="exec-1"
    )
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    return backup
