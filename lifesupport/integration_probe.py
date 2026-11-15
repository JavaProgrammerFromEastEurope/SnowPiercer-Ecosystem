"""Exercise LIFE-CORE-021 for a correlated, read-only ecosystem handshake."""
from datetime import datetime, timezone
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from lifesupport.core.registry import Registry
from lifesupport.core.telemetry import MetricPolicy, TelemetryAdmission, TelemetryError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()
    if not args.correlation_id.strip():
        parser.error("correlation-id must not be empty")
    source = "LIFE-SENSORS-001"
    gate = TelemetryAdmission(Registry.load(ROOT / "data/registry.json"),
                             {"temperature": MetricPolicy("Cel", frozenset({source}), 10)})
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    trace_key = sha256(args.correlation_id.encode("utf-8")).hexdigest()
    message = {"schema_version":"1.0", "kind":"LifeTelemetry", "source_component_id":source,
               "message_id":trace_key + ":life-sample",
               "timestamp_utc":"2026-11-14T23:59:59Z",
               "payload":{"metric":"temperature", "value":21.5, "unit":"Cel",
                          "quality":"GOOD", "sequence":1}}
    sample = gate.admit(message, now=now)
    checks = [{"name":"fresh_registered_sample_admitted", "passed":sample.value == 21.5 and sample.age_seconds == 1}]
    try:
        gate.admit(message, now=now)
    except TelemetryError:
        checks.append({"name":"replayed_identity_rejected", "passed":True})
    else:
        checks.append({"name":"replayed_identity_rejected", "passed":False})
    stale = {**message, "message_id":trace_key + ":stale", "timestamp_utc":"2026-11-14T23:59:00Z"}
    try:
        gate.admit(stale, now=now)
    except TelemetryError:
        checks.append({"name":"stale_sample_rejected", "passed":True})
    else:
        checks.append({"name":"stale_sample_rejected", "passed":False})
    passed = all(c["passed"] for c in checks)
    print(json.dumps({"schema":"snowpiercer.integration-probe.v1", "moduleId":"SP-LIFE",
                      "stageId":"LIFE-CORE-021", "correlationId":args.correlation_id,
                      "status":"ok" if passed else "failed", "checks":checks,
                      "operationalReady":False}, separators=(",", ":")))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
