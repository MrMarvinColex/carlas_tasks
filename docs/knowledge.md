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

**DOC:** a waypoint is an oriented point on a road lane, with transform and road identifiers. A continuous road is discretized at a declared resolution. Traffic Manager `set_path` receives a sequence of Locations; an arbitrary list can be topologically impossible. S03, S07.

**DECISION:** preserve five connected routes and validate them by actual driving. GlobalRoutePlanner is a route-construction candidate; use the version compatible with installed PythonAPI. ScenarioRunner/Leaderboard routes may be used after validating their map and version. Do not install a full benchmark only to obtain a few coordinates unless needed. S11, S12.

Route criteria: at least 10 waypoints, usable start, connectivity, suitable direction, meaningful duration, and no infinite cycle. Metrics: distance travelled, proximity to finish, path following, timeout, and collisions. Traffic Manager may continue after the finish, so the experiment must define completion.

DebugHelper is for route-selection verification. Remove or expire debug markings before dataset recording, because they may appear in RGB.

**EXPERIMENT (2026-09-17, CARLA 0.9.16):** On `Carla/Maps/Town01_Opt`, after hiding 25 RoadLines objects, `Map.generate_waypoints(2.0)` returned a complete finite sample of 3,266 waypoints. Five seeded native-spawn routes were created with direct `Waypoint.next(2.0)` calls; every route has 60 driving waypoints, 59 rechecked direct edges, and length 114.841–121.110 m. Complete-network and per-route DebugHelper views were captured, then cleared. This verifies graph construction only; no actor spawn, Traffic Manager path submission, or actual drive is implied. Run `20260917T194300Z-town01-opt-routes-final-c5b492`.

**EXPERIMENT (2026-09-18, CARLA 0.9.16):** A controlled route-04 nadir-RGB comparison on the same Town01_Opt/RoadLines state found normal road texture without DebugHelper, the same intact texture with `draw_line` only, and black rectangular occluders at every route sample with `draw_point(0.10)`. Thus the prior black roads were a DebugHelper point-rendering artefact, not missing map texture or a RoadLines side effect. Corrected route previews submit all 3,266 points temporarily, clear them before sensor capture, and draw routes with lines only. Evidence: `20260918T121243Z-debug-render-probe-295692`, `20260918T121645Z-town01-opt-routes-clean-debug-95bdcf`.

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

## 9. Comparison Protocol and Scale

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
| S15 | [GPT-6 Astra API card](https://developers.openai.com/api/docs/models/gpt-6-astra) | Candidate model; account access unverified |
| S16 | [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | Candidate card, not a verified API endpoint |
| S17 | [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | Smaller candidate from another series |

This index is a technical starting point. It **does not complete assignment item 2**: stage 5 still needs a review of research methods for LLM-driven CARLA editing, including primary papers and author repositories.

## 11. Adding Knowledge

Each entry should include date, topic/stage, evidence label, version, conclusion, source or run ID, applicability limits, and next action if needed. Keep disproved hypotheses as disproved with evidence rather than deleting them silently.
