"""LIFE-CORE-021: bounded, read-only admission of offline telemetry samples.

Policies are caller-provisioned engineering configuration, never sender input.
This module has no actuator, clinical threshold, network or persistence API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from types import MappingProxyType
from typing import Mapping

from .contracts import validate_envelope
from .registry import Registry, RegistryError


class TelemetryError(RegistryError):
    """A sample or admission policy cannot be trusted for this session."""


_METRIC = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z")
_ENVELOPE = frozenset(("schema_version", "kind", "source_component_id",
                       "message_id", "timestamp_utc", "payload"))
_PAYLOAD = frozenset(("metric", "value", "unit", "quality", "sequence"))


def _finite(value: object, label: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise TelemetryError(f"{label} must be a finite number, not a boolean")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise TelemetryError(f"{label} must be finite") from exc
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        raise TelemetryError(f"invalid {label}")
    return number


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise TelemetryError(f"{label} must be an aware UTC datetime")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise TelemetryError(f"{label} must be UTC")
    return value


@dataclass(frozen=True)
class MetricPolicy:
    """Allowed unit, source identities and freshness, from trusted configuration.

    Numeric limits are about message age only, not human physiological safety.
    """
    unit: str
    sources: frozenset[str]
    max_age_seconds: float
    future_skew_seconds: float = 0

    def __post_init__(self) -> None:
        if not isinstance(self.unit, str) or not self.unit.strip() or len(self.unit) > 32:
            raise TelemetryError("unit must be a nonempty bounded string")
        if not isinstance(self.sources, frozenset) or not self.sources:
            raise TelemetryError("sources must be a nonempty frozenset")
        if any(not isinstance(s, str) or not s.strip() for s in self.sources):
            raise TelemetryError("invalid source identity")
        _finite(self.max_age_seconds, "max_age_seconds", positive=True)
        _finite(self.future_skew_seconds, "future_skew_seconds")


@dataclass(frozen=True)
class TelemetrySample:
    message_id: str
    source_component_id: str
    metric: str
    value: float
    unit: str
    quality: str
    sequence: int
    observed_at: datetime
    admitted_at: datetime
    age_seconds: float


class TelemetryAdmission:
    """Single-threaded, in-memory, read-only telemetry session.

    Replays and non-increasing per-source/metric sequences are rejected. The
    replay set fails closed at capacity rather than evicting old identities.
    Restart loses this session state; durable/authenticated admission is outside
    this contract. It must not be used as an actuation authorizer.
    """

    def __init__(self, registry: Registry, policies: Mapping[str, MetricPolicy],
                 *, max_records: int = 10000) -> None:
        if not isinstance(registry, Registry):
            raise TelemetryError("validated registry required")
        if not isinstance(policies, Mapping) or not policies:
            raise TelemetryError("metric policies required")
        if type(max_records) is not int or not 1 <= max_records <= 1000000:
            raise TelemetryError("max_records must be an integer in 1..1000000")
        copied = dict(policies)
        ids = frozenset(registry.components)
        for metric, policy in copied.items():
            if not isinstance(metric, str) or not _METRIC.fullmatch(metric):
                raise TelemetryError("invalid metric identifier")
            if not isinstance(policy, MetricPolicy) or not policy.sources <= ids:
                raise TelemetryError("policy has an unknown source or invalid type")
        self._ids = ids
        self._policies = MappingProxyType(copied)
        self._capacity = max_records
        self._seen: set[str] = set()
        self._streams: dict[tuple[str, str], tuple[int, datetime]] = {}
        self._last_now: datetime | None = None

    @property
    def admitted_count(self) -> int:
        return len(self._seen)

    def admit(self, message: dict, *, now: datetime) -> TelemetrySample:
        """Validate completely before changing replay, sequence or clock state."""
        now = _utc(now, "now")
        if self._last_now is not None and now < self._last_now:
            raise TelemetryError("admission clock moved backwards")
        if not isinstance(message, dict) or set(message) != _ENVELOPE:
            raise TelemetryError("unexpected telemetry envelope fields")
        # Validate hashability/type before the legacy metadata validator performs
        # allowlist membership, so malformed external data fails with one error.
        for name in ("schema_version", "kind", "source_component_id", "message_id", "timestamp_utc"):
            if not isinstance(message[name], str):
                raise TelemetryError(f"{name} must be a string")
        if not _STAMP.fullmatch(message["timestamp_utc"]):
            raise TelemetryError("observation timestamp must be an RFC3339 UTC instant")
        try:
            validate_envelope(message, set(self._ids))
        except RegistryError as exc:
            raise TelemetryError(str(exc)) from exc
        if message["kind"] != "LifeTelemetry":
            raise TelemetryError("only read-only LifeTelemetry is admitted")
        identity = message["message_id"]
        if len(identity) > 200:
            raise TelemetryError("message_id exceeds 200 characters")
        if identity in self._seen:
            raise TelemetryError("replayed message_id")
        if len(self._seen) >= self._capacity:
            raise TelemetryError("admission capacity exhausted; start no implicit reset")
        payload = message["payload"]
        if set(payload) != _PAYLOAD:
            raise TelemetryError("unexpected telemetry payload fields")
        metric = payload["metric"]
        if not isinstance(metric, str) or metric not in self._policies:
            raise TelemetryError("unregistered metric")
        policy = self._policies[metric]
        source = message["source_component_id"]
        if source not in policy.sources:
            raise TelemetryError("source is not allowed for this metric")
        if payload["unit"] != policy.unit:
            raise TelemetryError("measurement unit does not match trusted policy")
        if payload["quality"] != "GOOD":
            raise TelemetryError("measurement quality is not GOOD")
        value = payload["value"]
        if type(value) not in (int, float):
            raise TelemetryError("measurement value must be a finite number")
        try:
            numeric = float(value)
        except (ValueError, OverflowError) as exc:
            raise TelemetryError("measurement value must be finite") from exc
        if not math.isfinite(numeric):
            raise TelemetryError("measurement value must be finite")
        sequence = payload["sequence"]
        if type(sequence) is not int or not 1 <= sequence <= (2**63 - 1):
            raise TelemetryError("sequence must be an integer in 1..2^63-1")
        observed = datetime.fromisoformat(message["timestamp_utc"].replace("Z", "+00:00"))
        age = (now - observed).total_seconds()
        if age > policy.max_age_seconds:
            raise TelemetryError("stale telemetry")
        if age < -policy.future_skew_seconds:
            raise TelemetryError("telemetry exceeds future clock tolerance")
        stream = (source, metric)
        previous = self._streams.get(stream)
        if previous and (sequence <= previous[0] or observed < previous[1]):
            raise TelemetryError("telemetry stream sequence or observation time moved backwards")
        sample = TelemetrySample(identity, source, metric, numeric, policy.unit,
                                 "GOOD", sequence, observed, now, age)
        self._seen.add(identity)
        self._streams[stream] = (sequence, observed)
        self._last_now = now
        return sample
