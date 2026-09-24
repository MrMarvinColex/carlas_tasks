# Using LLMs to Edit CARLA Scenes

**Working report. Status: Stages 1–4 are completed. The Stage-3 rig passed local validation and has a user-confirmed off-VM copy; the Stage-4 baseline matrix has user-reported checksum-verified Mac copies. LLM, animal, and comparison experiments remain.**

Document start date: 16 September 2026. Target deadline: 21 September 2026 in the current context; the source PDF specifies only day and month, without a year. Author/executor: complete before submission.

Recording rule: distinguish planned methods from completed experiments. For every result, provide the run ID, commit, parameters, and artifact link. Never replace `not measured` with zero. Do not put keys, private endpoints, or full machine logs in this report.

## Summary and Current Status

The assignment requires controlling CARLA through Python, recording five routes using cameras placed as in Argoverse 2, and studying natural-language scene editing with several LLMs. Per the user’s clarification, changes are limited to CARLA runtime capabilities and models are called through APIs. The selected rig has nine positions and two sensor types per position, recorded at 2 Hz of simulation time. Ego-vehicle poses are stored separately.

The user reported a successful CARLA 0.9.16 offscreen test on the GPU VM. Stage 1 subsequently verified Town01 loading, basic World/Actor/Blueprint operations, rendered weather changes, and the exposed map/object catalogues. Base Town01 direct RoadLines hiding was semantic-only, but the installed `Town01_Opt` passed paired RGB/raw-semantic checks at a straight road, intersection, and traffic-control location using direct RoadLines hiding; sampled navigation remained available. Stage 2 constructed five connected approved routes, saved their geometry and DebugHelper views, then drove all five with a spawned Traffic Manager vehicle under explicit completion and safety checks. Stage 3 selected a real AV2 calibration and locally validated all 18 camera streams with same-frame ego poses at 2 Hz. The user confirmed an off-VM copy of the completed rig run exists; its external checksum output was not supplied in this session. All later research outcomes remain unconfirmed.

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

**Replacement-VM check (2026-09-23):** the pinned Python client and exact image digest were reinstalled on a newly rented VM. A temporary offscreen smoke run `20260923T113354Z-new-vm-recovery-3f3dcb` returned one 800×600 RGB frame with client/server 0.9.16, and its three manifest entries passed local hash verification. The frame was not visually reviewed, and previous experiments have not yet been verified after transfer from the Mac. This is environment recovery evidence only, not a new Town01 or 18-camera result. See `docs/environment.md` and `docs/worklog.md`.

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
| `route_01_straight` | 12 | 110.000 | (92.396, 171.220) → (92.379, 61.220) | Middle-half crop; 56-point connected 2 m reference | `routes/route_01_straight.json`, run `20260923T160431Z-shorter-routes-b72a9d` |
| `route_02_left` | 32 | 125.106 | (66.364, -2.038) → (-2.049, 59.407) | Middle-half crop retaining one left turn; 62-point reference | `routes/route_02_left.json`, same run |
| `route_03_right` | 32 | 122.838 | (334.735, 272.670) → (262.928, 326.607) | Middle-half crop retaining one right turn; 64-point reference | `routes/route_03_right.json`, same run |
| `route_04_turn_then_bridge` | 44 | 251.108 | (369.340, 330.610) → (396.291, 101.661) | One left turn then complete original bridge crossing; 125-point reference | `routes/route_04_turn_then_bridge.json`, same run |
| `route_05_two_turns` | 60 | 225.939 | (372.484, -1.986) → (270.760, 129.491) | Original middle left/right pair; 114-point reference | `routes/route_05_two_turns.json`, same run |

**Superseded initial route-selection result:** after reapplying RoadLines hiding to 25 objects, the probe sampled all 3,266 values returned by `Map.generate_waypoints(2.0)`. A fixed selection seed (`20260917`) chose distinct native spawn anchors. Each of the 295 transitions was rechecked by confirming that the stored successor appeared in the predecessor's `next(2.0)` response. The run retains the full network sample, a route index, five complete route files, a clean map overview, and one temporary line-only DebugHelper overview per route. A controlled RGB comparison found that `draw_point`, not the map or RoadLines operation, had caused black texture occluders in the earlier preview; all waypoint points are now cleared before camera capture. This establishes only map-graph connectivity and visual route inspection; the run used no ego actor or Traffic Manager. Client/server version was 0.9.16; it began at `096d990` with the rendering correction uncommitted, which is recorded in its metadata.

**Current shortened set:** on 2026-09-23 the user requested reduced driving time and recording volume. The table shows contiguous crops of the previously approved, signed `20260919T154916Z-route-numbering-swap-b5e941` set. Original dense coordinates/identities are unchanged and 10/2 m adaptive spacing is preserved. All 416 retained dense edges passed CARLA direct-successor checks; all five new starts and drives passed. Earlier versions remain immutable historical evidence. The new bridge route turns before crossing; the fifth route retains two turns, so their descriptive IDs changed accordingly.

### 1.6. Traffic Manager Autopilot

Describe vehicle spawning, path assignment, TM settings, completion criterion, timeout, and stuck-vehicle handling. Attach actual trajectories for five drives and deviations from routes.

**Current result:** all five shorter routes passed in `20260923T160409Z-shorter-routes-autopilot-b8548d`. The same Tesla/controller, fixed 0.05 s step and TM seed as the historical comparison were used, without cameras. Maximum deviations were 0.996–1.246 m; collisions were zero; all post-finish stops passed. Every retained turn was traversed and the complete bridge exit was reached before braking.

| Route | Old driving simulation time, s | Shortened driving simulation time, s |
|---|---:|---:|
| 1, straight | 30.35 | 16.05 |
| 2, left | 23.65 | 12.70 |
| 3, right | 28.10 | 15.35 |
| 4, bridge | 41.45 | 14.90 |
| 5, two turns | 63.15 | 29.85 |
| Total | 186.70 | 88.85 |

These times run from the initial vehicle snapshot to route completion, excluding the subsequent 3 s braking and 1 s stopped observation. The 52.41% time reduction supports an expected reduction in 2 Hz image volume; new recorded image sizes and recorder wall times remain unmeasured. Evidence: `duration_comparison.json` in the current drive run.

**Historical longer-route result:** completed on `Carla/Maps/Town01_Opt` in run `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`. One Tesla Model 3 was spawned at each stored route start after RoadLines hiding was reapplied; world and Traffic Manager used a 0.05 s synchronous step. The initial adaptive and dense `set_path` trials were accepted but departed route 1 after 94 m at a later branch, so both are retained as incomplete diagnostics. The final method submitted derived `set_route` junction instructions (`Left`/`Right`/`Straight`) and projected every sampled vehicle pose onto the preserved 2 m reference chain.

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

**Completed Stage-4 matrix:** the fixed matrix is five shortened routes × `clear_day`/`wet_cloudy_day` × one repeat. All ten cells completed with zero collision, stopped ego vehicle, maximum route deviation 1.246 m (limit 15 m), and passed the drive, dataset, timing, raw-semantic, PNG-integrity and ego-body checks. Contact sheets were generated for every cell; representative clear and wet RGB/semantic sheets were visually reviewed.

| Route | Clear-day samples | Wet-cloudy-day samples | Accepted simulation span, s |
|---|---:|---:|---:|
| `route_01_straight` | 31 | 30 | 15.0 / 14.5 |
| `route_02_left` | 24 | 24 | 11.5 / 11.5 |
| `route_03_right` | 29 | 29 | 14.0 / 14.0 |
| `route_04_turn_then_bridge` | 28 | 28 | 13.5 / 13.5 |
| `route_05_two_turns` | 58 | 58 | 28.5 / 28.5 |

The accepted dataset has 339 aligned 2 Hz poses, 3,051 RGB, 3,051 raw 8-bit semantic-ID and 3,051 CityScapes-palette PNGs (9,153 PNGs total). It spans 164.500 s of accepted simulation time. Recording consumed 1,076.278 wall seconds, including 24.292 s explicit bounded-writer backpressure. The final ten run directories occupy 12,904,099,739 bytes; their 9,303 manifest entries were rechecked locally. An earlier user-stopped long-route pilot and one batch-interrupted partial retry remain retained as incomplete artifacts, rather than being counted as matrix cells.

The user ran checksum-mode `rsync -nrc --itemize-changes` for both `runs/` and `logs/` from the VM to `/Users/madness/Science/CARLA/runs_1/` and `logs_1/` on the Mac. Both commands had no difference output. This is user-reported terminal evidence that the external copies match the VM source byte-for-byte; it satisfies the preservation requirement while remaining distinct from an agent-operated Mac-side check.

**Route-source update (2026-09-23):** the matrix now selects the shorter, drive-validated revision above, with `route_05_two_turns` as its pilot. The 120 s benchmark used the historical long-route source and remains a throughput measurement. A full camera recording on the shorter routes is the next experiment.

## 2. Review of Publications and Repositories

**Status:** completed on 24 September 2026 from the primary publications and author repositories below. The source code was inspected but not executed; reported metrics remain author-reported rather than independently reproduced.

| Work | Method and LLM role | CARLA/code | Main evidence and limitation | Use in this project |
|---|---|---|---|---|
| [ScenarioGen](https://cse.buffalo.edu/tech-reports/2026-22.pdf) / [repository](https://github.com/harshit88a/scenario-gen) | Text is converted to a constrained JSON scenario, structurally validated, and passed to a fixed CARLA runner. | CARLA 0.9.15; author code; repository licence not confirmed. | The report gives three qualitative CARLA examples and reports over 90% first-attempt structural validity on about 50 prompts. This does not measure geometric correctness or repeatability. | Closest architectural analogue for separating the LLM, data specification, validator, and executor. Its local fine-tuned model is outside this project's API-only constraint. |
| [TTSG](https://arxiv.org/abs/2409.09575) / [repository](https://github.com/basiclab/TTSG) | Multiple LLM steps extract actors and road constraints, rank existing road segments, and produce an actor plan for runtime execution. | Tested with CARLA 0.9.15; author code; licence status not confirmed from a licence file. | On ten prompts, the authors report scene accuracy increasing from 0.560 to 0.800 with road ranking. The implementation selects its own map/road and uses `eval()` on model output before validation. | Supplies the useful idea of grounding spatial requests against map geometry. This project must restrict grounding to five existing `Town01_Opt` routes and parse data safely. |
| [TrafficComposer](https://arxiv.org/abs/2505.14881) / [repository](https://github.com/TrafficComposer/TrafficComposer) | Text and a reference image are converted into a traffic intermediate representation (IR); the LLM handles the textual part. | CARLA and LGSVL are evaluation targets; the repository exposes the IR pipeline, but not a complete reproducible CARLA conversion path; licence not confirmed. | The reported 97.0 ± 1.2% result is similarity to manually annotated IR, not successful CARLA scene execution. The visual pipeline adds models and an input not required here. | Supports using an explicit intermediate representation. A reference image is optional research context rather than a required Stage-6 input. |
| [ChatScene](https://openaccess.thecvf.com/content/CVPR2024/papers/Zhang_ChatScene_Knowledge-Enabled_Safety-Critical_Scenario_Generation_for_Autonomous_Vehicles_CVPR_2024_paper.pdf) / [repository](https://github.com/javyduck/ChatScene) | An LLM and a knowledge base assemble Scenic programs; SafeBench/Scenic samples and optimizes runtime CARLA scenarios on fixed routes. | Repository instructions use CARLA 0.9.13 and include an MIT licence file. | The reported collision rate evaluates selected safety-critical scenes, not fidelity to arbitrary text. The repository documents manual changes to generated Scenic files. | Motivates reusable, route-aware scenario primitives, but generated executable Scenic code does not satisfy the project's restricted-executor boundary. |

All four selected works change actors, weather, placement, or behaviour in a running simulator using existing maps and assets. Methods that author new Unreal geometry and methods that alter only rendered pixels address different tasks: neither establishes a reproducible physical scene under the CARLA Python API. None of the four is a drop-in solution for CARLA 0.9.16, `Town01_Opt`, the fixed five routes, or the validated 18-sensor rig.

The review therefore supports a deliberately small architecture for this test assignment. An API model returns a versioned `SceneSpec` containing only supported objects, spatial anchors, parameters, and actions. A deterministic validator checks schema, numeric ranges, blueprint availability, route/map compatibility, and spatial feasibility. A fixed executor maps accepted fields to previously tested CARLA calls, and post-application checks verify the actual actors, positions, visibility, and requested event. The request, raw response, parsed specification, resolved transforms/blueprints, seeds, outcome, and timing are saved so the accepted scene can be replayed without another model call.

ScenarioGen provides the clearest separation of specification from execution; TTSG contributes geometry-aware grounding; TrafficComposer supports an explicit IR; and ChatScene demonstrates reusable scenario primitives on fixed routes. The project adopts these principles without copying their local-model, unsafe parsing, multimodal, or executable-DSL components. None of the reviewed systems creates a missing animal asset, so that remains a separate Stage-7 dependency.

## 3. Natural-Language Scene Editing

### 3.1. Proposed Architecture

The user request and description of available capabilities are sent to an LLM API. The model returns a structured scene description. A validator checks syntax, parameters, and action feasibility; an executor then applies permitted CARLA operations. A saved configuration can replay the scene without another model call.

**Pre-API implementation result (24 September 2026):** `SceneSpec` v1.0 is implemented as strict passive JSON in `scripts/stage6_scene_spec.py`; the executor is `scripts/stage6_local_scene.py`. The initial protocol is intentionally narrow: `Town01_Opt`, the straight control route `route_01_straight`, `clear_day`/`wet_cloudy_day`, and one to three parked `vehicle.audi.a2` actors. The ego stays a Tesla Model 3. A specification contains only map/route/weather IDs, a seed, an allow-listed operation, blueprint ID and a route-progress anchor with side/offsets; it has no Python, Scenic or world-coordinate field. Duplicate keys, non-finite numbers, unsupported fields and malformed types are rejected. A separate `unsupported_capability` response records an impossible moving-animal request without pretending that an executor failure is a model success.

The executor creates a clean world for every attempt, reapplies direct RoadLines hiding, checks the current map/route and blueprint library, calculates actual transforms, requires CARLA spawn feasibility, applies weather, saves before/after observer views, records three aligned 2 Hz samples from all 18 cameras, checks semantic-supported object visibility, then completes the simple 110 m Traffic Manager route. Arbitrary code from a model response is never executed. A saved `scene_spec.json` replays through this same path without an API call.

`20260924T110210Z-local-straight-parked-vehicle-observer-fix-213a80` created one Audi in `wet_cloudy_day`; its three camera samples (81 PNGs) passed the existing validation and the route completed without collision (maximum deviation 0.999 m). Its fresh-world replay `20260924T110353Z-local-straight-replay-ad721d` reproduced the SceneSpec, blueprint and actual transform exactly, with the same visibility and route result. `20260924T110725Z-local-straight-composite-safe-af8031` repeated the check for two Audis in `clear_day`. These are local CARLA checks, not LLM experiments. The retained failed placements show why live feasibility validation is necessary: a right-side target remained on a driving lane and another left-side target intersected static map geometry.

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

The API adapter and this table remain unfilled because no provider/model access or spending limit has been verified, and no model call was made. The pre-API fixtures and local executor are not attributed to GPT-Astra or Qwen.

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
| External copy | User-confirmed; external checksum output not supplied in this session |

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

The primary assignment document is retained in the local package; requirements are captured in `docs/requirements.md`. The technical-source index is `docs/knowledge.md`, including the Stage-5 primary publications and author repositories. Screenshots and experimental tables must point to a concrete run ID and immutable configuration.
