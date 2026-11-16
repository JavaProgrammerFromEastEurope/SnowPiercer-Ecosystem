# TrainOS Stage 79 — Signed portable integrity anchors

## Goal
Provide a portable integrity-anchor envelope that can be sent to independently administered remote or immutable storage and later authenticated before it is trusted.

## Changes
- Added `sign_event_integrity_anchor()` and `verify_signed_event_integrity_anchor()` in `kernel/command/events/signed_event_integrity_anchor.py`.
- Envelopes use a versioned schema, canonical JSON serialization, domain-separated HMAC-SHA256, timezone-aware timestamps, strict field validation, and constant-time signature comparison.
- Exposed the helpers from `kernel.command.events`.
- Added tests for round-trip validation, wrong keys, tampered sequence/hash, malformed JSON, unexpected fields, short keys, invalid hashes, and naive timestamps.

## Security boundaries
HMAC is a shared-secret MAC, not a public-key signature. The signing key must be generated securely and stored separately from the event database and exported envelopes; never hard-code it or commit it. If an attacker can obtain the key, they can forge envelopes. This stage does not implement remote delivery, key rotation, revocation, or WORM retention. Operators must transmit the serialized envelope to a separately administered destination and alert on delivery/verification failures. A valid signature authenticates the checkpoint's origin and content; the event store still must be compared against the verified checkpoint sequence/hash. This is not a safety-certified railway control component.
