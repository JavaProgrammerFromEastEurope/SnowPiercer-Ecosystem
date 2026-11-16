# SnowPiercer Security — v0.1.0 (SP-SAFE)

**Separate baseline module** developed from the supplied `TrainOS_Workspace(5).zip`,
which listed Security as an independent direction but contained no Security source.
TrainOS and the six existing subsystem sources are retained unchanged.

**STATUS: BLOCKED / NO-GO.** This is a **simulation-only security reference**;
no use for train, energy, life-support, actuator, or other physical control is authorized.

## Scope and value

- `SP-IC-004` reference admission request and decision: strict schema, explicit allowlist,
  deny-by-default, version binding, simulated principal matching, mandatory audit link.
- SQLite `BEGIN IMMEDIATE` replay isolation, HMAC-SHA256 audit hash chain and detectable
  in-process tail truncation. A failure of storage or integrity blocks further admission.
- No implicit privileges: issue/recover/override/actuate/configure/admin all DENY.
- An unconditionally blocked `require_production_admission()` interface. No environment
  variable, configuration toggle, or `ALLOW` simulation result lifts the NO-GO.
- Same shared probe envelope used by existing ecosystem modules.

## Reproduce (Python >=3.11, stdlib only)

```sh
cd subsystems/security
PYTHONPATH=. python -W error::ResourceWarning -W error::DeprecationWarning -m unittest discover -s tests -v
PYTHONPATH=. python -W error::ResourceWarning -W error::DeprecationWarning integration_probe.py --correlation-id SEC-local-001
```

The repository's `tools/run_ecosystem_probes.py` supports the original six-module run
and the optional seventh Security probe. These are **independent** tests, not
cross-module signed commands, cross-UID protection or physical acceptance.

## Mandatory blocks before operational readiness

Independent tamper-resistant monotonic root; durable witness + permit authority with
separate UIDs; independently managed service lifecycle, OS MAC/LSM containment of
all same-UID legacy entrypoints; an authenticated cross-UID broker; verified non-bypass
of production interfaces; comprehensive crash/SIGKILL/restart/replay/rollback matrix;
physical integration and safety authorization. No assertion of these controls has
been made in this workspace.

See `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`,
`docs/ASSURANCE.md`, and `contracts/SP-IC-004.security-v0.1.schema.json`.
