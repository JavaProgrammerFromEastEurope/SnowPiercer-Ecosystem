"""Validate envelope metadata; does not execute commands."""
from datetime import datetime, timezone
from typing import Any
from .registry import RegistryError, _nonempty

KINDS = frozenset({"LifeTelemetry", "LifeCommand", "LifeCommandResult", "LifeAlarm", "LifeResourceStatus", "LifeHealthStatus", "LifeSafetyState"})

def validate_envelope(message: dict[str, Any], component_ids: set[str]) -> dict:
    if not isinstance(message, dict):
        raise RegistryError("message must be object")
    if message.get("schema_version") != "1.0":
        raise RegistryError("unsupported message schema_version")
    if message.get("kind") not in KINDS:
        raise RegistryError("unknown message kind")
    if message.get("source_component_id") not in component_ids:
        raise RegistryError("unknown source component")
    _nonempty(message.get("message_id"), "message_id")
    stamp = _nonempty(message.get("timestamp_utc"), "timestamp_utc")
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RegistryError("invalid timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise RegistryError("timestamp must be UTC")
    if not isinstance(message.get("payload"), dict):
        raise RegistryError("payload must be object")
    if message["kind"] == "LifeCommand":
        raise RegistryError("LifeCommand is disabled in LIFE-CORE-002: no actuation authorization")
    return message
