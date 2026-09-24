# Project Knowledge Base

This is a compact reference for the agent. Read only the sections relevant to the stage; it does not replace checking the installed image and recorded artifacts.

Evidence labels: **DOC** means documentation read during the original discussion; **HYPOTHESIS** is a candidate to test; **DECISION** is the selected approach; **EXPERIMENT** is a run result with an artifact link. At transfer time, no new project experiment is recorded here.

The sources below were found/read in the 15–16 September 2026 discussion. They were not re-browsed when this English package was prepared. `latest`, main/dev branches, and provider catalogues may change. During implementation, record version/commit and access date; do not turn unverified chat statements into report results.

## 1. CARLA Basics

The CARLA Server performs physics and rendering. A Python client sends commands and receives data. World is the current world, Actor is an object with a lifecycle, and Blueprint is an available actor template. A map combines environment geometry and an OpenDRIVE road definition. Traffic Manager controls registered vehicles from simulator state; it is not trained on the project’s RGB images.

Report implication: hiding visible road lines may change the dataset but need not affect Traffic Manager route following. This experiment does not evaluate a real vision-based autonomous-driving system. Likewise, visual weather changes do not automatically change tyre friction; validate every claimed physical effect. Sources: S03, S07, S08.

## 2. Version Choice and Documentation Trap

**DOC:** the CARLA 0.10.0 release description lists missing Towns 1–9, unsupported Map Layers API, constrained weather, and unported functionality. UE5 `latest` documentation describes `ue5-dev` and may show APIs absent from a packaged release. A Town01 example in a page does not prove its presence in the package. S01, S02.

**DECISION:** use `carlasim/carla:0.9.16`; the user reported that this image launches successfully. Check available maps and actual method effects in the installed image. In the report, attach 0.10.0 limitations to that verified release rather than claiming every UE5 build always has them.

## 3. Road Markings and Map Geometry

**DOC:** `World.get_environment_objects()` and `enable_environment_objects()` can control registered environment objects; map layers work for Opt maps. CARLA also exposes runtime texture replacement for supported objects. S03, S05, S06.

**HYPOTHESES for stage 1:**

1. Locate the road-line category in the actual API, obtain object IDs, and hide them. Verify that the list is non-empty and disappearance occurs in RGB and semantic frames.
2. On Town01_Opt, test `Decals` if some markings remain. It may contain unrelated decals; measure side effects.
3. Investigate runtime textures only if targeted hiding is insufficient. Asphalt-colour painting does not guarantee that RoadLine semantic class IDs disappear or that seams are invisible.

Do not alter OpenDRIVE to achieve a visual result. Save before/after frames from identical positions and weather. Check straight sections, intersections, crossings, and stop lines; several successful frames do not prove map-wide coverage. Report inspection method and all remaining objects.

If the method cannot meet the requirement, keep the item blocked. Do not present a code fragment suggested in chat as a tested implementation.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** Town01 exposes 259 `RoadLines` environment objects. Hiding them with `World.enable_environment_objects(ids, False)` reduced raw semantic class ID 24 to zero at a straight road (605→0 pixels), intersection (512→0), and traffic-control location (565→0), while visual inspection of the paired RGB files found yellow markings still present at all three locations. Topology remained 160 edges and the tested driving waypoints remained available. Run `20260917T110520Z-map-api-676d`.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** `Town01_Opt` exists. Unloading `MapLayer.Decals` left yellow markings visible and changed unrelated scene content (run `20260917T111200Z-town01-opt-decals-5a62`). An initial visual verdict on a one-location direct-RoadLines pair was erroneous; its corrected review confirms that the yellow markings disappeared when its 25 `RoadLines` objects were hidden (run `20260917T150510Z-town01-opt-direct-638d`). A separate three-location confirmation then showed RGB removal and raw class 24 counts of straight road 604→0, intersection 512→0, and traffic-control location 550→0. A sampled driving waypoint remained available at every location and topology was 160 edges (run `20260917T153000Z-town01-opt-coverage-b6e3`). This is the selected runtime method for `Carla/Maps/Town01_Opt`, with no claim of map-wide or crosswalk coverage.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** Texture API material targets use `Road_Marking_Town01_N`, while `EnvironmentObject.name` adds `_SM_0`. Resolving and applying a 2×2 neutral `TextureColor` through `MaterialParameter.Diffuse` succeeded without API errors for all 259 target names, but visual inspection found no usable change to a target marking or three coverage observations. Combining this call with RoadLines hiding still left markings visible in RGB. Run `20260917T145900Z-town01-texture-ead1`.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** A separate 64×64 `apply_textures_to_object` call set Diffuse, Emissive, Normal, and AO/Roughness/Metallic/Emissive textures on resolved material `Road_Marking_Town01_1`. The call succeeded, but the matched target RGB pair retained yellow segments and its RoadLines class count remained 402→402. This closes the tested all-material texture API variant; it does not imply that no future compatible packaged material solution exists. Run `20260917T151600Z-town01-full-texture-1c2f`.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** Town01's blueprint library contained 214 entries (41 `vehicle.*`, 52 `walker.*`, 19 `sensor.*`) and zero IDs matching `animal`, `dog`, `cat`, `deer`, `horse`, `cow`, `sheep`, `goat`, `pig`, `bird`, `bear`, `wolf`, or `fox` as name components. This is an exposed-catalogue result only; it does not establish absence of every compatible prebuilt extension. Run `20260917T110520Z-map-api-676d`.

## 4. Waypoints and Routes

**DOC:** a waypoint is an oriented point on a road lane, with transform and road identifiers. A continuous road is discretized at a declared resolution. Traffic Manager `set_path` receives a sequence of Locations, and `set_route` receives `Left`, `Right`, or `Straight` instructions; CARLA warns that road/lane topology must permit either request. S03, S07.

**DECISION:** preserve five connected routes and validate them by actual driving. GlobalRoutePlanner is a route-construction candidate; use the version compatible with installed PythonAPI. ScenarioRunner/Leaderboard routes may be used after validating their map and version. Do not install a full benchmark only to obtain a few coordinates unless needed. S11, S12.

Route criteria: at least 10 waypoints, usable start, connectivity, suitable direction, meaningful duration, and no infinite cycle. Metrics: distance travelled, proximity to finish, path following, timeout, and collisions. Traffic Manager may continue after the finish, so the experiment must define completion.

DebugHelper is for route-selection verification. Remove or expire debug markings before dataset recording, because they may appear in RGB.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** On `Carla/Maps/Town01_Opt`, after hiding 25 RoadLines objects, `Map.generate_waypoints(2.0)` returned a complete finite sample of 3,266 waypoints. Five seeded native-spawn routes were created with direct `Waypoint.next(2.0)` calls; every route has 60 driving waypoints, 59 rechecked direct edges, and length 114.841–121.110 m. Complete-network and per-route DebugHelper views were captured, then cleared. This verifies graph construction only; no actor spawn, Traffic Manager path submission, or actual drive is implied. Run `20260917T194300Z-town01-opt-routes-final-c5b492`.

**EXPERIMENT (2026-09-18, CARLA 0.9.16):** A controlled route-04 nadir-RGB comparison on the same Town01_Opt/RoadLines state found normal road texture without DebugHelper, the same intact texture with `draw_line` only, and black rectangular occluders at every route sample with `draw_point(0.10)`. Thus the prior black roads were a DebugHelper point-rendering artefact, not missing map texture or a RoadLines side effect. Corrected route previews submit all 3,266 points temporarily, clear them before sensor capture, and draw routes with lines only. Evidence: `20260918T121243Z-debug-render-probe-295692`, `20260918T121645Z-town01-opt-routes-clean-debug-95bdcf`.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** A deterministic search enumerated 1,020 complete direct-`Waypoint.next(2.0)` paths from 255 native spawn anchors and classified sustained heading changes. It produced five visual replacement candidates of 220.061–350.302 m with zero, one left, one right, and two different three-turn profiles. All dense reference edges were revalidated. An adaptive subset using approximately 10 m spacing on straights and 2 m within 12 m of real turn events retained 23–90 points per route. `is_junction` alone is not a suitable densification trigger because it caused long straight-through sections to remain at 2 m density in the first iteration. These are candidates, not adopted routes or driving evidence. Evidence: `20260919T054900Z-route-candidates-adaptive-a1`, `20260919T055800Z-route-candidates-adaptive-a2`.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** After the user accepted replacement geometries 1–3, their dense waypoint IDs were reconstructed and verified unchanged. Route 4 was extended to four detected approximately 90-degree turns and 508.150 m. A seeded search of 1,275 complete direct-next paths found 237 candidates that fully crossed the selected outer automobile bridge and later turned; the selected route is 495.316 m and deviates only 4.684 m from the 500 m design target. Its bridge segment crosses both declared banks before the later turn. The narrow bridge visible inside town had no connected Driving-waypoint candidate in the tested corridor. All five dense reference chains and adaptive subsets validated; no vehicle drive is implied. The user subsequently approved revised routes 4–5, making all five geometries authoritative for the next Stage-2 step. Evidence: `20260919T062007Z-route-revision-ca00ee`.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** Two route-1 Traffic Manager `set_path` probes accepted first an adaptive and then a complete connected 2 m location chain, but each left the route after 94 m at a later branch and timed out. They are retained as incomplete rather than treated as connectivity failures. A `set_route` pilot using four derived `Straight` decisions completed route 1; a one-route pilot then completed route 2. The full `set_route` run spawned a Tesla Model 3 at every approved route start, used synchronous world/TM settings and 100% ignored signs/lights, and passed all five drives: 7.20–7.93 m finish distance (≤8 m), 0.997–1.247 m maximum deviation (≤15 m), at least 95% projected progress, zero collision events, no timeout/stuck outcome, and stop after completion. Evidence: incomplete `20260919T065121Z-tm-autopilot-pilot-ea602d`, `20260919T065327Z-tm-autopilot-pilot-282f01`; complete `20260919T065802Z-tm-autopilot-approved-routes-106f97`. This validates Stage-2 route following only; it is not camera/data-recording evidence.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** At the user's request, the route labels were reordered without changing waypoint geometry: the 495.316 m bridge route became route 4 and the 508.150 m four-turn route became route 5. A fresh revision copied the geometry-bearing fields unchanged, retained source and target hashes, and passed all mapping checks. A new all-five `set_route` drive then passed under those current identifiers with the same acceptance metrics. Evidence: `20260919T154916Z-route-numbering-swap-b5e941`, `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`.

**ARTIFACT-CONFIRMED (2026-09-23, CARLA 0.9.16):** Cropping the existing dense reference chains and reapplying the unchanged adaptive spacing policy produced five shorter routes of 110.000–251.108 m with 12/32/32/44/60 working points. All 416 retained dense edges were reconstructed and checked against `Waypoint.next(2.0)` by the existing autopilot loader. A camera-free drive of each new start passed, with no collisions and 0.996–1.246 m maximum deviations. Trajectories passed within 0.292 m of every retained turn centre; the bridge drive reached reference index 120 before braking, beyond its exit at index 118. Compared with the historical same-controller/seed drives, total driving time excluding the 4 s stop observation fell from 186.70 to 88.85 s (52.41%). This measures route-driving duration, not image bytes or recording wall time. Evidence: `20260923T160431Z-shorter-routes-b72a9d/trim_validation.json`, `20260923T160409Z-shorter-routes-autopilot-b8548d/validation.json` and `duration_comparison.json`.

**ARTIFACT-CONFIRMED (2026-09-23, CARLA 0.9.16):** The first full 18-sensor recording on the shortened routes, `20260923T161516Z-baseline-pilot-route05-two-turns-clear-day-895150`, completed `route_05_two_turns` in `clear_day`. Its 58 accepted samples span 28.500 s of simulation time and contain 522 RGB, 522 lossless raw semantic-ID and 522 CityScapes-preview PNGs. Both validators passed (including frame/pose timestamp equality, PNG integrity and zero ego-body pixels), and visual review found normal RGB and interpretable semantic palette frames. Recording took 170.993 wall seconds with 2.160 s writer backpressure; the signed local set is 2,205,036,691 bytes. It became the first cell of the complete Stage-4 matrix.

**ARTIFACT-CONFIRMED (2026-09-23, CARLA 0.9.16):** The complete shortened-route Stage-4 matrix contains ten successful route/weather cells: five routes under `clear_day` and `wet_cloudy_day`, one repeat each. It has 339 aligned samples and 9,153 PNGs across 164.500 accepted simulation seconds. Every accepted run has `outcome=completed`, zero collision, stopped ego vehicle, maximum route deviation at most 1.246 m, passed data/baseline validation, and a locally rechecked manifest (9,303 signed entries total). The ten final directories occupy 12,904,099,739 bytes; recording wall time totalled 1,076.278 s, including 24.292 s bounded-writer backpressure. Representative clear and wet RGB/semantic contact sheets were visually reviewed. One user-interrupted partial retry is retained separately rather than counted as a cell. The user supplied successful checksum-mode `rsync` output for the full Mac copies of `runs/` and `logs/`; this is external-copy evidence reported through the session. Evidence: matrix config, batch summaries `logs/stage4-batch-20260923T163322Z.json` and `logs/stage4-batch-20260923T165856Z.json`, and the registered run directories.

## 5. Argoverse 2 Camera Rig

**DOC:** AV2 Sensor Dataset provides seven ring cameras, two front stereo cameras, sensor-to-ego calibration, and camera intrinsics. The full dataset is very large; this project needs a selected calibration, not every sensor log. S09, S10.

Nine position names:

- `ring_front_center`
- `ring_front_left`
- `ring_front_right`
- `ring_side_left`
- `ring_side_right`
- `ring_rear_left`
- `ring_rear_right`
- `stereo_front_left`
- `stereo_front_right`

**DECISION:** attach RGB plus semantic sensors at every position. These semantic sensors are a synthetic project addition; do not claim real AV2 had physical semantic-segmentation cameras.

Select one AV2 log/calibration and preserve its log ID, source, raw values, and retrieval check. A documentation table is an example, not a universal calibration. Do not mix values from different logs.

Validate:

1. Transform direction (for example, `egovehicle_SE3_sensor`), quaternion component order, units, and camera/vehicle coordinate systems.
2. Conversion to CARLA axes and handedness. Copying xyz or changing one angle sign is not proof of a valid transform.
3. The chosen CARLA vehicle actor origin relative to AV2 ego origin. Record and justify the needed offset/transform.
4. Rotation matrices, optical-axis directions, stable numerical checks, and images from every camera. Control points must project in the expected direction.
5. Resolutions: AV2 documentation lists front-centre as width 1550 × height 2048 and the other eight as width 2048 × height 1550. Confirm this for the selected calibration.

For a pinhole estimate, horizontal FOV is `2*atan(width/(2*fx))`, converted to degrees. This alone cannot reproduce arbitrary fx/fy/principal-point/distortion combinations. Check CARLA camera capabilities, preserve differences, and satisfy the placement requirement through extrinsics without falsely claiming full optical equality.

## 6. Recording at 2 Hz and Synchronisation

**DECISION:** frequency is simulation time. With a 0.05-second world step, a 0.5-second period spans ten steps; actual sensor frames must still be checked. `sleep(0.5)` does not prove 2 Hz simulation sampling.

CARLA and TM need compatible synchronous mode. Camera callbacks can arrive after the frame is calculated. Group all camera images by frame ID and match them to the ego transform from the same world snapshot. Drain expected data after the final tick and close files correctly. S03, S07, S08.

Minimum ego-pose record: frame, simulation timestamp, location x/y/z, and rotation roll/pitch/yaw with documented units and coordinate system. Speed/control values may be stored for animal-effect analysis but must remain separate from the required minimum.

Calculate expected image count from the defined capture interval and window boundaries, including warm-up, rather than rounding `duration*2`. Every accepted timestamp requires all 18 images and one pose. Treat lost callbacks, duplicates, resolution mismatch, and corrupt files as diagnosable events.

Store semantic data as lossless class IDs. Extract the ID from the channel specified by the installed CARLA version. Keep human-readable palettes separately. Do not hard-code labels from another release and do not save labels as JPEG. S08.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** official AV2 calibration Feather files for Sensor Dataset log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca` were retrieved anonymously from the documented public S3 dataset, without downloading sensor imagery. Their SHA-256 values are preserved in `configs/av2/.../calibration.json`. AV2 ego (+x forward, +y left, +z up) was converted to CARLA vehicle (+x forward, +y right, +z up), while AV2 optical (+x right, +y down, +z forward) was converted to the CARLA camera actor axes. Every converted rotation had determinant 1, orthonormal error below `2.3e-16`, and Euler round-trip error below the validator limit. The Tesla rear axle was computed from the wheel positions only after one synchronous tick; before that tick this build returned an identity actor transform and world-space wheel coordinates. Failed pilots preserve both mistakes rather than hiding them.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** exact AV2 rear-axle placement made the Tesla hood visible in the front-centre image. A declared uniform `+0.5 m` local-z mounting adaptation removed it; the validator obtains the ego semantic tag from the actor and found zero ego pixels in the bottom 10% of all full-rig raw semantic frames. This adaptation is a CARLA vehicle-clearance compromise and prevents a claim of exact AV2 translation equivalence. CARLA used AV2 resolution and `2*atan(width/(2*fx))` horizontal FOV, but did not reproduce the off-centre principal point or full distortion coefficients.

**EXPERIMENT (2026-09-19, CARLA 0.9.16):** run `20260919T162408Z-av2-all-cameras-short-247e3f` used 18 sensors in synchronous 0.05 s simulation and accepted four complete samples at 0.5 s intervals. Each frame has nine RGB images, nine raw-ID semantic images, nine palette previews, and one same-frame ego pose. The validator decoded all 108 PNGs (163,964,529 bytes), found no missing or duplicate sensor key and no late event after stop, and generated RGB/semantic contact sheets that passed visual review. The accepted capture span was 1.500000022 s, wall time 126.905 s, and measured run output before validation was about 109.34 MB per accepted simulation second. GPU memory samples peaked at 4,657 MiB and host used-memory samples at about 8.08 GB. This is a short rig/throughput validation, not a complete baseline route or a claim that longer recordings cannot drop frames.

Dataset validation must check: JSON parseability; existing paths; unique frames; 0.5-second intervals; all-camera alignment; dimensions/encoding; and no unexplained drops. Define floating-point tolerance before validation, not afterwards to hide errors.

## 7. Animal: Capability Boundaries

**DOC:** the standard blueprint library exposes ready actors and props. `static.prop.mesh` can use meshes already present in the selected package; it cannot universally import arbitrary files from disk. Typical new-asset ingestion requires preparation and packaging. S13, S14.

**UNCONFIRMED:** a suitable animal mesh in the current image. A public catalogue without animals does not prove no hidden mesh exists, but a `dog` or `deer` string match does not prove a functional asset either. A `doghouse` is not a dog.

Validation order: catalogue → real asset → spawn → visibility → movement → semantics → collision/response. A compatible prebuilt extension can be investigated, but validate its licence, Unreal-preparation requirement, and fit with the user’s constraint.

Kinematic motion without leg animation is acceptable. It does not guarantee correct collision between frames. Traffic Manager may not react to an arbitrary prop as it reacts to a registered vehicle or walker. Do not secretly apply ego braking and report it as natural reaction; if another controller is used by agreement, disclose it.

For reproduction, preserve starting pose, trajectory, speed, trigger/start time, and seed. If conclusions use minimum distance, collision, or braking, retain enough measurements in a separate actor log.

## 8. LLMs and Evaluation

**DECISION:** use APIs only. Give the model the available operations, asset catalogue, and spatial anchors such as route waypoint and road side. The model chooses executable actions; the executor validates ranges and applies operations in a known order.

Preserve user request, system/developer prompt, schema, raw response, parsed SceneSpec, settings, and every attempt. Give all models equivalent scene information and tasks. Document API differences and adapters.

Exact API IDs are unconfirmed. The discussion considered GPT-6 Astra, Qwen3.8-27B, and Qwen3-8B; the 8B candidate is from a different series. A public card or availability in Codex does not prove access through the user’s project API account. S15–S17.

Before calls, fix prompt set, success criteria, repeats, retries, timeouts, and correction rules. Metrics:

- valid response and valid schema;
- execution without manual correction;
- request fulfilment, including object count and spatial relations;
- first-attempt success and success after retries, separately;
- complete API-response time; time to first token only when streaming is measured;
- CARLA validation/application time separately;
- usage/cost only where data and price are available;
- errors, unavailable actions, and correct refusal.

Replay a saved configuration for dataset recording without another LLM call. LLM quality uses all attempts; a manually selected successful run must not conceal other failures.

**DOCUMENTED REVIEW (2026-09-24, Stage 5):** ScenarioGen, TTSG, TrafficComposer, and ChatScene were compared from their primary publications and author repositories (S18–S21). All four concern runtime traffic-scenario construction from existing maps and assets, but none is directly compatible with the complete project stack: CARLA 0.9.16, `Town01_Opt`, five fixed routes, and the validated 18-sensor recorder. The common useful principle is an intermediate representation between language and simulator operations. ScenarioGen most directly separates JSON, validation, and a fixed runner; TTSG adds map-geometry grounding; TrafficComposer uses an explicit traffic IR; ChatScene uses reusable route-aware primitives but ultimately executes Scenic programs.

**DECISION:** Stage 6 will use a project-owned, versioned `SceneSpec` as passive data, strict pre-execution validation, a fixed allow-listed CARLA executor, and post-application checks. It will not evaluate model-generated Python/Scenic or use `eval()` to parse model output. Replay must preserve the request and raw response as provenance while resolving all selected blueprints, transforms, route/map IDs, parameters, seeds, and outcomes. The review supports this design direction but does not prove it works on the project setup; that is a Stage-6 experiment. None of the reviewed methods resolves the missing compatible animal asset.

## 9. Comparison Protocol and Scale

**EXPERIMENT (2026-09-24, Stage 6 pre-API):** a project-owned strict JSON parser and deterministic `SceneSpec` resolver were tested without an API. It rejects duplicate object keys, `NaN`/`Infinity`, direct world coordinates, unsupported fields, unknown map/weather/route/blueprint values, out-of-range values and planned actor conflicts. A separate response form records a structured `unsupported_capability` refusal for a moving animal. The executor loaded a fresh `Town01_Opt` world, reapplied RoadLines hiding, reloaded the stored route, applied the fixed weather profile, checked live blueprint/map feasibility, spawned only allow-listed parked vehicles, saved before/after observer RGB frames, captured three complete 2 Hz samples from the existing 18-sensor rig, and drove the 110 m straight route to completion. No model endpoint was called.

The initial one-Audi wet run `20260924T110210Z-local-straight-parked-vehicle-observer-fix-213a80` and replay `20260924T110353Z-local-straight-replay-ad721d` each passed the existing camera/data validator (3 samples, 81 PNGs), route completion without collision, and semantic-supported visibility in the front-centre, front-left, stereo-front-left and stereo-front-right cameras. The saved SceneSpec, selected blueprint and actual transform were identical after the fresh-world replay. The two-Audi clear run `20260924T110725Z-local-straight-composite-safe-af8031` also passed. Failed attempts are retained: sandbox loopback does not permit the CARLA client; a right-side target was still a driving lane; one left-side target intersected static geometry; and an observer callback wait was fixed. This validates the local architecture only, not an API model or an LLM comparison.

**EXPERIMENT (2026-09-24, Stage 6 access only):** `20260924T120821Z-api-model-inventory-5f0d01` used authenticated model-list requests only, with no prompt/text generation. OpenAI returned 132 advertised IDs including `gpt-6-astra`; Model Studio's Singapore endpoint returned 161 Qwen IDs including `qwen3.8-27b` and `qwen3-8b`. The model-list endpoint establishes credential and region compatibility, not a successful completion, a billable price, or structured-output support. The project records the three exact IDs as the initial comparison candidates and retains the prior sandbox-network failure and Model Studio parser-revision limitation as separate runs.

**EXPERIMENT (2026-09-24, Stage 6 generation smoke):** `20260924T121813Z-api-generation-smoke-611d18` sent one natural-language parked-Audi request to OpenAI `gpt-6-astra` and DashScope `qwen3-8b`, each with a maximum of 192 output tokens and no retry. Their JSON-mode responses used 250/146 and 265/138 input-or-prompt/output-or-completion tokens respectively and passed the project parser plus deterministic route-relative resolver. Their resolved transforms agreed exactly; seeds 1 and 42 are model outputs. The run did not start CARLA, execute a scene, or measure price, so it is integration evidence rather than an LLM-quality comparison.

**EXPERIMENT (2026-09-24, Stage 6 fixed pilot):** `20260924T123036Z-api-fixed-protocol-884ef7` used one shared JSON-mode prompt context and three fixed tasks for `gpt-6-astra`, `qwen3.8-27b`, and `qwen3-8b`: one parked Audi, two parked Audis and unsupported moving animal. The protocol fixed one repeat, zero retries, 60 s timeout and at most 256 output tokens before calls. All 9/9 first attempts passed the strict parser, executor policy and exact task matcher; the three animal answers were structured `unsupported_capability` refusals. Reported API latency ranged from 3.465898 to 10.565166 s; provider usage is retained, but cost is not calculated because no dated price record is stored.

Each of the six accepted SceneSpecs was executed later without another API request in a fresh `Town01_Opt` world. The runs each passed the existing 18-camera validator (three aligned 2 Hz samples; 81 PNGs), semantic-supported visibility, collision-free 110 m route completion and stopped-ego check. Selected CARLA application/validation wall time was 39.186744–41.130043 s. A second GPT simple-scene replay is retained because its process completed after the orchestration handle returned; it is shown as an extra replay, not a hidden replacement. The machine-readable linkage/timing table is `stage6_comparison.json` in the API run. These are one-repeat pilot observations, not a statistical model ranking, a cost measurement, or animal validation.

Two comparisons have different units: LLM request/attempt for scene editing, and vehicle drive for the dataset. Keep them distinct in the report.

Control route, weather, rig, vehicle, and control settings before/after changes. Scene versions must cover both item 3 and item 4. Changing weather together with the scene without a paired control prevents causal interpretation.

Calculate recording count after selecting the matrix: `routes × scene versions × weather conditions × drive repeats`. For example, `5 × 3 × 2 × 1 = 30` is only an illustration for three selected scenes, not an approved volume or a complete model comparison.

For T seconds, C=9 positions, two sensor types, and 2 Hz, expect roughly `36*T` image files before capture-window boundary details. Real size depends on content and compression. Measure a pilot, then extrapolate. The 300 GB SSD also holds the image, environment, and temporary files, not only the dataset.

## 10. Primary-Source Index

| ID | Source | Use |
|---|---|---|
| S01 | [CARLA 0.10.0 release](https://carla.org/2024/12/19/release-0.10.0/) | Limits of the specific packaged UE5 release |
| S02 | [UE5 downloads](https://carla-ue5.readthedocs.io/en/latest/download/) and [UE5 API](https://carla-ue5.readthedocs.io/en/latest/python_api/) | Release/nightly/dev distinction; not evidence an API works in 0.10.0 |
| S03 | [CARLA Python API](https://carla.readthedocs.io/en/latest/python_api/) | World, map, actors, TM; compare with installed 0.9.16 |
| S04 | [CARLA 0.9.16 release](https://carla.org/2025/09/16/release-0.9.16/) | Selected release/branch |
| S05 | [Maps and navigation](https://carla.readthedocs.io/en/latest/core_map/) | Waypoints, environment objects, topology |
| S06 | [Runtime texture API](https://carla.readthedocs.io/en/0.9.15/tuto_G_texture_streaming/) | Candidate for texture edits; verify against 0.9.16 |
| S07 | [Traffic Manager](https://carla.readthedocs.io/en/latest/adv_traffic_manager/) | Synchronisation, control, limitations |
| S08 | [Sensors reference](https://carla.readthedocs.io/en/latest/ref_sensors/) | Camera attributes, semantic encoding, `sensor_tick` |
| S09 | [Argoverse 2](https://www.argoverse.org/av2.html) | Assignment link |
| S10 | [AV2 Sensor Dataset guide](https://argoverse.github.io/user-guide/datasets/sensor.html) | Nine cameras, calibration, resolution |
| S11 | [ScenarioRunner](https://github.com/carla-simulator/scenario_runner) | Routes/version compatibility; need not install project |
| S12 | [CARLA Leaderboard](https://github.com/carla-simulator/leaderboard) | Open route tests; validate map and version |
| S13 | [Props catalogue 0.9.16](https://carla.readthedocs.io/en/0.9.16/catalogue_props/) | Typical available props |
| S14 | [Content authoring: props](https://carla.readthedocs.io/en/latest/content_authoring_props/) | `static.prop.mesh` and packaged-asset limits |
| S15 | [GPT-6 Astra API card](https://developers.openai.com/api/docs/models/gpt-6-astra) | OpenAI inventory and one local-validation smoke confirm advertised access to `gpt-6-astra`; not a comparison result |
| S16 | [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | Candidate card; DashScope Singapore inventory confirms advertised `qwen3.8-27b`, but no completion yet |
| S17 | [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | Smaller candidate; DashScope Singapore inventory and one local-validation smoke confirm `qwen3-8b` access |
| S18 | [ScenarioGen report](https://cse.buffalo.edu/tech-reports/2026-22.pdf) and [author repository](https://github.com/harshit88a/scenario-gen) | JSON schema, validator, fixed CARLA runner; accessed 2026-09-24 |
| S19 | [TTSG paper](https://arxiv.org/abs/2409.09575) and [author repository](https://github.com/basiclab/TTSG) | Language parsing and road-geometry grounding; accessed 2026-09-24 |
| S20 | [TrafficComposer paper](https://arxiv.org/abs/2505.14881) and [author repository](https://github.com/TrafficComposer/TrafficComposer) | Explicit multimodal traffic intermediate representation; accessed 2026-09-24 |
| S21 | [ChatScene paper](https://openaccess.thecvf.com/content/CVPR2024/papers/Zhang_ChatScene_Knowledge-Enabled_Safety-Critical_Scenario_Generation_for_Autonomous_Vehicles_CVPR_2024_paper.pdf) and [author repository](https://github.com/javyduck/ChatScene) | Knowledge-enabled Scenic generation and route-aware scenario selection; accessed 2026-09-24 |
| S22 | [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) and [Alibaba Model Studio model-list API](https://www.alibabacloud.com/help/en/model-studio/list-models) | Common safe structured-output direction and authenticated model-inventory endpoint; accessed 2026-09-24 |

The Stage-5 method review is complete for the four selected, most relevant runtime-scenario approaches. Detailed comparison and project applicability are summarized in section 2 of `report/report.md`.

## 11. Adding Knowledge

Each entry should include date, topic/stage, evidence label, version, conclusion, source or run ID, applicability limits, and next action if needed. Keep disproved hypotheses as disproved with evidence rather than deleting them silently.
