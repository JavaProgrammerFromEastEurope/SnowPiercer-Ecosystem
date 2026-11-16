# ISLAND-GEO-005 / ISLAND-GEO-004 stage naming

This release implements **ISLAND-GEO-004**; internal requirements use `ISLAND-GEO-005` numbering because historical ISLAND-GEO-003 used `004` requirement IDs. The historical IDs remain unchanged to preserve traceability.

## Method

Piecewise-linear interpolation of interval head bounds at a common time coordinate. Evaluate all upstream and downstream observation knots within the requested window, plus both endpoints. At each knot reuse the static 1D Darcy interval screening model. Aggregate extrema of gradient, specific discharge and volumetric discharge. This enclosure holds for piecewise-linear head bounds, time-independent nonnegative conductivity intervals, and fixed path geometry; it does not solve the transient flow PDE. Unknown knots or conductivity make all numeric envelopes unknown.

## Explicit exclusions

No transient diffusion, delayed groundwater response, storage, anisotropy, nonlinear unsaturated seepage, erosion, piping, site calibration, uncertainty probability distribution, or engineering approval. Flag propagation is a logical information flow, not physical hazard containment.

## Safety

NO-GO for design, construction, operations and certification. External site investigation, groundwater monitoring, peer review and applicable codes remain required.
