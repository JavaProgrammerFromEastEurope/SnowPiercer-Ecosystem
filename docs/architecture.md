# Conceptual architecture / ADR-001

Island is a physical-infrastructure domain with eight asset groups: GEO, CIV, UND, UTL, TRN, DAT, ENV, OPS. The dependency model is a directed graph, not a verified engineering bill of materials.

## Boundaries

Island provides site/facility status and receives alarms through future authenticated interfaces. No actuator permissions are specified or granted. TrainOS orchestrates, Energy supplies utility coordination, Rail Systems manages railway interfaces, Life Support defines habitability services, Logistics supplies material flow, Security defines physical protection, and AI/Cognition provides advisory analysis only. All integration semantics are TBD.

## Assumptions and blocking items

Site unknown; geography, soil, water table, seismicity, weather, loading, population, railway geometry, legal codes and regulator unknown. Physical construction cannot be authorized. No operational availability, redundancy or safety claims follow from these models.
