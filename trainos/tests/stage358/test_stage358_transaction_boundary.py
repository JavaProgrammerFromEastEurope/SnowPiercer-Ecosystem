import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_identical_completion_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-358', 'charge', {'amount': 358}, execution_id='exec-358')
        first = store.complete('key-358', {'accepted': True, 'reference': 'r358'}, execution_id='exec-358')
        second = store.complete('key-358', {'reference': 'r358', 'accepted': True}, execution_id='exec-358')
        assert second == first
        assert store.get('key-358') == first
    finally:
        store.close()
