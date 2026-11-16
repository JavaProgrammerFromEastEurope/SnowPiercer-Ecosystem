import sqlite3
import pytest
from kernel.command.events import DiagnosticInvestigationStore, InvestigationRevisionConflict, InvestigationStoreIntegrityError


def test_create_update_and_history_form_a_checksum_chain(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "db" / "investigations.sqlite3") as store:
        first = store.save("hypothesis", "h-1", {"status": "under_review", "evidence": ["e1"]})
        second = store.save("hypothesis", "h-1", {"status": "reviewed"}, expected_revision=1)
        history = store.history("hypothesis", "h-1")
        assert (first.revision, second.revision) == (1, 2)
        assert [item.revision for item in history] == [1, 2]
        assert history[1].previous_checksum == first.checksum
        assert store.verify_integrity() == ()


def test_data_survives_close_and_reopen(tmp_path):
    path = tmp_path / "investigations.sqlite3"
    with DiagnosticInvestigationStore(path) as store:
        expected = store.save("task_tracker", "snapshot-1", {"tasks": [{"id": "t1", "state": "pending"}]})
    with DiagnosticInvestigationStore(path) as reopened:
        actual = reopened.load("task_tracker", "snapshot-1")
        assert actual.payload == expected.payload and actual.checksum == expected.checksum


def test_optimistic_concurrency_rejects_stale_revision(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        store.save("hypothesis", "h-1", {"v": 1})
        with pytest.raises(InvestigationRevisionConflict):
            store.save("hypothesis", "h-1", {"v": 2})
        with pytest.raises(InvestigationRevisionConflict):
            store.save("hypothesis", "h-1", {"v": 3}, expected_revision=0)
        assert store.load("hypothesis", "h-1").payload == {"v": 1}


def test_record_ids_are_isolated_and_unknown_records_return_none(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        assert store.load("hypothesis", "missing") is None
        store.save("hypothesis", "h-1", {"v": 1})
        store.save("hypothesis", "h-2", {"v": 2})
        assert store.load("hypothesis", "h-1").payload == {"v": 1}
        assert store.load("hypothesis", "h-2").payload == {"v": 2}


def test_invalid_payload_and_revision_are_rejected_without_mutation(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        with pytest.raises(ValueError): store.save("hypothesis", "h-1", {"bad": float("nan")})
        with pytest.raises(TypeError): store.save("hypothesis", "h-1", ["not", "a", "dict"])
        with pytest.raises(ValueError): store.save("hypothesis", "h-1", {}, expected_revision=True)
        assert store.history("hypothesis", "h-1") == ()


def test_checksum_corruption_is_reported_and_never_silently_loaded(tmp_path):
    path = tmp_path / "store.db"
    with DiagnosticInvestigationStore(path) as store:
        store.save("hypothesis", "h-1", {"status": "under_review"})
    connection = sqlite3.connect(path)
    connection.execute("UPDATE investigation_record_versions SET payload_json=? WHERE record_type=? AND record_id=? AND revision=1",
                       ('{"status":"tampered"}', "hypothesis", "h-1"))
    connection.commit(); connection.close()
    with DiagnosticInvestigationStore(path) as store:
        assert store.verify_integrity()[0].code == "checksum_mismatch"
        with pytest.raises(InvestigationStoreIntegrityError, match="checksum mismatch"):
            store.load("hypothesis", "h-1")
        with pytest.raises(InvestigationStoreIntegrityError):
            store.save("hypothesis", "h-1", {"status": "new"}, expected_revision=1)


def test_missing_middle_revision_is_detected(tmp_path):
    path = tmp_path / "store.db"
    with DiagnosticInvestigationStore(path) as store:
        store.save("hypothesis", "h-1", {"v": 1})
        store.save("hypothesis", "h-1", {"v": 2}, expected_revision=1)
        store.save("hypothesis", "h-1", {"v": 3}, expected_revision=2)
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM investigation_record_versions WHERE record_type='hypothesis' AND record_id='h-1' AND revision=2")
    connection.commit(); connection.close()
    with DiagnosticInvestigationStore(path) as store:
        assert store.verify_integrity()[0].code == "revision_gap"
        with pytest.raises(InvestigationStoreIntegrityError, match="revision gap"):
            store.history("hypothesis", "h-1")


def test_close_is_idempotent_and_closed_store_rejects_operations(tmp_path):
    store = DiagnosticInvestigationStore(tmp_path / "store.db")
    store.close(); store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.load("hypothesis", "h-1")


def test_unicode_and_nested_json_round_trip(tmp_path):
    payload = {"summary": "неисправность", "details": {"events": ["событие-1", 2], "active": True}}
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        stored = store.save("report", "r-1", payload)
        assert store.load("report", "r-1").payload == payload
        assert stored.payload == payload


def test_separate_store_instances_use_revision_guard_to_prevent_lost_updates(tmp_path):
    path = tmp_path / "shared.sqlite3"
    first = DiagnosticInvestigationStore(path)
    second = DiagnosticInvestigationStore(path)
    try:
        first.save("hypothesis", "h-1", {"v": 1})
        with pytest.raises(InvestigationRevisionConflict):
            second.save("hypothesis", "h-1", {"v": 2}, expected_revision=0)
        assert second.load("hypothesis", "h-1").payload == {"v": 1}
    finally:
        first.close()
        second.close()
