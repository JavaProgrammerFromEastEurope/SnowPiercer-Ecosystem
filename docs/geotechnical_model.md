# ISLAND-GEO-001 — Conceptual geotechnical screening

This stage provides an **illustrative, non-design** one-dimensional stress model using synthetic inputs. All depths are metres below grade, unit weights kN/m³, pressure kPa, and force kN. Total vertical overburden = sum(layer thickness × bulk unit weight). Hydrostatic pore pressure = 9.81 × max(0, depth - groundwater depth). Effective stress = total - pore pressure under the illustrative hydrostatic assumption. Surface applied force = pressure × footprint. Surface surcharge is NOT included in vertical overburden. No bearing capacity, settlement, stability, seismic, liquefaction, uplift, drainage, consolidation, heterogeneity or uncertainty bounds are calculated. Groundwater unknown returns null, never zero. No soil parameter is calibrated; synthetic data must never be mistaken for site data.

## Interfaces and limitations

`island.geotechnics` provides `Layer`, `Site`, `screen`, `total_vertical_stress_kpa`, `hydrostatic_pore_pressure_kpa`, `GeotechnicalInputError`. The prior `island.validation` API is unchanged. The interface contract in `contracts/geotechnical_interface.json` is a draft, not a live integration. Values are illustrative, not code-compliant design values. Field investigation, groundwater monitoring, regional hazards, applicable national standards, licensed engineer review, and independently verified calculations are prerequisites for design. `verified-field` is merely a user-provided label, not attestation; never grants approval.

## Risk treatment

Risk flags are qualitative triggers, not quantified risk scores. Even when flags are empty, engineering approval remains BLOCKED/NO-GO. Synthetic test coverage cannot prove field safety.
