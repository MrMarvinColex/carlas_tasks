# CARLA Test Task: LLM-Based Scene Editing

This is the portable context package for the test assignment “Using LLMs with the CARLA Autonomous Driving Simulator.” It was prepared on 16 September 2026 from the original PDF and the user’s clarifications. The working deadline is 21 September; the PDF does not state a year, and 2026 is inferred from the current context.

**This package now contains the reproducible environment, map probes, five approved/driven routes, and a locally validated 18-camera Stage-3 recorder plus dataset validator. It does not yet contain the Stage-4 baseline matrix or an LLM executor.** Do not treat later-stage experiments as already completed.

## What the Project Builds

CARLA 0.9.16 runs in Docker on a temporary Ubuntu GPU VM. A Python client controls Town01, drives an ego vehicle along five routes, and records RGB images, semantic labels, and the vehicle pose. The rig uses the nine Argoverse 2 camera positions with two sensor types per position and records at 2 Hz of simulation time.

LLMs are called only through APIs. They translate natural-language requests into validated descriptions of scene changes, which a restricted executor applies through CARLA. Three selected model variants are compared. Unreal scene editing is outside the agreed approach. The deliverables are reproducible code, a dataset, and a report.

## Moving to VS Code

1. Save this package on the Mac. The ZIP contains one top-level directory: `carla_test_task/`.
2. Create or use the project’s private Git repository. If a project already exists, compare and merge files; do not overwrite working changes. Place the root `AGENTS.md` next to `README.md`, without an accidental `carla_test_task/carla_test_task` nesting level.
3. Keep the repository in external Git. The PDF under `docs/source/assignment.pdf` is ignored by Git by default and can be transferred separately. The English requirements summary is already in `docs/requirements.md`.
4. Open `~/carla_test_task` on the server with VS Code Remote SSH and start a new Codex task. Confirm that the agent sees the server directory and root instructions.
5. Ask the agent to recover context and finish stage 0. After that, assign the numbered stages separately.

Suggested first prompt for the new VS Code task, in Russian:

> Прочитай AGENTS.md и перечисленные в нём стартовые документы. Проверь рабочую папку и Git-статус. Кратко изложи текущее состояние проекта, ограничения и незавершённые проверки. Затем выполни оставшуюся часть этапа 0 из docs/plan.md. Веди статус, журнал и отчёт по правилам проекта. Не удаляй VM и не публикуй материалы.

Later prompts may be as short as:

> Давай займёмся этапом 1 из docs/plan.md. Выполни его критерии приёмки и обнови документацию.

To resume interrupted work:

> Продолжи текущий этап с точки, указанной в docs/STATUS.md. Сначала проверь фактическое состояние файлов и процессов.

No dedicated RAG system is needed. `AGENTS.md` sets the reading order, and the documents preserve knowledge independently of task history and VM lifetime. See the [Codex AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Tools, connectors, and personal skills from a previous chat do not automatically transfer to Codex in VS Code. The core stages need terminal and file access on the server; literature review, API calls, and uploads also require the relevant network access and credentials. The documents do not grant Google Drive or paid API access. If a source is unavailable, record the limitation instead of inventing verification results.

## Navigation

| Document | When to use it |
|---|---|
| [AGENTS.md](AGENTS.md) | Agent working rules |
| [Requirements](docs/requirements.md) | Original assignment and user clarifications |
| [Stage plan](docs/plan.md) | Work items and acceptance criteria |
| [Current status](docs/STATUS.md) | Start and end of every task |
| [Decisions](docs/decisions.md) | Why an approach was selected; unresolved issues |
| [Environment](docs/environment.md) | VM facts and infrastructure checks |
| [Runbook](docs/runbook.md) | VM recovery, export, and session completion |
| [Knowledge base](docs/knowledge.md) | Verified sources, technical hypotheses, pitfalls |
| [Work log](docs/worklog.md) | History and evidence |
| [Working report](report/report.md) | Incrementally assembled final submission |
| [Artifact registry](artifacts/index.csv) | Result locations and backup-verification state |

## Stages

0. Reproducible environment and data safety.
1. Map and API capabilities.
2. Routes and autopilot.
3. Cameras and recording.
4. Baseline dataset.
5. Literature and repository review.
6. LLM-driven scene editing.
7. Moving animal.
8. Repeated drives and analysis.
9. Final delivery.

Run stages as separate tasks and preserve each result. Literature review and report preparation can be done on the Mac without a GPU. Check animal availability early in stage 1 so that the main risk is not deferred until the end.

## Where Code and Data Live

- Git: code, instructions, non-secret configuration, small tables, and report sources.
- VM: working copy and temporary experiment data.
- Mac or external storage: independent verified copies of large data and source logs.
- Google Drive: final report and dataset after preparation and authorized publication.
- API keys: server-side `.env`, ignored by Git; restore through the user’s secure source.

The Mac `rsync` hierarchy is the selected operational backup path; the stage-0 smoke copy was checksum-verified. Use the same method for every completed run before bulk recording. `.gitignore` prevents new matching files from being tracked, but does not scan already tracked files for secrets.

## Stage-0 Commands

Run these commands on the GPU VM from the repository root. `scripts/setup.sh` creates only `.venv`; it does not alter system Python. `scripts/run_carla.sh` starts one local offscreen server named `carla-server`; `scripts/stop_carla.sh` stops only that named CARLA 0.9.16 container. Both require the passwordless Docker `sudo` access verified during stage 0.

```sh
bash scripts/preflight.sh
bash scripts/setup.sh
bash scripts/run_carla.sh
run_dir="$(.venv/bin/python scripts/create_run.py --stage 0 --label smoke)"
.venv/bin/python scripts/smoke_rgb.py --run-dir "$run_dir"
.venv/bin/python scripts/finalize_run.py "$run_dir" --state complete
bash scripts/stop_carla.sh
```

The path was smoke-tested on 16 September 2026 in `runs/20260916T210617Z-carla-smoke-beb230`: it produced a readable 800×600 PNG with CARLA client/server 0.9.16. The run directory contains configuration, metadata, one `rgb/front.png`, diagnostics, and a SHA-256 manifest. To verify a copy made by the user-selected external mechanism, run `scripts/verify_export.py SOURCE_RUN EXTERNAL_COPY`; it compares every file and does not copy or delete anything. Do not call a second directory on this VM an external backup.

## Stage-1 Evidence

`scripts/stage1_map_api.py` is a small, synchronous capability probe: it loads Town01, creates/destroys a vehicle actor, captures paired RGB/raw-semantic views, checks rendered weather, catalogues environment objects/blueprints, and tests `RoadLines`. `scripts/stage1_texture_probe.py` tests the documented material-texture API only against resolved Town01 RoadLines names. Both create an auditable run directory and leave no actors behind.

On 17 September 2026, the probes confirmed Town01/Town01_Opt availability. On base Town01, direct RoadLines hiding is semantic-only; Decals and the tested texture calls also fail visible removal. On the explicitly selected `Town01_Opt`, however, `World.enable_environment_objects(RoadLines_ids, False)` removed the yellow markings in paired RGB views and raw semantic class 24 at a straight road, intersection, and traffic-control location, with sampled navigation intact. The coverage is not map-wide: no crosswalk API point was returned. See `docs/STATUS.md` and the six stage-1 registry rows. Apply the operation after every Town01_Opt load and retain RGB/raw-semantic validation. The stage-1 probe runs are local-only until copied and hash-verified on the Mac.

## Stage-3 Camera Check

`scripts/stage3_recording.py` loads the preserved AV2 calibration, aligns its rear-axle ego origin to the CARLA vehicle, spawns RGB/raw-semantic pairs at all nine positions, and groups callbacks by frame before pairing them with the same `WorldSnapshot` ego pose. `scripts/stage3_validate_dataset.py` checks timing, completeness, PNG integrity/dimensions, raw semantic encoding, and ego-body occlusion. The short all-camera run `20260919T162408Z-av2-all-cameras-short-247e3f` passed locally; it is not a complete Stage-4 route recording and is not externally backed up yet.

Example after starting CARLA and creating a Stage-3 run directory:

```sh
.venv/bin/python scripts/stage3_recording.py --run-dir runs/RUN_ID --sample-count 4 --mount-z-offset-m 0.5
.venv/bin/python scripts/stage3_validate_dataset.py runs/RUN_ID --require-all-nine
.venv/bin/python scripts/finalize_run.py runs/RUN_ID --state complete
```

The selected AV2 source is log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca`. CARLA uses its image dimensions and horizontal FOV derived from `fx`, but not arbitrary principal-point or full distortion coefficients. The explicit 0.5 m mount-height adaptation prevents the Tesla body from appearing in the images.

## Current Starting Point

CARLA 0.9.16 is validated offscreen on the RTX A6000. Stages 1–2 and the local technical checks for Stage 3 are complete; the Stage-3 run still needs a verified off-VM copy before its acceptance criterion is closed. The Stage-4 baseline matrix and a usable animal asset remain outstanding. See [STATUS](docs/STATUS.md) for details.

Before deleting a VM, push code and verify an external copy of results. According to the user, Stop does not end billing and Delete is irreversible. This package performs no VM operations.
