# Reusable Research Runtime

**Status: PROPOSED, 2026-10-02.** Follow-up to the [audit](../reviews/restructuring-2026-10-02.md). This is a design proposal; the interfaces below are illustrative and implementation has not started.

## Goal and package boundary

Make camera, route and scene variants use a reusable research package instead of a chain of assignment-stage scripts. Retain tested geometry, calibration, synchronization, encoding and scene policies. Build independence from historical stages and individual experiments; CARLA remains the simulation target.

Use one installable Python package in this repository, starting from `carla_tasks`, with focused internal modules and a thin CLI. Offline planning, geometry, input checks and dataset analysis should work on Mac. Simulation and model API dependencies are optional capabilities for their execution environments. Separate library repositories and plugin discovery have no demonstrated need yet.

| Logical area | Responsibility |
|---|---|
| Specifications and geometry | Experiment, rig, route, scene and capture descriptions; units, reference frames and pure validation |
| CARLA runtime | Connection, world/vehicle/sensor operations, route control, actual capabilities and owned-resource cleanup |
| Capture | Frame/timestamp alignment, bounded queues, same-frame ego pose and detached image buffers |
| Scenes | Allowed actions, live feasibility checks and updates during a drive |
| LLM generation | Providers, prompts, retries, provenance and validation into passive SceneSpec data |
| Experiments | Resolve inputs, plan cells/repeats, coordinate runs, resume policy and concise status |
| Artifacts | Dataset encoding/validation, manifests, registry and external-copy evidence |

These are responsibility boundaries, not a requirement to create empty subpackages. Commands call library interfaces; library modules never import stage scripts or parse CLI arguments. Specifications and offline checks do not import `carla`. Runtime-specific objects stay near the CARLA boundary; writers receive ordinary metadata and detached buffers.

## Contracts that make the split useful

Start with a few explicit contracts: `RigSpec`, `RouteSpec`, `SceneSpec`, `ExperimentSpec`, an aligned captured sample and a finalized result. Declare units, reference frames, required streams and validation rules.

The AV2 loader produces one rig preset. The recorder and validator use that rig's declared streams rather than a global nine-camera order. Custom layouts reuse the same pipeline. Initially retain paired RGB/semantic streams and a shared cadence; additional projections or asynchronous sensor rates require explicit capability work. Semantic IDs remain lossless.

Distinguish requested and applied settings. Vehicle geometry, asset availability and spawn feasibility can require CARLA. Record the applied rig, actual environment and adaptations; an offline plan does not establish successful live checks.

Only one owner advances simulation time. Route control, scene motion and capture participate in that loop. Define when actions apply and which frame/snapshot their measurements describe. A session owns its actors/settings and cleans up on success, exception or cancellation. Container ownership remains an explicit, separate lifecycle responsibility.

## Configurations and research variants

One experiment entry declares world/map version, routes, rig, accepted scene, capture settings and repeats. Reused presets may be referenced by name/version; one-off settings may remain inline. Avoid deep inheritance. Save complete planned and actual applied configurations in each run.

Example acceptance case: compare the current AV2 rig with three cameras on the same route/weather. The selected rig changes; capture, writing, validation and evidence lifecycle stay shared. Parked vehicles and animal motion similarly provide scene actions to the common loop.

Generation and replay are separate operations. A saved validated SceneSpec can serve several camera variants without another model request. API-variability studies still execute new requests and retain every attempt.

Separate study/matrix identity, effective measurement identity, repeat index and execution attempt. Expanding a matrix preserves matching prior cells. Keep full source/environment provenance and define equivalence explicitly. A newly requested repeat always remains a new measurement.

An authored map/build is a versioned input with source/build identity, location and checksums. Unreal authoring/building has its own tools and recovery procedure; the runtime consumes declared assets and performs supported scene actions. Verify navigation and semantics after map changes. Small specifications travel through Git; large assets/results use verified external transfer.

## Incremental migration

1. Correct audit findings in copy verification/import, per-cell reuse, wait outcomes and VM handoff. Cover their transition sequences before extending these mechanisms.
2. Define rig/sample/session contracts, adapt the AV2 preset and extract pure transformations plus CARLA sensor setup while preserving baseline behavior. Keep old commands as temporary wrappers.
3. Complete one baseline path through the shared session, capture, writer and validator. Check offline contracts and outputs; perform a short GPU pilot before accepting live equivalence.
4. Introduce one real alternative rig. Acceptance: the same recorder handles both presets and derives expected streams from the saved rig.
5. Move parked-vehicle and animal behavior into scene components using the common loop; extract provider adapters behind generation interfaces. Retire old implementations when replacements pass acceptance.

Each increment has a coherent diff, a stated behavior change, appropriate checks and a separate commit boundary. Package extraction, offline workflow tests and GPU integration checks have different acceptance scopes. Mock-based checks on Mac do not establish Linux/CARLA compatibility.

The final workflow should expose one documented run/status/validate/export path, bounded routine output and file-based diagnostics. Its registry must remain consistent through imports, failed verification, interruption and VM recovery. A fresh VM restores tracked inputs and declared assets, then resumes from portable evidence without old images.

Module boundaries should be judged by these research workflows. Directory names, class counts and package size are secondary. Demonstrate one working path before generalizing further.
