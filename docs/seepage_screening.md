# ISLAND-GEO-003 — Conceptual seepage screening

This module uses **steady 1-D Darcy** `i=(h_up-h_down)/L`, `q=k*i`, `Q=q*A`, with interval corner bounds. Negative flux indicates reverse direction. Zero-crossing indicates uncertain direction. Missing inputs yield null results, not zero. Critical-gradient comparisons are only **screening flags**, not uplift/piping verification. No 2-D/3-D flow, unsaturated flow, transient groundwater, anisotropy, heterogeneity, erosion, consolidation, soil-structure interaction, or construction approval is modeled. No site-specific evidence is supplied.

Risk graph edges are directed source-to-target and explicitly allowlisted. This is a logical propagation control, **not physical hazard isolation**. Existing Stage001/002/003 APIs are preserved. No third-party dependencies.

Physical deployment and engineering approval: BLOCKED/NO-GO. Independent investigation, applicable standards, design calculations, peer review, and permits are required.
