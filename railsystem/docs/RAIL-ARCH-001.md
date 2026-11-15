# RAIL-ARCH-001 — Architecture and Subsystem Registry

Status: **implemented in scaffold; local automated tests passing; independent architecture review pending**.

## Scope
The machine-readable `architecture/registry.json` inventories eight internal domains and eight external ecosystem boundaries. Every component has an identifier, responsibility, safety criticality, planned implementation status and dependency references. Every external boundary is **proposed** and explicitly prohibits actuation.

## Dependency rules
Internal references must resolve, be unique, not self-reference and form a directed acyclic graph. The validator rejects invalid identifiers, missing responsibilities, unknown classifications, duplicate entries, cycles and actuation-enabled external interfaces.

## Safety and assurance
The classifications are provisional architectural labels, **not** SIL assignments, hazard acceptance or certification. No safety case, hardware integration, live signaling, or movement authority is provided by this Stage. A formal hazard analysis and jurisdiction-specific standards applicability assessment remain outstanding.

## Acceptance evidence
- Registry JSON present and readable
- Validation on successful input and negative cases
- Existing v0.1 contract tests retained
- `python -m unittest discover -s tests -v` completes successfully

## Open decisions
- Confirm physical operating concept and railway jurisdiction
- Approve subsystem owners and design authorities
- Define versioned external contracts with TrainOS v80 and other domains
- Establish requirement IDs, hazard log and independent review
