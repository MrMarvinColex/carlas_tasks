# Research-oriented Restructuring, 2026-10-01

**Decision record:** R01/R02 in [decisions](decisions.md). **Authority:** the user approved implementing the discussed repository restructuring after reviewing its rationale and Mac/VM transfer rules. This document is the durable explanation for future developers and a detailed commit description. It records intended architecture and current migration scope; local checks do not substitute for a GPU run.

**October 2 follow-up:** the original changes are now preserved as four commits; audit lifecycle/identity fixes and the reusable library foundation have separate commits. [Library handoff](library-handoff.md) and R03 describe the implemented rig/capture contracts and remaining live migration. Historical audit measurements below remain evidence of the original restructuring.

## Problem and audit evidence

The repository grew coherently through assignment stages, but active agent memory combined requirements, current state, run chronology, technical references and report material. Each task was instructed to load AGENTS, STATUS, requirements, decisions and plan, then additional guides. The audit presented in this conversation measured **107,035 bytes / 14,622 English words** in mandatory startup text before code. English translation did not solve the structural repetition.

The reviewed 28 chat files showed 12 context compactions in nine sessions, 23 broad reads of the four mandatory docs, 47 broad STATUS reads and 41 decisions reads. These are audit counts, not model billing/token measurements; chat files also contain images. A [September 23 session](../logs_chats/2026/09/23/rollout-2026-09-23T11-58-28-01a0ce21-addb-7eb0-ab61-4673042371cb.jsonl) illustrates compaction followed by broad rereading/truncation.

The process audit distinguishes legitimate waiting from repeated execution: 41 status checks in one case monitored one experiment. A [September 24 session](../logs_chats/2026/09/24/rollout-2026-09-24T10-38-35-01a0d2fe-e799-7f83-a711-23445b9d0464.jsonl) instead relaunched a GPT scene replay after the orchestration handle returned; the original process also completed. Wide pgrep -af could capture a roughly 17,000-character service command. Waiting, process completion and data acceptance need separate recorded states.

Old docs contradicted themselves: the runbook still claimed no code/routes/dataset, while later STATUS paragraphs recorded completed results and left superseded animal/API questions open. Agents had to reconcile historical and current claims every time. Later scripts imported utilities from earlier stage scripts, coupling execution entry points to implementation. Approved routes lived inside a historical run, making new VMs depend on selectively restoring an otherwise 30+ GB output archive. Batch skip logic keyed only on route/weather, risking skipped new-camera experiments.

## Selected structure

```text
AGENTS.md                       permanent rules and reading contract
README.md                       human entry and workflow links
docs/STATUS.md                  current task, checks, continuation
docs/PROJECT.md                 small topic map
docs/{cameras,scenes,experiments,vm-workflow}.md
                                topic guidance, read on demand
docs/architecture.md            migration rationale, read on demand
docs/decisions.md                current changes in approach
docs/worklog.md                 short chronological entries
docs/archive/assignment-2026/   original docs, immutable snapshot
carla_tasks/                    shared implementation and CLI
scripts/                        compatible command/lifecycle wrappers
configs/                        checked-in settings and calibration
inputs/                         small versioned reusable data
artifacts/                      small result/export metadata
runs/, logs/                    generated data, excluded from Git
report/                         unchanged historical reports/figures
logs_chats/                     unchanged raw chat evidence
```

Mandatory startup is AGENTS + STATUS + PROJECT, with a **15 KiB combined ceiling**. The offline check-docs command checks the budget, active links and archive hashes without scanning runs/chats. History, reports and technical guides may grow independently because reading them is task-specific. Do not create a new global summary that gradually reproduces the archive.

STATUS is replaced with present facts; completed detail goes to one short worklog entry linked to machine evidence. Decisions explain new approaches; guides change when verified knowledge changes; reports change when reporting is requested. This supersedes the old requirement to update every narrative after every step.

Ten original AGENTS/README/docs files were copied byte-for-byte before edits (261,243 bytes) with SHA-256 manifest. Historical AGENTS is renamed AGENTS.snapshot.md to prevent automatic instruction discovery; its bytes are unchanged. The archive retains the original document layout and explains links to original repository/runtime context. Historical false starts and corrections remain intact. Reports, raw chats, results and the user's .gitignore edit are preserved.

## Stable baseline and flexible research

Preserve the recorded CARLA 0.9.16/Town01_Opt/Tesla/five-short-route/AV2-nine-pair/2-Hz setup as reproducible baseline. New rig layouts, dimensions, lossless formats, sample rates, routes, maps and authored scenes are declared variants. The user expressed interest in Unreal/editor work; this makes a future investigation possible without silently rewriting historical runtime-only experiments.

Permanent invariants are evidence, synchronization, lossless class IDs, complete pose records, secret protection, explicit publication/deletion authority and verified off-VM preservation. Model descriptions remain passive validated SceneSpec with fixed allowed execution. API hosting remains the default; no local models, engine build, map authoring or expensive experiments are part of restructuring.

Historical 0–9 stage numbers remain meaningful when explicitly requested. Stage 8 was declined, not completed; delivery was not public. New research no longer inherits the deadline or mandatory assignment progression.

## Shared code and compatibility

Implementation belongs in a Python package; execution commands call it. Geometry, image handling, dataset validation, export checks, runtime helpers, inputs and experiment identity have reusable modules. The intended dependency is command → orchestration → shared modules. Shared modules do not import command wrappers. Offline geometry/policy/input checks must not require CARLA import/server access.

Existing stage-named script paths remain compatible entry points and historical evidence references remain usable. Migration is incremental: moving every monolithic executor at once would obscure behavioral changes and is unnecessary to reduce current coupling. Adding a new experiment should reuse capture/validation functions rather than copy an entire stage script.

The command entry point is python -m carla_tasks; exact supported flags are provided by its help and [experiments](experiments.md). Supported Stage-3/4 capture and Stage-6/7 scene commands share an exclusive recorder lock; a competing process is rejected and exceptions release ownership. The batch coordinator uses a separate lock to avoid deadlocking its own workers. A managed process records durable identity, progress/log path and exit result. Tool-call completion cannot trigger a duplicate launch. Server startup distinguishes TCP listening from RPC readiness; default and baseline-batch image identity are pinned by digest. A unique lease records the exact created Docker container ID, so failed/interrupted launch and batch cleanup target only that attempt and cannot remove a replacement container sharing its name. Explicit batch --attach-server checks and uses a matching healthy existing server without taking cleanup ownership. Relevant shell/runtime behavior still needs a short GPU pilot.

## Git inputs and disposable VMs

Promote five approved route JSONs plus index from run 20260923T160431Z-shorter-routes-b72a9d to inputs/routes/town01_opt_short_v1. Original payloads total **375,114 bytes**; retain source run, map/version and file hashes. Change defaults/configs to that bundle while preserving original archive outputs. AV2 source calibration is already in Git. New VMs recover these with a clone/fetch, not a 30+ GB image transfer.

Small approved scenes can be promoted with response/provenance identity when needed. Large maps, cooked assets, images and complete logs remain external, with source/version/hash manifests tracked in Git. Do not use Git LFS merely to move all generated results into the code repository.

Git preserves code/settings/inputs/metadata. rsync preserves full execution data; verify destination bytes against manifest and record external location/time/evidence. VM deletion requires both remote-code confirmation and verified retained results. A small registry travels through Git for resume. New verified-copy records require matching manifest-covered execution-host identity and a distinct verification host; same-VM rehashes cannot become external-backup proof. This establishes recorded destination evidence, not perpetual accessibility. Deletion checks include actual machine/storage context and current independent preservation evidence. Do not turn uncertain historical backup statements into verified claims during migration.

## Configuration identity and preparation reuse

One implementation serves baseline and variant configurations. Avoid deep configuration inheritance; planned baseline-plus-overrides resolution saves a complete final configuration in every run. Existing complete stage JSON configurations are retained during migration.

Distinguish experiment ID, configuration/input fingerprint, execution run ID and repeat index. Fingerprint relevant settings and content-addressed inputs, including route/calibration/weather sources, rather than only route/weather names. The batch recomputes identity before and after each capture; input/source drift fails the attempt rather than accepting stale metadata. Changing cameras/timing/inputs must create new matching identity; a requested additional repeat remains a new measurement even when settings match.

A portable successful-run record supports resume without copying images only when it retains matching identity and validated manifest/export evidence. Legacy runs lacking identity cannot be imported by inventing a fingerprint from current settings: keep them in artifacts/index.csv. Newly identified runs can be imported after local manifest and baseline-validation verification. Skipping is a resumption decision, not renewed validation of remote data. Failures/interruption stay visible and cannot satisfy a matrix cell. Relevant recorder/validator/runtime source hashes participate in identity; run metadata additionally records Git/environment identity. Runtime options also participate, so writer-setting changes are conservative new identities.

Reuse deterministic preparation (route data, calibration conversion, declared asset preparation) only when inputs and relevant versions match. Replay a saved accepted scene without paying for a new response when scene repetition is the goal. Requested API variability/latency and drive repeat measurements always need actual executions. Seed equality does not make them duplicates.

## Validation and deferred work

Local acceptance checks must cover archive bytes/hashes; Markdown links and startup budget; promoted input hashes and no historical-run defaults; CLI help/offline paths; changed geometry/dataset/export/policy behavior; configuration/repeat identity and no loose skips; durable process state; shell syntax/owned-container safeguards. Tests should target behavior and failure cases, not duplicate implementation. Final results belong in [STATUS](STATUS.md) and [worklog](worklog.md).

No CARLA/API/network run is performed on Mac. Moving functions/defaults and mocked runtime checks preserves intended compatibility but does not prove live recorder behavior. The next validation is a short baseline recording on a new VM restored from Git alone, followed by actual external export verification.

October 2 adds a versioned perspective RGB/semantic rig schema and an offline-tested recording kernel. Still deferred: its live CARLA backend and route/scene integration, additional formats/projections, a general config override resolver, authored-map toolchain, derived-asset restoration automation, complete live recorder progress and statistical repeats. See the handoff for bounded migration tasks. Optimize throughput after measuring writer/disk/API/application costs rather than assuming all repeated tool output is repeated simulation.
