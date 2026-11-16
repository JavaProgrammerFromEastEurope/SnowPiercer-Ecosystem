"""Constructor failure must not leak SQLite connections."""
from contextlib import closing
import gc
import sqlite3
import warnings

import pytest
from kernel.command.events import CommandEventStore


def test_constructor_closes_connection_after_schema_failure(tmp_path):
    path = tmp_path / 'invalid.sqlite'
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute('CREATE VIEW command_events AS SELECT 1 AS sequence')
    # The view is incompatible with the store's required append-only table.
    with warnings.catch_warnings():
        warnings.simplefilter('error', ResourceWarning)
        with pytest.raises(sqlite3.DatabaseError):
            CommandEventStore(path)
        gc.collect()
