# SnowPiercer Logistics v0.21.0 — LOG-CORE-021

Current stage adds `TimedLogisticsLedger`: a local TrainOS command envelope with
expiry, atomic expected event revision, and persistent exact-replay binding.
Trusted identity is supplied separately by the host; clients cannot declare
their own role in the envelope. See `docs/STAGE_021_*`,
`tests/test_stage021.py`, and `integration_probe.py`.

Production remains **BLOCKED / NO-GO**. This is a software-model adapter, not a
four-UID production transaction or a robotics/transport safety certification.

## Earlier cumulative foundation (v0.12.0)
Cumulative Python source and tests. Stage 012 adds privileged deployment planning and descriptor-based installation primitives, with a deliberately fail-closed production entrypoint. Strict local regression results in evidence/. Production: BLOCKED / NO-GO. No independently verified cross-UID end-to-end safety claim.


## LOG-CORE-013 (v0.13.0)
Real Linux UID/DAC/AF_UNIX acceptance probes in `stage013.py`. Production entrypoint remains closed. See docs/STAGE_013_* and evidence/stage013_*.

## Stage 015
Opt-in direct-client recovery permit attestation (not production certified); see docs/STAGE_015_*.md.

## LOG-CORE-017
Opt-in quarantined transaction classification and descriptor-checked phase reading. Production remains BLOCKED/NO-GO; see docs/STAGE_017_*.md.

## LOG-CORE-018 (v0.18.0)
Opt-in fail-closed transaction classification; no integrated four-UID transaction proof. Production BLOCKED / NO-GO. See docs/STAGE_018_*.md and evidence/stage018_*.log.
