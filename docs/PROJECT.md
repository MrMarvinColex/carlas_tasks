# Project Map

The active project explores CARLA cameras and scene editing. The assignment is an evidence archive, not the default backlog. Read this map and [STATUS](STATUS.md) at startup, then only the needed guide.

| Question | Entry point |
|---|---|
| Current task and continuation? | [STATUS](STATUS.md) |
| Permanent invariants versus experiment parameters? | [requirements](requirements.md) |
| Cameras, routes, timing and output? | [cameras](cameras.md) |
| Maps, runtime edits, animals, SceneSpec? | [scenes](scenes.md) |
| Configuration, repeats, process state? | [experiments](experiments.md) |
| Recover/end a VM and preserve data? | [VM workflow](vm-workflow.md) |
| Rationale and deferred scope? | [architecture](architecture.md), [decisions](decisions.md) |
| Continue implementing the reusable library? | [library handoff](library-handoff.md), only the active M1–M4 task |
| Historical claim or stage N? | [assignment archive](archive/assignment-2026/index.md), [reports](../report/report.md) |

Code and small inputs travel through Git; images, full run evidence and large logs through rsync with integrity checks. `inputs/` supplies approved routes without historical datasets; `configs/av2/` preserves source calibration.

The baseline uses CARLA 0.9.16/Town01_Opt, Tesla, five short routes, nine paired AV2 cameras and 2 Hz. Alternatives are separately configured experiments. API variants, asset availability and server state come from the chosen configuration and actual environment.

Keep current state short, guidance focused and history append-only. Existing stage-named scripts retain their names for compatibility; stage numbering does not govern new research.
