import sqlite3

import pytest

from kernel.command.events import (
    DiagnosticInvestigationStore,
    InvestigationStoreIntegrityError,
)


def _create_two_revisions(path):
    with DiagnosticInvestigationStore(path) as store:
        store.save("case", "case-1", {"revision": 1})
        store.save("case", "case-1", {"revision": 2}, expected_revision=1)


def test_invalid_created_at_is_reported_and_record_cannot_be_loaded(tmp_path):
    path = tmp_path / "metadata.db"
    _create_two_revisions(path)
    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE investigation_record_versions SET created_at_iso=? WHERE record_type=? AND record_id=? AND revision=?",
        ("2026-10-20T10:00:00", "case", "case-1", 1),
    )
    connection.commit()
    connection.close()

    with DiagnosticInvestigationStore(path) as store:
        issues = store.verify_integrity()
        assert any(issue.code == "created_at_invalid" and issue.revision == 1 for issue in issues)
        with pytest.raises(InvestigationStoreIntegrityError, match="created_at timestamp invalid"):
            store.load("case", "case-1")


def test_reversed_revision_timestamp_is_reported_and_history_rejected(tmp_path):
    path = tmp_path / "metadata.db"
    _create_two_revisions(path)
    connection = sqlite3.connect(path)
    first = connection.execute(
        "SELECT created_at_iso FROM investigation_record_versions WHERE record_type=? AND record_id=? AND revision=1",
        ("case", "case-1"),
    ).fetchone()[0]
    connection.execute(
        "UPDATE investigation_record_versions SET created_at_iso=? WHERE record_type=? AND record_id=? AND revision=2",
        ("2000-01-01T00:00:00+00:00", "case", "case-1"),
    )
    # Ensure the first timestamp is later than the deliberately old second revision.
    connection.execute(
        "UPDATE investigation_record_versions SET created_at_iso=? WHERE record_type=? AND record_id=? AND revision=1",
        ("2020-01-01T00:00:00+00:00", "case", "case-1"),
    )
    connection.commit()
    connection.close()

    with DiagnosticInvestigationStore(path) as store:
        issues = store.verify_integrity()
        assert any(issue.code == "created_at_time_reversed" and issue.revision == 2 for issue in issues)
        with pytest.raises(InvestigationStoreIntegrityError, match="created_at timestamp reversed"):
            store.history("case", "case-1")


def test_metadata_integrity_scan_is_read_only(tmp_path):
    path = tmp_path / "metadata.db"
    _create_two_revisions(path)
    connection = sqlite3.connect(path)
    before = connection.execute(
        "SELECT revision, payload_json, checksum, previous_checksum, created_at_iso "
        "FROM investigation_record_versions ORDER BY revision"
    ).fetchall()
    connection.close()

    with DiagnosticInvestigationStore(path) as store:
        assert store.verify_integrity() == ()

    connection = sqlite3.connect(path)
    after = connection.execute(
        "SELECT revision, payload_json, checksum, previous_checksum, created_at_iso "
        "FROM investigation_record_versions ORDER BY revision"
    ).fetchall()
    connection.close()
    assert after == before
