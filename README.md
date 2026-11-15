# SnowPiercer Ecosystem

An ongoing, multi-subsystem project. **TrainOS** is one of the ecosystem subsystems, not the complete ecosystem. This repository contains distinct module branches and a central integration branch.

## Главная страница и обзор

- **[Главная страница / Archived Workspace](TrainOS-Workspace/site/index.html)** — authentic uploaded website snapshot with `#overview` and `#domains` sections.
- **[Обзор проекта](TrainOS-Workspace/overview.md)** — readable Markdown summary.
- **[Обзор — отдельная HTML-страница](TrainOS-Workspace/site/overview.html)**.
- **[24 функциональные области TrainOS](TrainOS-Workspace/functional-areas.md)** — independent Markdown page.
- **[Функциональные области — отдельная HTML-страница](TrainOS-Workspace/site/functional-areas.html)**.

Original site URL requested by the project owner: https://trainos.artisticfoam8.chatgpt.site/#overview . The live site was **unavailable for verification**. The included page and assets originate from the user-uploaded TrainOS Workspace snapshot, marked **TrainOS v101**. It does not claim to reflect the current v107 source or production readiness.

Run the archived HTML locally with a static file server if you want the app's navigation and scripts. GitHub's HTML file preview does not execute the application.

## Подсистемы, источники и Git-ветки

| Subsystem | Branch | Requested source baseline | Current state |
|---|---|---|---|
| TrainOS | [`module/trainos`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/trainos) | `v107` | SOURCE_RECOVERED / IMPORT_PENDING — v107 ZIP bytes and manifest verified; full current-host suite incomplete |
| RailSystem | [`module/rail-system`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/rail-system) | `RAIL-TRUST-016` | SOURCE_BLOCKED — precise snapshot unavailable |
| Energy | [`module/energy`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/energy) | `ENERGY-CORE-020 / v0.20.0` | SOURCE_IMPORTED / PRODUCTION_NO_GO |
| Life Support | [`module/life-support`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/life-support) | `LIFE-CORE-021 / v0.21.0` | SOURCE_IMPORTED / PRODUCTION_NO_GO |
| Logistics | [`module/logistics`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/logistics) | `LOG-CORE-021 / v0.21.0` | SOURCE_IMPORTED / PRODUCTION_NO_GO |
| Security | [`module/security`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/security) | `v0.1.0 candidate` | SOURCE_VERIFIED / IMPORT_PENDING — simulation-only, NO-GO |
| AI / Cognition | [`module/ai-cognition`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/ai-cognition) | `AI-CORE-021` | SOURCE_IMPORTED / PRODUCTION_NO_GO |
| Island | [`module/island`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/island) | `ISLAND-GEO-022` | SOURCE_RECOVERED / IMPORT_PENDING — ISLAND-GEO-022 ZIP, SHA256SUMS and 3×200 regressions verified |
| Integration & Operations | [`module/integration-operations`](https://github.com/JavaProgrammerFromEastEurope/SnowPiercer-Ecosystem/tree/module/integration-operations) | `SP-OPS v0.1.0 candidate` | SOURCE_VERIFIED / IMPORT_PENDING — simulation-only, NO-GO |

**Source import** is not a new functional Stage. Four imported source trees were checked for ZIP CRC, path traversal, duplicate paths, symlinks, UTF-8 validity, and Python syntax. Their import commits preserve parent history and include `IMPORT_PROVENANCE.json` with ZIP SHA-256 per file. Historical evidence within archives is not a live test result from this host.

**Source recovery update (16 November 2026):** The exact user-uploaded TrainOS v107 and ISLAND-GEO-022 ZIP bytes have now been recovered and verified locally against their cumulative file manifests. TrainOS v107 SHA-256 `661c0346721f7aa3ace1572430f4259d78bba722c3c4eab540de05eaa36ac284`; Island 022 SHA-256 `e71d3d78c79dcea71e151c9d34d10b460a61b0a782eb927042f1c286dab42ce9`. The GitHub module branches have **not** yet been updated with these sources. RAIL-TRUST-016 exact ZIP remains unavailable; RAIL-TRUST-015 is not a substitute. Current-host TrainOS full strict regression remains incomplete. All production is NO-GO. See [source recovery evidence](AUDIT/exact-source-recovery/2026-11-16.md).

## Правила разработки

- Two sequential **verified functional Stages** per module, one commit per Stage with the actual module version; module-level changes are distinct from import commits.
- Daily check at **00:00 UTC** only attempts publication when source, tests, approval, trusted runner and Git CAS evidence are satisfied.
- Integration into the default branch is independent, requires full cross-module compatibility evidence and explicit review; no blind merge or force push.
- For safety-critical real-world operations, production remains **BLOCKED / NO-GO** until independently verified isolation, immutable witness/rollback root, OS enforcement, and physical acceptance are established.

## Источник и происхождение

The preserved source ZIP for each imported module is identified by SHA-256 in its branch's `IMPORT_PROVENANCE.json`. TrainOS Workspace's historical frontend and 24 domains are kept under [`TrainOS-Workspace`](TrainOS-Workspace/README.md). This README reports exact confirmed source import state and is not a certification of autonomous development.
