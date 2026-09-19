# Using LLMs to Edit CARLA Scenes

**Working report. Status: Stages 1–2 are completed; the Stage-3 camera/recording implementation passed locally and awaits its required verified off-VM copy. Baseline recording, LLM, animal, and comparison experiments remain.**

Document start date: 16 September 2026. Target deadline: 21 September 2026 in the current context; the source PDF specifies only day and month, without a year. Author/executor: complete before submission.

Recording rule: distinguish planned methods from completed experiments. For every result, provide the run ID, commit, parameters, and artifact link. Never replace `not measured` with zero. Do not put keys, private endpoints, or full machine logs in this report.

## Summary and Current Status

The assignment requires controlling CARLA through Python, recording five routes using cameras placed as in Argoverse 2, and studying natural-language scene editing with several LLMs. Per the user’s clarification, changes are limited to CARLA runtime capabilities and models are called through APIs. The selected rig has nine positions and two sensor types per position, recorded at 2 Hz of simulation time. Ego-vehicle poses are stored separately.

The user reported a successful CARLA 0.9.16 offscreen test on the GPU VM. Stage 1 subsequently verified Town01 loading, basic World/Actor/Blueprint operations, rendered weather changes, and the exposed map/object catalogues. Base Town01 direct RoadLines hiding was semantic-only, but the installed `Town01_Opt` passed paired RGB/raw-semantic checks at a straight road, intersection, and traffic-control location using direct RoadLines hiding; sampled navigation remained available. Stage 2 constructed five connected approved routes, saved their geometry and DebugHelper views, then drove all five with a spawned Traffic Manager vehicle under explicit completion and safety checks. Stage 3 selected a real AV2 calibration and locally validated all 18 camera streams with same-frame ego poses at 2 Hz; its required independent copy is still unverified. All later research outcomes remain unconfirmed.

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
| Code / commit | Run began from `0e52c6a8ef7cb4bbb6116c6c40a72e772a7b6a1d`; reproducible stage-0 implementation was subsequently preserved at `ce26b8e`, now in private branch `Dev` after the branch rename |
| Verification run | `20260916T210617Z-carla-smoke-beb230`; verified Mac copy and manifest check at 2026-09-16 21:19 UTC |

### 1.2. Basic Use

Describe Client, World, Actor, Blueprint, and actor lifecycle using a genuinely completed minimal example. Attach a connection log and a reference RGB frame. State separately how synchronisation and shutdown were handled.

**Completed minimal smoke result:** an isolated client connected to the offscreen server, spawned temporary vehicle/camera actors, saved a readable 800×600 RGB PNG, and cleaned the actors up. The server and client reported 0.9.16. The run used CARLA's default `Town10HD_Opt`; it is only a connection/frame test and does not validate Town01, sensors beyond one RGB camera, or synchronous recording. The run manifest passed local verification and the user verified its Mac copy with `rsync` plus SHA-256 checks for all manifest files. The source location and external copy are registered in `artifacts/index.csv`.

**Stage-1 basic API result:** run `20260917T110520Z-map-api-676d` loaded Town01, created and destroyed a vehicle actor from the blueprint library, saved paired RGB/semantic captures, and changed weather parameters before verifying an RGB byte-level change. It used temporary synchronous settings (0.05 s) only for deterministic captures and restored settings afterwards. Client/server versions were both 0.9.16. This is a map/API probe, not a multi-camera recording result.

### 1.3. Loading Town01

Record the list of available maps, the actual name of the loaded map, and, if `Town01_Opt` is used, the rationale and its correspondence to Town01. Attach an overview image and launch metadata.

**Result:** artifact-confirmed in run `20260917T110520Z-map-api-676d`. `get_available_maps()` contained `Town01` and `Town01_Opt`; the required map was loaded as `Carla/Maps/Town01`. `Town01_Opt` was investigated separately as an optional map-layer candidate, not silently substituted for Town01. The 800×600 nadir captures cover a generated straight road, a generated junction, and a traffic-control location; `get_crosswalks()` returned no point, so there is no claim that a crosswalk was captured.

### 1.4. Removing Road Markings

The goal is to hide visual road markings while preserving the road and navigation topology. Stage 1 tested the installed runtime APIs using paired RGB/raw-semantic observations and visual review. The selected runtime method is direct RoadLines hiding on the explicitly recorded `Town01_Opt` map; its coverage is three observations rather than a map-wide assertion.

| Method under test | Map/version | RGB before/after | Semantic before/after | Side effects | Conclusion |
|---|---|---|---|---|---|
| `enable_environment_objects` for all RoadLines | Town01 / 0.9.16 | Yellow markings remained at straight road, intersection, traffic control | Class 24: 605→0, 512→0, 565→0 pixels | Topology stayed 160 edges; sampled driving waypoints remained available | Semantic-only; fails visible removal |
| `unload_map_layer(Decals)` | Town01_Opt / 0.9.16 | Yellow markings remained | Not a sufficient semantic removal check | Broad unrelated scene changes | Not targeted; fails |
| `enable_environment_objects` for RoadLines | Town01_Opt / 0.9.16 | Yellow markings disappeared at straight road, intersection, traffic-control location | Class 24: 604→0, 512→0, 550→0 pixels | 25 objects hidden; topology 160 edges; sampled driving waypoints remained available | Passes declared coverage; selected method |
| Diffuse `TextureColor` on all resolved RoadLines materials plus hiding | Town01 / 0.9.16 | Target and three coverage views retained yellow markings | Target: 402→402 with texture; combined capture class 24 = 0 | 259 calls returned without API error | No usable visual effect; fails |
| 64×64 all-channel `apply_textures_to_object` | Town01 / 0.9.16 | Target marking remained yellow | Class 24: 402→402 | Diffuse, emissive, normal, and AO/roughness/metallic/emissive texture calls accepted | No usable visual effect; fails |

Evidence: `20260917T110520Z-map-api-676d`, `20260917T111200Z-town01-opt-decals-5a62`, `20260917T145900Z-town01-texture-ead1`, `20260917T150510Z-town01-opt-direct-638d` (corrected review), `20260917T151600Z-town01-full-texture-1c2f`, and `20260917T153000Z-town01-opt-coverage-b6e3` (three-location confirmation). Each has matched PNGs, raw semantic counts, a visual review, and local manifest verification; none has an external copy yet. The successful observations cover samples only: the map returned no crosswalk API point, so no claim covers crosswalks/stop lines or every map marking. No performance effect was measured.

### 1.5. Waypoints and Five Routes

Describe discretisation resolution, route provenance, and visualisation of the complete waypoint sample. Each route must contain at least ten consecutive points. Disable debug drawings before dataset recording.

| Route | Adaptive waypoint count | Length, m | Start/finish | Provenance | File/run |
|---|---|---|---|---|---|
| `route_01_straight` | 23 | 220.061 | (92.405, 227.220) → (92.367, 7.159) | Approved adaptive subset; 111-point connected 2 m reference | `routes/route_01_straight.json`, run `20260919T154916Z-route-numbering-swap-b5e941` |
| `route_02_left` | 44 | 253.109 | (130.365, -2.047) → (-2.041, 123.409) | Approved adaptive subset; 126-point connected 2 m reference | `routes/route_02_left.json`, same run |
| `route_03_right` | 45 | 246.838 | (334.773, 210.670) → (200.928, 326.600) | Approved adaptive subset; 126-point connected 2 m reference | `routes/route_03_right.json`, same run |
| `route_04_bridge_then_turn` | 101 | 495.316 | (301.340, 330.610) → (334.889, 18.076) | Approved adaptive subset; 244-point connected 2 m reference | `routes/route_04_bridge_then_turn.json`, same run |
| `route_05_four_turns` | 119 | 508.150 | (396.368, 19.923) → (88.399, 192.263) | Approved adaptive subset; 252-point connected 2 m reference | `routes/route_05_four_turns.json`, same run |

**Superseded initial route-selection result:** after reapplying RoadLines hiding to 25 objects, the probe sampled all 3,266 values returned by `Map.generate_waypoints(2.0)`. A fixed selection seed (`20260917`) chose distinct native spawn anchors. Each of the 295 transitions was rechecked by confirming that the stored successor appeared in the predecessor's `next(2.0)` response. The run retains the full network sample, a route index, five complete route files, a clean map overview, and one temporary line-only DebugHelper overview per route. A controlled RGB comparison found that `draw_point`, not the map or RoadLines operation, had caused black texture occluders in the earlier preview; all waypoint points are now cleared before camera capture. This establishes only map-graph connectivity and visual route inspection; the run used no ego actor or Traffic Manager. Client/server version was 0.9.16; it began at `096d990` with the rendering correction uncommitted, which is recorded in its metadata.

**Approved replacement set:** the user approved all five geometries on 2026-09-19, then requested that route numbers reflect complexity. Immutable run `20260919T154916Z-route-numbering-swap-b5e941` keeps every geometry unchanged but makes the bridge crossing route 4 and the four-turn route 5. Adaptive counts are 23, 44, 45, 101, and 119; every corresponding dense 2 m edge passed direct-successor validation. This table supersedes the original five 60-point routes for subsequent implementation.

### 1.6. Traffic Manager Autopilot

Describe vehicle spawning, path assignment, TM settings, completion criterion, timeout, and stuck-vehicle handling. Attach actual trajectories for five drives and deviations from routes.

**Result:** completed on `Carla/Maps/Town01_Opt` in run `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`. One Tesla Model 3 was spawned at each stored route start after RoadLines hiding was reapplied; world and Traffic Manager used a 0.05 s synchronous step. The initial adaptive and dense `set_path` trials were accepted but departed route 1 after 94 m at a later branch, so both are retained as incomplete diagnostics. The final method submitted derived `set_route` junction instructions (`Left`/`Right`/`Straight`) and projected every sampled vehicle pose onto the preserved 2 m reference chain.

| Route | Outcome | Finish distance, m | Maximum deviation, m | Collisions |
|---|---:|---:|---:|---:|
| `route_01_straight` | Completed | 7.885 | 0.997 | 0 |
| `route_02_left` | Completed | 7.199 | 1.204 | 0 |
| `route_03_right` | Completed | 7.935 | 0.999 | 0 |
| `route_04_bridge_then_turn` | Completed | 7.706 | 1.232 | 0 |
| `route_05_four_turns` | Completed | 7.923 | 1.247 | 0 |

The criterion was finish distance ≤8 m plus ≥95% reference progress; each route also passed timeout, stuck, deviation (≤15 m), and post-finish-stop checks. This is a CARLA Traffic Manager navigation test, not an evaluation of learned visual perception. No cameras or dataset frames were recorded in this stage.

### 1.7. Camera and Transform Recording at 2 Hz

The implemented recorder uses a synchronous 0.05 s world step and Traffic Manager, with all cameras set to a 0.5 s sensor period. Callbacks are grouped by CARLA frame ID and accepted only when every expected sensor is present and the timestamp matches the ego `ActorSnapshot` from that frame's `WorldSnapshot`. Complete warm-up frames are discarded explicitly. GPU callback delay therefore cannot pair an image with a later `vehicle.get_transform()` call. A partial transform document is updated after each accepted sample; final `transforms.json` is written only after the requested capture completes.

RGB is saved losslessly as PNG. The semantic camera's raw R-channel class ID is written unchanged to an 8-bit grayscale PNG, while a separate CityScapes-palette PNG is a human-readable preview. The validator checks JSON, unique frames, timing, camera sets, file paths, PNG signatures/chunk CRCs/decompression, dimensions, raw encoding, and ego-body pixels. It also creates contact sheets for visual review.

| Check | Measurement | Artifact |
|---|---|---|
| Simulation-timestamp interval | 0.5000000 s within 0.0001 s tolerance; four samples | `20260919T162408Z-av2-all-cameras-short-247e3f/validation.json` |
| Completeness of 18 frames per timestamp | 4/4 complete; 72 required RGB/raw-ID images | Same validation |
| Ego-pose/frame alignment | All sensor timestamps equal the same-frame snapshot timestamp | Same validation |
| Drops/duplicates | 0 missing, 0 duplicate keys, 0 late events after stop | `capture_summary.json` |
| JSON/images are readable | `transforms.json` parsed; all 108 PNGs including previews decoded and CRC-checked | Same validation |

### 1.8. Argoverse 2 Cameras

Nine viewpoints: `ring_front_center`, `ring_front_left`, `ring_front_right`, `ring_side_left`, `ring_side_right`, `ring_rear_left`, `ring_rear_right`, `stereo_front_left`, and `stereo_front_right`. Each gets RGB and semantic sensors, for 18 synthetic sensors. [AV2 sensors and calibration guide](https://argoverse.github.io/user-guide/datasets/sensor.html).

| Item | Actual selection |
|---|---|
| AV2 log ID / calibration source | Sensor log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca`; official public S3 Feather files with preserved SHA-256 |
| CARLA vehicle | `vehicle.tesla.model3` |
| Ego-origin transform | AV2 rear-axle centre aligned to the CARLA rear-wheel midpoint after the first synchronous tick; AV2 y-left converted to CARLA y-right |
| Extrinsics for nine cameras | Quaternion rotations converted through explicit ego/optical bases; uniform `+0.5 m` local-z clearance adaptation declared |
| Intrinsics / FOV / resolutions | AV2 width/height and horizontal FOV from `fx`; front-centre 1550×2048, other eight 2048×1550 |
| Verification of all views | Numerical rotation/body checks plus RGB and semantic contact-sheet review passed |

CARLA 0.9.16 cannot set the small AV2 principal-point offsets or reproduce the full `k1/k2/k3` model, so distortion was disabled and exact optical equivalence is not claimed. Exact rear-axle placement exposed the Tesla hood; a retained failed pilot demonstrates this, and the declared 0.5 m height adaptation removes the body from every validated view. Raw source, applied transforms, numerical checks, and projection limits are in the run's `calibration.json`.

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
| Number of scenes / routes / weather conditions | One short Stage-3 rig check on the beginning of route 1; baseline matrix not yet run |
| Number of complete and failed drives | One complete 18-sensor short check; three retained calibration/body diagnostics and one successful one-view pilot |
| Total simulation time | Full-rig accepted span 1.500000022 s after warm-up |
| Image / pose-record count | 72 required images + 36 previews + 4 ego poses in the full-rig check |
| Data volume | 165,463,137 bytes including validation, contact sheets, metadata, and manifest |
| Validator / version | `scripts/stage3_validate_dataset.py`; all checks passed |
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
