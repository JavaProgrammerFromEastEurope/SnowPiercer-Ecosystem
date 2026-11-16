# ISLAND-GEO-002 — Architecture, assumptions, limitations

The v0.2.0 public API (`island.geotechnics`) is preserved unchanged. New independent module `island.groundwater` provides `Interval`, `WaterObservation`, `GroundwaterSeries`, `Scenario`, `interval_screen`, and `propagate_risks`.

## Computational contracts
- Depth is measured positive downward; observation time is days from a caller-defined epoch. Groundwater depths must be nonnegative.
- Piecewise linear interpolation is performed independently for interval endpoints; outside the observation window the operation raises `GeotechnicalInputError`. Missing observations result in unknown pore/effective stress.
- Total vertical overburden is an illustrative 1D sum of depth-weight products. Pore pressure assumes static hydrostatic water, 9.81 kN/m³, and no capillary effects. Effective stress bounds are total.low minus pore.high and total.high minus pore.low. Rounded outputs are not certified engineering calculations.
- Dependencies map target asset to upstream risk sources. Flags propagate to a monotone fixed point, including cycles. This is a logical exposure model, **not** physical flood/settlement simulation.
- Assumptions: homogeneous interval weight per layer, deterministic time interpolation, independent worst-case parameter combinations, no consolidation, flow, transient pore-pressure PDE, seepage, settlement, liquefaction, seismic or load-bearing design.

## Interfaces and traceability
`contracts/groundwater_uncertainty_interface.json` is a proposed additive contract, not a deployed IPC service. `ISLAND-GEO2-001..008` trace to `tests/test_stage003.py`. Five preliminary hazards are appended to `safety/hazards.json`.

## Readiness and validation boundaries
No field data, licensed engineer, site survey, boreholes, piezometers, calibration, code compliance assessment, construction permits, physical safety case, or independent end-to-end verification are supplied. Even a caller-provided `verified-field` label is not cryptographically attested. **Physical deployment remains BLOCKED/NO-GO**. Software tests validate implemented invariants only.
