# Current Research Requirements

These rules replace assignment-only constraints for new research. The [original requirements](archive/assignment-2026/docs/requirements.md) remain unchanged; historical experiments retain original acceptance criteria.

## Permanent invariants

- Preserve evidence, failures, secrets and recoverable code/data across disposable VMs.
- Record resolved configuration/input identity, run ID, seed, revision/dirty state, environment, timestamps and validation.
- Align requested streams and same-frame pose; preserve semantic IDs losslessly and final `transforms.json`.
- Execute passive validated model descriptions through allowed operations. Preserve API provenance and separate API/application/simulation/wall times.
- Define controls, repeats and acceptance before measurement; seeds alone do not prove determinism.
- Require explicit authorization for publication, infrastructure/resources and deletion; verify external preservation before deleting a VM.

## Baseline and experimental choices

The baseline remains Docker CARLA 0.9.16, Ubuntu 22.04/NVIDIA, Town01_Opt, Tesla, five short routes, nine AV2 RGB/semantic pairs, 2 Hz and API-hosted models.

Camera layout/count/resolution, lossless storage layout, sampling, map/routes, authored scenes, models and repetitions can vary in a declared experiment. Engine/build work needs its own plan and validation; it is not implemented by restructuring. API hosting remains the default; do not install local weights automatically.

The old deadline, delivery checklist and stage order do not govern new research. Requests for historical stages use the fixed [0–9 plan](archive/assignment-2026/docs/plan.md) and its evidence.
