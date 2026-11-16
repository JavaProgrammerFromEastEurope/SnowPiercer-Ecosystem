from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3

from kernel.command.events import DiagnosticInvestigationStore


def _seed(path):
    with DiagnosticInvestigationStore(path) as store:
        store.save("case", "case-1", {"n": 1})
        store.save("case", "case-1", {"n": 2}, expected_revision=1)


def test_invalid_timestamp_is_reported_once(tmp_path):
    path = tmp_path / "audit.db"
    _seed(path)
    with managed_sqlite_connection(path) as connection:
        connection.execute(
            "UPDATE investigation_record_versions SET created_at_iso=? WHERE record_type=? AND record_id=? AND revision=?",
            ("2026-10-20T10:00:00", "case", "case-1", 1),
        )
    with DiagnosticInvestigationStore(path) as store:
        issues = store.verify_integrity()
    matches = [issue for issue in issues if issue.code == "created_at_invalid" and issue.revision == 1]
    assert len(matches) == 1


def test_independent_scan_keeps_distinct_timestamp_findings(tmp_path):
    path = tmp_path / "audit.db"
    _seed(path)
    with managed_sqlite_connection(path) as connection:
        connection.execute(
            "UPDATE investigation_record_versions SET created_at_iso=? WHERE record_type=? AND record_id=? AND revision=?",
            ("bad-timestamp", "case", "case-1", 1),
        )
        connection.execute(
            "UPDATE investigation_record_versions SET created_at_iso=? WHERE record_type=? AND record_id=? AND revision=?",
            ("also-bad", "case", "case-1", 2),
        )
    with DiagnosticInvestigationStore(path) as store:
        issues = store.verify_integrity()
    invalid_revisions = [issue.revision for issue in issues if issue.code == "created_at_invalid"]
    assert invalid_revisions == [1, 2]
