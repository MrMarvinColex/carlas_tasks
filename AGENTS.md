# CARLA Test Task Working Rules

This repository is the portable memory of the project. A new agent is not guaranteed to have access to the original chat history. Recover context from these documents and the actual files. Speak to the user in Russian unless the user asks otherwise; write project documentation, logs, and the working report in English. Explain unfamiliar terms plainly: the user knows some classical ML but is learning CARLA and LLM workflows.

## Start of Every Task

1. Check the working directory, Git status, and applicable instructions. Preserve existing user changes. On the target server, the expected project directory is `~/carla_test_task`; the server user is `Ubuntu`, including case. Read the actual home directory from the environment rather than assuming it.
2. Read [STATUS](docs/STATUS.md), [requirements](docs/requirements.md), and [decisions](docs/decisions.md). Then read [the plan](docs/plan.md), especially the requested stage and its dependencies.
3. Read the additional documents selected by the table below. Do not reread the whole work log or report each time; use the current entries and sections relevant to the task.
4. Briefly state the intended outcome of the stage. When the user says “stage N” or “этап N”, use the fixed 0–9 numbering in the plan. Do not confuse it with sections 1.1–5 of the original assignment.
5. Check the stage prerequisites. Resolve ordinary local issues within the task. If a material decision or access is missing, record the exact blocker; continue useful independent work where possible.

| Task | Additional reading |
|---|---|
| Project transfer, new VM, environment | `README.md`, `docs/environment.md`, `docs/runbook.md` |
| Map, road markings, animal | Relevant sections of `docs/knowledge.md`; risks in `docs/decisions.md` |
| Routes, cameras, recording | `docs/knowledge.md`; acceptance criteria for stages 2–4 |
| LLMs, literature review, comparison | `docs/knowledge.md`; stages 5–8; relevant parts of `report/report.md` |
| Exporting or ending a VM session | `docs/runbook.md`, `artifacts/index.csv`, `docs/STATUS.md` |

## Requirements and Scope

- Baseline: CARLA 0.9.16 in Docker on Ubuntu 22.04 with an NVIDIA GPU. The client, data recording, and LLM API calls run on the server. Do not deploy local models.
- Map: Town01. Town01_Opt is an allowed candidate for map layers, but its presence and suitability must be tested and the actual map name recorded. Do not silently substitute another town for Town01.
- Edit the scene through the CARLA API at runtime. Do not switch to Unreal scene editing, engine builds, or importing assets through Unreal without discussing a changed approach.
- Remove visible road markings while preserving the navigation structure. `Decals`, `RoadLines`, and texture replacement are not yet confirmed in this project as a complete solution.
- Use five connected routes, each with at least 10 waypoints. Choose any larger waypoint count or route length for meaningful runs, not as an additional user requirement.
- Use all nine Argoverse 2 camera positions; attach RGB and semantic-segmentation sensors at every position: 18 sensors. Save images and the ego vehicle transform at 2 Hz of simulation time, aligned by frame and timestamp.
- Each completed drive must produce one complete `transforms.json`. JSONL is allowed as an intermediate write format. Preserve semantic class IDs losslessly; treat colour palettes as previews.
- The LLM produces a validated scene description; the executor performs only allowed CARLA operations. Do not execute arbitrary code returned by a model. Prompts must only offer capabilities that the executor has actually verified.
- A visible moving animal with a measurable effect on the scene is required. A pedestrian, a cube, or an image overlaid onto RGB does not satisfy this clarified requirement. Availability of an appropriate asset is still unknown.
- Target comparison variants: GPT-Astra, a Qwen model around 27B, and a Qwen model around 8B through APIs. Exact IDs, providers, and access remain to be verified. Record model-generation substitutions; do not attribute every difference solely to model size.
- Development uses a private repository. The final delivery requires public code and a report/dataset on Google Drive. Preparing materials does not authorize changing repository visibility or publishing files.

## Evidence and Reproducibility

Use these labels: **requirement**, **decision**, **user-reported**, **artifact-confirmed**, **documented**, **hypothesis**, **open question**. The initial CARLA launch was reported by the user; raw logs are not included in this package. Do not claim you ran experiments on the remote server.

Stage statuses are `TODO`, `IN_PROGRESS`, `BLOCKED`, and `DONE`. Set `DONE` only after the acceptance criteria have been met and evidence is linked. “Code written” is not “tested.” Do not populate the report with invented measurements, screenshots, or results. Keep failed experiments as failed experiments.

For every run, store a unique run ID, configuration, seed, Git commit and dirty-state indicator, CARLA server/client versions, image identifier, timestamps, logs, and validation result. For LLMs also store the exact model/provider/settings, prompt, response, retries, and timing. Exclude secrets from all logs. These requirements guide future implementation; the code and formats have not yet been created.

Compare equivalent routes and weather conditions. Separate API latency from scene-application time, and simulation time from wall-clock time. A fixed seed helps reproduction but does not by itself prove complete determinism. For cameras, validate frames/timestamps, drops, coordinate transforms, and vehicle occlusion. Remove debug drawings before recording the dataset.

## Documentation After Each Meaningful Step

- Update `docs/STATUS.md`: current position, completed work, blockers, and the exact next action.
- Add a chronological entry to `docs/worklog.md`: what changed, how it was checked, the outcome, and evidence paths. Keep failures.
- Add new architectural decisions or approach changes to `docs/decisions.md`, stating what they replace.
- Add verified technical knowledge to `docs/knowledge.md` with a source or run ID.
- Update the relevant section of `report/report.md`. Keep planned work and completed experiments visibly distinct.
- Register results in `artifacts/index.csv`; record an external location and integrity check for exports. A local folder does not prove a backup exists.

Avoid duplicating a fact across documents without need. Requirements belong in `requirements.md`, current state in `STATUS.md`, decisions in `decisions.md`, and technical notes in `knowledge.md`.

## Disposable VM and Authority

The VM is disposable. The user reported that stopping a container or VM does not stop billing, that deleting the instance is required, and that deletion is irreversible. Do not change pricing or resources and do not delete the VM without explicit user instruction. Before deletion, confirm that code and results are preserved outside the VM according to `runbook.md`.

Never commit `.env`, keys, dataset images, large logs, or model weights. The user restores secret backups securely; do not ask the user to paste keys into chat. `.env.example` contains empty values only.

Do not use `sudo` for routine repository or Python-environment work. Docker on the current VM was reported to require `sudo`; verify the actual state first. Do not start expensive bulk experiments before a short run validates recording, free disk space, and the export path.

## End of a Task

Report the outcome, completed checks, artifact locations, remaining constraints, and the next stage. Do not automatically continue through the entire assignment when the user assigned one stage. If stopping mid-stage, leave an exact continuation point in `STATUS.md`, including unfinished processes. A new agent must be able to continue without chat history.
