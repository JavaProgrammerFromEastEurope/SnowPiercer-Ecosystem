import copy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from lifesupport.core.registry import Registry
from lifesupport.core.telemetry import MetricPolicy, TelemetryAdmission, TelemetryError


NOW = datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)
SOURCE = "LIFE-SENSORS-001"
ROOT = Path(__file__).resolve().parents[1]


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.registry = Registry.load(ROOT / "data/registry.json")
        self.policies = {"temperature": MetricPolicy("Cel", frozenset({SOURCE}), 10)}
        self.gate = TelemetryAdmission(self.registry, self.policies, max_records=3)
        self.message = {
            "schema_version": "1.0", "kind": "LifeTelemetry",
            "source_component_id": SOURCE, "message_id": "sample-1",
            "timestamp_utc": "2026-11-14T23:59:59Z",
            "payload": {"metric": "temperature", "value": 21.5,
                        "unit": "Cel", "quality": "GOOD", "sequence": 1},
        }

    def reject(self, message=None, now=NOW):
        with self.assertRaises(TelemetryError):
            self.gate.admit(self.message if message is None else message, now=now)

    def next_message(self, *, identity="sample-2", sequence=2,
                     timestamp="2026-11-15T00:00:00Z"):
        m = copy.deepcopy(self.message)
        m["message_id"] = identity
        m["payload"]["sequence"] = sequence
        m["timestamp_utc"] = timestamp
        return m

    def test_fresh_sample_is_immutable_and_detached_from_input(self):
        sample = self.gate.admit(self.message, now=NOW)
        self.assertEqual(sample.age_seconds, 1)
        self.assertEqual(sample.value, 21.5)
        self.message["payload"]["value"] = 999
        self.assertEqual(sample.value, 21.5)
        with self.assertRaises(FrozenInstanceError):
            sample.value = 1

    def test_negative_finite_measurement_is_not_a_safety_threshold(self):
        self.message["payload"]["value"] = -10
        self.assertEqual(self.gate.admit(self.message, now=NOW).value, -10)

    def test_exact_age_boundary_is_admitted(self):
        self.message["timestamp_utc"] = "2026-11-14T23:59:50Z"
        self.assertEqual(self.gate.admit(self.message, now=NOW).age_seconds, 10)

    def test_stale_sample_is_rejected_without_state_change(self):
        self.message["timestamp_utc"] = "2026-11-14T23:59:49.999999Z"
        self.reject()
        self.assertEqual(self.gate.admitted_count, 0)

    def test_sender_cannot_override_freshness_policy(self):
        self.message["payload"]["max_age_seconds"] = 100000
        self.reject()

    def test_future_sample_is_rejected_by_default(self):
        self.message["timestamp_utc"] = "2026-11-15T00:00:00.000001Z"
        self.reject()

    def test_trusted_future_tolerance_is_explicit_and_bounded(self):
        gate = TelemetryAdmission(self.registry, {"temperature": MetricPolicy("Cel", frozenset({SOURCE}), 10, 2)})
        self.message["timestamp_utc"] = "2026-11-15T00:00:02Z"
        self.assertEqual(gate.admit(self.message, now=NOW).age_seconds, -2)
        m = self.next_message(timestamp="2026-11-15T00:00:02.000001Z")
        with self.assertRaises(TelemetryError):
            gate.admit(m, now=NOW)

    def test_non_utc_or_naive_admission_clock_is_rejected(self):
        for now in (NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=3))), "2026-11-15"):
            with self.subTest(now=now):
                self.reject(now=now)

    def test_timestamp_requires_rfc3339_utc_and_valid_calendar(self):
        for stamp in ("2026-11-15", "20261115T000000Z", "2026-11-15T03:00:00+03:00",
                      "2026-02-30T00:00:00Z", "2026-11-15T00:00:00", "", "x"):
            with self.subTest(stamp=stamp):
                self.message["timestamp_utc"] = stamp
                self.reject()

    def test_non_string_metadata_fails_as_telemetry_error(self):
        for field in ("schema_version", "kind", "source_component_id", "message_id", "timestamp_utc"):
            m = copy.deepcopy(self.message)
            m[field] = []
            with self.subTest(field=field):
                self.reject(m)

    def test_admission_clock_rollback_rejects_new_identity(self):
        self.gate.admit(self.message, now=NOW)
        self.reject(self.next_message(timestamp="2026-11-14T23:59:59Z"), now=NOW-timedelta(microseconds=1))

    def test_rejected_sample_does_not_poison_clock_or_replay_state(self):
        bad = copy.deepcopy(self.message)
        bad["payload"]["quality"] = "INVALID"
        self.reject(bad, now=NOW+timedelta(seconds=1))
        self.assertEqual(self.gate.admit(self.message, now=NOW).message_id, "sample-1")

    def test_replayed_identity_is_rejected_even_with_higher_sequence(self):
        self.gate.admit(self.message, now=NOW)
        self.reject(self.next_message(identity="sample-1"))
        self.assertEqual(self.gate.admitted_count, 1)

    def test_replayed_sequence_with_new_identity_is_rejected(self):
        self.gate.admit(self.message, now=NOW)
        self.reject(self.next_message(sequence=1))

    def test_higher_sequence_cannot_roll_back_observation_time(self):
        self.gate.admit(self.message, now=NOW)
        self.reject(self.next_message(timestamp="2026-11-14T23:59:58Z"))

    def test_increasing_sequence_with_same_observation_time_is_supported(self):
        self.gate.admit(self.message, now=NOW)
        self.assertEqual(self.gate.admit(self.next_message(timestamp=self.message["timestamp_utc"]), now=NOW).sequence, 2)

    def test_capacity_fails_closed_without_forgetting_replay_ids(self):
        self.gate.admit(self.message, now=NOW)
        self.gate.admit(self.next_message(), now=NOW)
        self.gate.admit(self.next_message(identity="sample-3", sequence=3), now=NOW)
        self.reject(self.next_message(identity="sample-4", sequence=4))
        self.reject(self.message)
        self.assertEqual(self.gate.admitted_count, 3)

    def test_unknown_metric_and_unexpected_payload_fields_are_rejected(self):
        for mutation in ({"metric": "co2"}, {"actuate": True}):
            m = copy.deepcopy(self.message)
            m["payload"].update(mutation)
            self.reject(m)

    def test_unknown_and_unauthorized_sources_are_rejected(self):
        for source in ("OTHER", "LIFE-CORE-001"):
            m = copy.deepcopy(self.message)
            m["source_component_id"] = source
            self.reject(m)

    def test_wrong_unit_rejected_instead_of_implicit_conversion(self):
        self.message["payload"]["unit"] = "K"
        self.reject()

    def test_invalid_or_suspect_quality_is_not_a_current_good_value(self):
        for quality in ("SUSPECT", "INVALID", None, True, "good"):
            self.message["payload"]["quality"] = quality
            self.reject()

    def test_nonfinite_and_boolean_values_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, "21.5", 10**1000, None):
            with self.subTest(value=str(value)[:50]):
                self.message["payload"]["value"] = value
                self.reject()

    def test_invalid_sequences_are_rejected(self):
        for sequence in (0, -1, True, 1.0, "1", 2**63):
            self.message["payload"]["sequence"] = sequence
            self.reject()

    def test_commands_and_other_message_kinds_remain_disabled(self):
        for kind in ("LifeCommand", "LifeAlarm", "LifeCommandResult", "LifeHealthStatus"):
            self.message["kind"] = kind
            self.reject()

    def test_unexpected_envelope_fields_and_missing_fields_rejected(self):
        m = dict(self.message, authorization=True)
        self.reject(m)
        for key in self.message:
            m = copy.deepcopy(self.message)
            del m[key]
            self.reject(m)

    def test_policy_snapshot_does_not_follow_caller_mapping_mutations(self):
        self.policies["temperature"] = MetricPolicy("K", frozenset({SOURCE}), 1000)
        self.assertEqual(self.gate.admit(self.message, now=NOW).unit, "Cel")

    def test_policies_fail_closed_for_invalid_freshness_and_sources(self):
        for age in (0, -1, True, float("nan"), float("inf")):
            with self.assertRaises(TelemetryError):
                MetricPolicy("Cel", frozenset({SOURCE}), age)
        for skew in (-1, True, float("nan"), float("inf")):
            with self.assertRaises(TelemetryError):
                MetricPolicy("Cel", frozenset({SOURCE}), 10, skew)
        for sources in (set(), {SOURCE}, frozenset(), frozenset({""})):
            with self.assertRaises(TelemetryError):
                MetricPolicy("Cel", sources, 10)
        with self.assertRaises(TelemetryError):
            TelemetryAdmission(self.registry, {"temperature": MetricPolicy("Cel", frozenset({"OTHER"}), 10)})

    def test_invalid_capacity_and_metric_configuration_rejected(self):
        for capacity in (True, 0, -1, 1.0, 1000001):
            with self.assertRaises(TelemetryError):
                TelemetryAdmission(self.registry, self.policies, max_records=capacity)
        for policies in ({}, {"bad metric": self.policies["temperature"]}, {"temperature": None}):
            with self.assertRaises(TelemetryError):
                TelemetryAdmission(self.registry, policies)

    def test_sequences_are_separate_for_distinct_metrics(self):
        self.policies["pressure"] = MetricPolicy("Pa", frozenset({SOURCE}), 10)
        gate = TelemetryAdmission(self.registry, self.policies)
        gate.admit(self.message, now=NOW)
        m = self.next_message(sequence=1)
        m["payload"].update(metric="pressure", unit="Pa", value=101325)
        self.assertEqual(gate.admit(m, now=NOW).sequence, 1)


if __name__ == "__main__":
    unittest.main()
