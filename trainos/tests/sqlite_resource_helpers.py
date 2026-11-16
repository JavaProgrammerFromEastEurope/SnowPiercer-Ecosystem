"""Test-only SQLite transaction context that also closes the connection."""
import sqlite3
from contextlib import contextmanager

@contextmanager
def managed_sqlite_connection(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
