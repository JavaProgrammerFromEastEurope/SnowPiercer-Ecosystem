# Legacy production entrypoint audit — INITIAL INVENTORY ONLY

This workspace contains multiple independently versioned modules and a historic
TrainOS v101 source ZIP. This document does NOT claim a complete source-level audit
or that legacy execution routes are fenced.

Inventory targets for the next review: TrainOS scheduler, command/event bus, process
spawn/cgroup methods and recovery; RailSystem direct admission, recovery broker and
socket listeners; Energy issue/recover service and witness; Life Support write/recovery
IPC; Logistics dispatch and recovery; AI proposals and review bridge; Island brokers,
permit consumption and service lifecycle; integration probes, CLI tools and sidecar
scripts. Include entrypoints via package imports, CLI, user service units, aliases,
service-manager templates and shared file permissions.

Evidence required: per-entrypoint owners, UID/GID/MAC labels, listen socket,
privilege boundary, admission path, bypass trial, enforced denial result, and hash of
code + deployed policy. No such closure is claimed in this release.
