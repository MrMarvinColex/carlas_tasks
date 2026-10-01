# Maps, Scene Editing and LLM Execution

## Tested runtime baseline

Use the explicitly selected Town01_Opt, not an implicit substitution for Town01. After each world load, hide returned RoadLines environment objects through World.enable_environment_objects. Paired RGB/raw-semantic observations passed at straight/intersection/traffic-control locations in `20260917T153000Z-town01-opt-coverage-b6e3`; this is not map-wide/crosswalk coverage. Base Town01 hiding removed semantic line pixels but retained visible markings. Decals/texture probes failed and stay in history.

Five approved short routes come from [inputs](../inputs/README.md). Hiding geometry does not demonstrate visual-autonomy performance: Traffic Manager uses simulator state rather than project RGB.

## Restricted LLM path

Model output is passive versioned SceneSpec, strictly validated then applied by fixed allowed operations. Never eval/execute model code. Preserve prompt/response, exact provider/model/settings, retry policy, usage, timings, resolved transforms and outcomes. Replay accepted saved scenes without another API call; new calls are required when API variability is the measurement.

Stage-6 policy is in [config](../configs/stage6_scene_editing.json): the straight route, selected weather profiles and bounded parked Audi placements. JSON validity does not prove live spawn feasibility. Check map/blueprints, driving-lane placement and spawn conflicts before mutation. Retain failures. The fixed API pilot is compliance/integration evidence, not a statistically reliable model ranking or cost study.

## Animal capability

The stock image had no observed usable animal. AnimaSim v0.2.1 supplies cooked animal assets for 0.9.16 in a separately derived image. Exact release source, 243,116,126-byte archive, SHA-256 and image details are in [probe config](../configs/stage7_animasim_probe.json); asset preparation is external to Git. Preserve the base image unchanged and verify source/licence/checksum when restoring.

`static.prop.deer` passed grounded spawn, front-centre RGB and raw Dynamic-class visibility, a 12 m lateral path at 2 m/s and direct collision geometry in `20260924T135331Z-animasim-deer-front-probe-grounded-d91894`. Motion is repeated transforms without gait animation; no TM braking or full-rig edited-drive result is claimed. [Stage-7 policy](../configs/stage7_scene_editing.json) exposes only the tested bounded crossing. Three API replies replayed that one scene; identical scene content is not broad generative ability.

## Authored scenes and maps

New research may investigate Unreal/editor authoring separately from runtime edits. Before implementation define the changed geometry/assets, compatible CARLA/Unreal toolchain, source and packaged-output versions, navigation/semantic effects, licence and recovery procedure. Store small source manifests/settings in Git and large cooked maps/assets externally by checksum.

A rebuilt map must pass map load, waypoint connectivity, spawn/route execution, camera semantics/alignment and the experiment-specific visual checks. Do not assume unchanged town name or a successful build preserves old route evidence. The current local restructuring does not build an engine or edit a map.

Detailed evidence/source review: archived [knowledge](archive/assignment-2026/docs/knowledge.md), [decisions D23–D26](archive/assignment-2026/docs/decisions.md), [working report](../report/report.md) and [artifact registry](../artifacts/index.csv).
