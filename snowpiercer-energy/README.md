# SnowPiercer Energy v0.18.0
Cumulative experimental library stages ENERGY-CORE-001 through ENERGY-CORE-018.
New: `energy.os_boundary` opt-in UID policy and OS path preflight.
Safety: BLOCKED / NO-GO. Legacy APIs remain importable; independent witness and end-to-end OS production enforcement are not demonstrated.
See `docs/ENERGY-CORE-018.md` and `evidence/`.

## ENERGY-CORE-019 (v0.19.0)

Adds `energy.ipc_diagnostics` with bounded accept, kernel-authenticated UID
checks, private production object preflight and read-only lock diagnostics.
See `docs/ENERGY-CORE-019.md`. The new mechanisms are opt-in and do not close
all legacy production bypasses. Safety status: BLOCKED; physical NO-GO.

## ENERGY-CORE-020 (v0.20.0)
Experimental bounded production IPC facade `energy.production_ipc_v4.BoundedIsolatedEnergyService`. See `docs/ENERGY-CORE-020.md`. Production BLOCKED; physical NO-GO.
