# Using LLMs to Edit CARLA Scenes

**Working report. Status: the structure is prepared; project experiments have not been completed.**

Document start date: 16 September 2026. Target deadline: 21 September 2026 in the current context; the source PDF specifies only day and month, without a year. Author/executor: complete before submission.

Recording rule: distinguish planned methods from completed experiments. For every result, provide the run ID, commit, parameters, and artifact link. Never replace `not measured` with zero. Do not put keys, private endpoints, or full machine logs in this report.

## Summary and Current Status

The assignment requires controlling CARLA through Python, recording five routes using cameras placed as in Argoverse 2, and studying natural-language scene editing with several LLMs. Per the user’s clarification, changes are limited to CARLA runtime capabilities and models are called through APIs. The selected rig has nine positions and two sensor types per position, recorded at 2 Hz of simulation time. Ego-vehicle poses are stored separately.

The user reported a successful CARLA 0.9.16 offscreen test on the GPU VM. Stage 1 subsequently verified Town01 loading, basic World/Actor/Blueprint operations, rendered weather changes, and the exposed map/object catalogues. However, no permitted runtime operation tested so far removes road markings from both RGB and raw semantic observations; item 1.4 remains blocked. Full camera recording and all later research outcomes remain unconfirmed.

After experiments, replace this section with a short abstract of the actual results, data volume, and limitations.

## 1. CARLA Experiments

### 1.1. Version Choice and Installation

**Decision:** CARLA 0.9.16 in Docker. The official description of the packaged 0.10.0 release lists the absence of Town01 and limitations in needed functionality, so a UE4-branch release was selected. This is rationale for the choice, not a result of an independent test of 0.10.0. [CARLA 0.10.0 release](https://carla.org/2024/12/19/release-0.10.0/), [CARLA 0.9.16 release](https://carla.org/2025/09/16/release-0.9.16/).

**Environment reported by the user:** Massed Compute; Ubuntu 22.04.5 LTS; RTX A6000 48 GB; 6 vCPU; 96 GB RAM; 300 GB SSD. Docker 29.1.5, NVIDIA driver 580.126.09, and `nvidia-container-cli` 1.18.1. Complete this with actual logs and versions during implementation.

| Reproduction parameter | Actual value |
|---|---|
| Docker image digest | `carlasim/carla@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953` (stage-0 check) |
| Server/client version | Both `0.9.16` in run `20260916T210617Z-carla-smoke-beb230` |
| Python / pinned dependencies | Python 3.10.12; isolated `.venv`; `carla==0.9.16` |
| Launch command | `bash scripts/run_carla.sh` (same-VM smoke verified; see `docs/runbook.md`) |
| Code / commit | Run began from `0e52c6a8ef7cb4bbb6116c6c40a72e772a7b6a1d`; reproducible stage-0 implementation was subsequently preserved in private branch `00_-_stage` at `ce26b8e` |
| Verification run | `20260916T210617Z-carla-smoke-beb230`; verified Mac copy and manifest check at 2026-09-16 21:19 UTC |

### 1.2. Basic Use

Describe Client, World, Actor, Blueprint, and actor lifecycle using a genuinely completed minimal example. Attach a connection log and a reference RGB frame. State separately how synchronisation and shutdown were handled.

**Completed minimal smoke result:** an isolated client connected to the offscreen server, spawned temporary vehicle/camera actors, saved a readable 800×600 RGB PNG, and cleaned the actors up. The server and client reported 0.9.16. The run used CARLA's default `Town10HD_Opt`; it is only a connection/frame test and does not validate Town01, sensors beyond one RGB camera, or synchronous recording. The run manifest passed local verification and the user verified its Mac copy with `rsync` plus SHA-256 checks for all manifest files. The source location and external copy are registered in `artifacts/index.csv`.

**Stage-1 basic API result:** run `20260917T110520Z-map-api-676d` loaded Town01, created and destroyed a vehicle actor from the blueprint library, saved paired RGB/semantic captures, and changed weather parameters before verifying an RGB byte-level change. It used temporary synchronous settings (0.05 s) only for deterministic captures and restored settings afterwards. Client/server versions were both 0.9.16. This is a map/API probe, not a multi-camera recording result.

### 1.3. Loading Town01

Record the list of available maps, the actual name of the loaded map, and, if `Town01_Opt` is used, the rationale and its correspondence to Town01. Attach an overview image and launch metadata.

**Result:** artifact-confirmed in run `20260917T110520Z-map-api-676d`. `get_available_maps()` contained `Town01` and `Town01_Opt`; the required map was loaded as `Carla/Maps/Town01`. `Town01_Opt` was investigated separately as an optional map-layer candidate, not silently substituted for Town01. The 800×600 nadir captures cover a generated straight road, a generated junction, and a traffic-control location; `get_crosswalks()` returned no point, so there is no claim that a crosswalk was captured.

### 1.4. Removing Road Markings

The goal is to hide visual road markings while preserving the road and navigation topology. Stage 1 tested the installed runtime APIs using paired RGB/raw-semantic observations and visual review. No tested method is sufficient; the requirement remains blocked.

| Method under test | Map/version | RGB before/after | Semantic before/after | Side effects | Conclusion |
|---|---|---|---|---|---|
| `enable_environment_objects` for all RoadLines | Town01 / 0.9.16 | Yellow markings remained at straight road, intersection, traffic control | Class 24: 605→0, 512→0, 565→0 pixels | Topology stayed 160 edges; sampled driving waypoints remained available | Semantic-only; fails visible removal |
| `unload_map_layer(Decals)` | Town01_Opt / 0.9.16 | Yellow markings remained | Not a sufficient semantic removal check | Broad unrelated scene changes | Not targeted; fails |
| `enable_environment_objects` for RoadLines | Town01_Opt / 0.9.16 | Yellow markings remained | Class 24: 604→0 pixels | Topology stayed 160 edges | Semantic-only; fails |
| Diffuse `TextureColor` on all resolved RoadLines materials plus hiding | Town01 / 0.9.16 | Target and three coverage views retained yellow markings | Target: 402→402 with texture; combined capture class 24 = 0 | 259 calls returned without API error | No usable visual effect; fails |
| 64×64 all-channel `apply_textures_to_object` | Town01 / 0.9.16 | Target marking remained yellow | Class 24: 402→402 | Diffuse, emissive, normal, and AO/roughness/metallic/emissive texture calls accepted | No usable visual effect; fails |

Evidence: `20260917T110520Z-map-api-676d`, `20260917T111200Z-town01-opt-decals-5a62`, `20260917T145900Z-town01-texture-ead1`, `20260917T150510Z-town01-opt-direct-638d`, and `20260917T151600Z-town01-full-texture-1c2f`. Each has matched PNGs, raw semantic counts, a visual review, and local manifest verification; none has an external copy yet. These observations cover samples only, but a visible remaining marking is already enough to reject a claim of complete removal. No performance effect was measured.

### 1.5. Waypoints and Five Routes

Describe discretisation resolution, route provenance, and visualisation of the complete waypoint sample. Each route must contain at least ten consecutive points. Disable debug drawings before dataset recording.

| Route | Waypoint count | Length, m | Start/finish | Provenance | File/commit |
|---|---|---|---|---|---|
| Not selected yet | Not measured | Not measured | — | — | — |

### 1.6. Traffic Manager Autopilot

Describe vehicle spawning, path assignment, TM settings, completion criterion, timeout, and stuck-vehicle handling. Attach actual trajectories for five drives and deviations from routes.

**Result:** not completed. Interpretation clarification: TM uses simulator state; this experiment alone does not evaluate the learned visual perception of an autonomous-driving system.

### 1.7. Camera and Transform Recording at 2 Hz

Plan: synchronous simulation, cameras with a 0.5 s period, and frame-ID matching to the ego pose from the same snapshot. Both simulation and wall-clock time are recorded separately. A complete `transforms.json` is written at the end of a drive.

Describe the actual world step, phase/warm-up, semantic-ID encoding, handling of camera delay, capture window, omissions, and recovery after interruption.

| Check | Measurement | Artifact |
|---|---|---|
| Simulation-timestamp interval | Not measured | — |
| Completeness of 18 frames per timestamp | Not measured | — |
| Ego-pose/frame alignment | Not checked | — |
| Drops/duplicates | Not measured | — |
| JSON/images are readable | Not checked | — |

### 1.8. Argoverse 2 Cameras

Nine viewpoints: `ring_front_center`, `ring_front_left`, `ring_front_right`, `ring_side_left`, `ring_side_right`, `ring_rear_left`, `ring_rear_right`, `stereo_front_left`, and `stereo_front_right`. Each gets RGB and semantic sensors, for 18 synthetic sensors. [AV2 sensors and calibration guide](https://argoverse.github.io/user-guide/datasets/sensor.html).

| Item | Actual selection |
|---|---|
| AV2 log ID / calibration source | Not selected |
| CARLA vehicle | Not selected |
| Ego-origin transform | Not calculated |
| Extrinsics for nine cameras | Not applied |
| Intrinsics / FOV / resolutions | Not configured |
| Verification of all views | Not completed |

After implementation, attach the source and applied calibration, axis/unit definition, rotation conversion, numerical checks, and a contact sheet of all nine views. List optical-model differences if exact equivalence cannot be achieved.

### 1.9. Baseline Drives and Weather

Record the route × weather × repeat matrix, seeds, and actual weather settings. Cover all five routes. The number of conditions is decided after a pilot recording; a proposal of two weather modes per route is not yet an experiment.

Explain the limits of seasonality: changing rain, clouds, and sun is not a full seasonal change. State the measured number of drives, duration, size, recording speed, resource usage, and validator result.

**Result:** dataset not created.

## 2. Review of Publications and Repositories

**Status:** the research review has not yet been completed. The initial technical links in `docs/knowledge.md` do not replace a method review.

| Paper/repository | Year/version | LLM role | What changes | CARLA/code | Limitations | Applicability |
|---|---|---|---|---|---|---|
| Complete from primary sources | — | — | — | — | — | — |

Compare runtime scenarios, geometry editing, and image post-processing. For nearby but non-identical tasks, state the distinction explicitly. The section’s conclusion should justify the project architecture.

## 3. Natural-Language Scene Editing

### 3.1. Proposed Architecture

The user request and description of available capabilities are sent to an LLM API. The model returns a structured scene description. A validator checks syntax, parameters, and action feasibility; an executor then applies permitted CARLA operations. A saved configuration can replay the scene without another model call.

This is a project design. Concrete components, SceneSpec version, refusal handling, and scene reset are recorded after implementation. Arbitrary code from a model response is never executed.

### 3.2. Comparison Protocol

| Parameter | Fixed selection |
|---|---|
| Model A / provider / ID | Target: GPT-Astra; access not verified |
| Model B / provider / ID | Target: Qwen around 27B; access not verified |
| Model C / provider / ID | Target: Qwen around 8B; access not verified |
| API versions / regions | Not selected |
| Prompt set / schema | Not written |
| Repeats / retries / timeout | Not selected |
| Metrics | Schema validity, execution, fulfilment, latency, errors; usage/cost where available |

Use equivalent scene context and tasks for all variants. Record the raw response, parsed specification, validation result, executor result, complete response latency, and model/provider settings. Separate first-attempt success from success after retries. Do not substitute a manually corrected successful scene for the actual model outcome.

### 3.3. Results Table

| Model | Task/prompt ID | Attempts | Schema-valid | Executed | Request fulfilled | End-to-end latency | API latency | CARLA time | Artifact |
|---|---|---:|---|---|---|---:|---:|---:|---|
| Not run | — | — | — | — | — | — | — | — | — |

**Early capability result:** Town01's exposed blueprint catalogue contained 214 entries (41 vehicle, 52 walker, 19 sensor) and no name matching the project animal-candidate pattern. This does not prove that no compatible prebuilt animal package exists; mesh/asset spawning, visibility, motion, collision, and Traffic Manager response remain untested. Evidence: `20260917T110520Z-map-api-676d`.

## 4. Adding a Moving Animal

The edited scene must contain an actual animal, visible on the cameras, whose presence affects the scene. First establish whether the selected CARLA package has a usable animal asset. The simplest acceptable solution may have kinematic movement without leg animation, but asset, visibility, movement, semantics, collision/response, and impact on the ego vehicle must each be checked separately. If Traffic Manager does not brake for a prop, report that fact; do not infer a reaction from a single frame.

Use the same request set for the animal’s appearance and motion across LLMs. Store its parameters and trajectory separately from the ego JSON. Add confirming frames/video and measurements.

**Results and conclusions:** unavailable until experiments are conducted.

## 5. Repeated Drives on Edited Scenes

Define scene versions that cover the outcomes of sections 3 and 4. Recheck waypoints and the applicability of the same five routes, then record the same weather conditions and camera rig.

| Scene version | LLM provenance/attempt | Routes/weather | Drive success | Data validated | Link |
|---|---|---|---|---|---|
| Not created yet | — | — | Not measured | No | — |

Compare completion time, collisions, animal visibility, data completeness, and agreement of edits with requests. Preserve failed drives. Separate the count of LLM attempts from the count of replayed drives. Do not attribute changes caused by another seed, weather, or control setting to visual editing.

## 6. Dataset and Reproducibility

After implementation, describe the actual format, JSON schema, frame/timestamp convention, coordinate units, calibrations, semantic IDs, and real launch commands. Documentation must not retain commands for scripts that do not exist.

| Metric | Actual value |
|---|---|
| Number of scenes / routes / weather conditions | Not measured |
| Number of complete and failed drives | Not measured |
| Total simulation time | Not measured |
| Image / pose-record count | Not measured |
| Data volume | Not measured |
| Validator / version | Not implemented |
| Verified external copy | Not confirmed |

State the Git commit/tag, image digest, pinned dependencies, configurations, and seeds. Data and code must be usable without the current VM. Include checksum manifests in the submission.

## 7. Limitations and Conclusions

There are no final conclusions before experiments are complete. Later, explicitly discuss:

- runtime-editing limits and marking removal;
- animal availability, movement realism, semantics, and TM response;
- differences between the camera model and AV2;
- completeness of seasonal simulation;
- effects of provider/network/reasoning settings on LLM latency;
- sample size, repeatability, and failed attempts;
- reproducibility on a new VM.

## 8. Submission Materials

| Material | Link | Access verified |
|---|---|---|
| Public Git repository | Not published | No |
| Report on Google Drive | Not published | No |
| Dataset on Google Drive | Not published | No |
| Manifests/instructions | Not published | No |

Publication occurs only after explicit instruction. Before publishing, check secrets, personal information, and rights to third-party materials.

## Appendices and Sources

The primary assignment document is retained in the local package; requirements are captured in `docs/requirements.md`. The technical-source index is `docs/knowledge.md`; research sources must be added after stage 5. Screenshots and tables must point to a concrete run ID and immutable configuration.
