"""Collect deferred SQLite finalizers at test boundaries to attribute resource leaks."""
import gc
import pytest

@pytest.fixture(autouse=True)
def collect_resource_finalizers():
    gc.collect()
    yield
    gc.collect()
