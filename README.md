# CARLA Scene and Camera Experiments

Research tools for CARLA routes, RGB/semantic recording and validated LLM scene descriptions. Work alternates between a Mac for offline development and disposable Ubuntu GPU VMs for simulation/API experiments.

Start with [STATUS](docs/STATUS.md) and the [project map](docs/PROJECT.md). Agents follow [AGENTS](AGENTS.md). The [architecture record](docs/architecture.md) explains the October 2026 restructuring, rationale, compatibility and deferred work.

## Code and data

| Path | Purpose | Transfer |
|---|---|---|
| `carla_tasks/` | Shared Python implementation and command entry | Git |
| `scripts/` | Existing command wrappers and VM lifecycle scripts | Git |
| `configs/` | Settings and preserved AV2 calibration | Git |
| `inputs/` | Small versioned reusable routes/scenes | Git |
| `artifacts/` | Result/export registry | Git |
| `runs/`, `logs/` | Execution outputs | rsync |
| `docs/archive/assignment-2026/` | Preserved assignment-era documents | Git; on demand |
| `report/` | Historical working/reader reports | Git; on demand |
| `logs_chats/` | Preserved chat evidence | External archive; selective reads |

Approved route inputs belong in `inputs/routes/town01_opt_short_v1/`; a new VM does not need the historical image tree. Large maps/assets use versioned external sources and checksums.

## Workflows

- [Cameras and recording](docs/cameras.md): calibration, synchronization and baseline limits.
- [Scene work](docs/scenes.md): road markings, SceneSpec, deer and authored-map experiments.
- [Experiments](docs/experiments.md): configuration/repeat identity and process continuation.
- [VM workflow](docs/vm-workflow.md): recovery, Git, rsync and integrity checks.

The reproducible historical baseline is CARLA 0.9.16, explicitly selected Town01_Opt, Tesla Model 3, five short routes, nine AV2 RGB/semantic pairs and 2 Hz simulation-time capture. These can vary in separately declared experiments. New settings have not automatically been simulated.

## Offline start on Mac

From the repository root, use system Python without the CARLA wheel:

```sh
python3 -m carla_tasks check-docs
python3 -m carla_tasks check-inputs
python3 -m carla_tasks plan --config configs/stage4_baseline_matrix.json
python3 -m carla_tasks scene-check fixtures/stage6/valid_parked_vehicle.json
python3 -m unittest discover -s tests
```

Input checking, matrix planning and static SceneSpec v1.0 validation are offline operations. The scene-check command does not support the animal v1.1 policy. See [experiment commands](docs/experiments.md) for registry/process/export operations and [VM workflow](docs/vm-workflow.md) for actual captures. A new rig or live server is not validated by these checks.

The reusable library foundation has a rig-driven recording kernel, bounded frame/writer queues and a lossless capture writer. Try `python3 examples/record_synthetic.py --output /tmp/carla-synthetic-UNIQUE`; this uses synthetic data and requires a new directory. The live CARLA backend and route/scene migration remain pending. [Library handoff](docs/library-handoff.md) contains contracts, runnable checks and ordered implementation tasks; the core can also be installed as one package without CARLA dependencies.

## Historical evidence

Stages 0–7 were recorded complete; stage 8 was declined and remains TODO; delivery remained IN_PROGRESS. The [archived status](docs/archive/assignment-2026/docs/STATUS.md), [English working report](report/report.md), [Russian report](report/final_report_ru.md) and [artifact registry](artifacts/index.csv) retain evidence and backup limits. This restructuring does not publish materials or close historical acceptance criteria.
