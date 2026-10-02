# CARLA Research Working Rules

This repository preserves code, reusable inputs and evidence across a Mac and disposable GPU VMs. Speak to the user in Russian; write project documentation and machine logs in English. Explain unfamiliar terms plainly. Follow the current request rather than treating the historical assignment as an active backlog.

## Start and recovery

1. Check the working directory, applicable instructions and Git status. Preserve existing user changes. Read [STATUS](docs/STATUS.md) and [PROJECT](docs/PROJECT.md). These three files are mandatory starting context; do not load the archive, report or full worklog by default.
2. State the intended outcome. Establish goal, changed parameters, controls and acceptance from the request/configuration. Read only the relevant guide below, then the specific code/artifact needed.
3. Distinguish Mac/offline work from GPU/VM work. Check prerequisites once per environment change. Read the actual home and repository path; do not assume a historical server path is current.
4. After compaction, recover from STATUS and the active configuration/process record. Check a running process before another attempt; do not replay full startup reading.

| Task | Read on demand |
|---|---|
| Cameras, routes, recording | [cameras](docs/cameras.md) |
| Scene/map edits, animals, LLM execution | [scenes](docs/scenes.md) |
| Configuration, repeats, processes, results | [experiments](docs/experiments.md) |
| New VM, Git/rsync, export, session end | [VM workflow](docs/vm-workflow.md) |
| Architecture/migration changes | [architecture](docs/architecture.md), relevant [decision](docs/decisions.md) |
| Original assignment or stage N | Relevant section of the [archive](docs/archive/assignment-2026/index.md) |

## Durable rules

- Keep a reproducible baseline. New layouts, formats, maps and authored scenes are experiment parameters, not changes to historical evidence. Docker CARLA 0.9.16 and API-hosted LLMs remain defaults; do not install local weights. Discuss material engine/build or infrastructure changes in the task implementing them.
- LLM output is validated passive SceneSpec data. Execute only verified allow-listed operations, never model-produced code. Preserve exact model/provider/settings, prompts, replies, attempts, timing and provenance. Record substitutions; do not attribute every difference to parameter count.
- Every run needs a unique ID, resolved inputs/configuration, seed, Git commit/dirty state, actual client/server versions, image identifier, timestamps, logs and validation. Separate simulation time, recording wall time, API latency and application time. A seed does not prove determinism.
- Pair requested images and ego pose by frame/timestamp. Keep semantic IDs losslessly and previews separately. Validate drops, transforms, dimensions and ego occlusion; clear debug drawings before recording. Completed drives require complete final `transforms.json`.
- Preserve failures and distinguish **requirement**, **decision**, **user-reported**, **artifact-confirmed**, **documented**, **hypothesis** and **open question**. Code written is not tested; local data or a transfer does not prove a verified backup. Do not invent remote experiments.
- Never commit secrets, `.env`, dataset images, large logs or weights; never request keys in chat. Do not publish, change repository visibility/resources, or delete a VM without explicit authorization. User-reported billing requires Delete rather than Stop; prove off-VM preservation before deletion.

## Efficient execution and handoff

Use Git for code/configuration/small inputs; rsync for large runs. Restore only needed data. Check free space/export destination, then validate a short run before a costly batch. Avoid routine sudo; verify actual Docker access.

Use stored process identity, progress and exit status. Poll with bounded output; read a small log tail on a new error. Avoid repeated full logs, wide `pgrep -af`, dataset recounting, or relaunching because an orchestration handle finished.

At meaningful completion, replace STATUS with current facts/checks/constraints, exact next action and unfinished process IDs. Append one short worklog entry linking evidence. Change a decision or guide only when its content changed; update reports when reporting is part of the task. Register identified runs/copy checks in `artifacts/run_registry.jsonl`; keep historical and other evidence in `artifacts/index.csv`. Keep mandatory startup under 15 KiB. Finish the assigned scope and report checks, paths, limits and next action.
