# LIFE-CORE-021 — Read-only telemetry admission for ecosystem integration

Date: 2026-11-15. Base: LIFE-CORE-020. Stage software version: 0.21.0.

`lifesupport.core.telemetry.TelemetryAdmission` adds the typed receive boundary
missing from the original metadata-only envelope validator. The caller supplies
a validated registry and trusted `MetricPolicy` objects. Sender-supplied policy
fields, unknown metrics, sources or units are rejected. No clinical thresholds,
actuation or external equipment connection are introduced.

The API admits only `LifeTelemetry` with a finite numeric value, `quality=GOOD`,
an RFC3339 UTC observation, and a strictly increasing source/metric sequence.
Freshness and future clock tolerance come from local configuration. The supplied
admission clock must be aware UTC and must not move backwards after a successful
admission. The return value is immutable and detached from the caller's message.

Each admitted identity remains in a bounded session replay set; exhaustion denies
new messages instead of evicting replay history. Rejected messages never update
replay, stream or clock state. Existing metadata validation and the disabled
`LifeCommand` path remain unchanged.

## Acceptance and evidence

See `requirements/TELEMETRY_REQUIREMENTS.md`,
`contracts/telemetry-admission.schema.json`, `tests/test_telemetry.py`, and
`evidence/LIFE-CORE-021_TEST_RESULTS.txt`.

The baseline is 265 unittest cases (251 pass, 14 privileged cases skipped).
The final regression is 294 unittest cases (280 pass, the same 14 skipped),
including 29 new telemetry checks. All runs escalate `ResourceWarning`.

The initial baseline had one failure because this container's restrictive umask
created the old `test_sidecar_mode` fixture as safe mode 0600. Repeating with
explicit umask 022 restores the old test's intended unsafe 0644 fixture. No old
test or storage protection was weakened. Both logs are preserved.

## Reproduce

```sh
umask 022
PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q
python integration_probe.py --correlation-id YOUR-TRACE-ID
```

The probe exercises a fresh sample, a rejected replay and a rejected stale
sample on the real API. It reports `operationalReady=false`.

## Limits

This is a single-threaded, in-memory admission session. Process restart loses
replay state; network authentication, durable replay storage and cross-process
concurrency are not claimed. A trusted, reliable UTC clock and correct metric
policy must be provided externally. GOOD quality is a sender assertion, not
proof of sensor calibration or physical safety. Root-only cross-UID tests were
not run under this unprivileged account. Medical/physical operation remains
NO-GO; no ecosystem completion percentage is derived from these tests.

Older package metadata is historically inconsistent (pyproject: 0.12.0,
`lifesupport.__version__`: 0.2.0). This stage explicitly consolidates both at
0.21.0; older manifests and historical evidence are retained unchanged.
