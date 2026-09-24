# Decisions, Assumptions, and Open Questions

Initial record date: 2026-09-16. User-approved constraints override earlier assistant proposals. This document preserves current rationale, not the full conversation.

## Accepted Approach

### D01. CARLA 0.9.16

**Status:** accepted baseline; image launch reported by the user.

The user authorized selecting the version that can complete the assignment. The official CARLA 0.10.0 packaged-release description lists missing Town01 and restrictions in required functions. `latest` pages may describe development features unavailable in a release. We therefore use 0.9.16 and verify the actual image. This does not claim that all future UE5 versions are unsuitable. Sources: S01–S04 in `knowledge.md`.

### D02. Runtime Scene Editing Through CARLA API

**Status:** user clarification.

An edited map version means a saved configuration layered over baseline Town01: enabling/hiding objects, placing available actors, movement, and weather. We do not rebuild OpenDRIVE or the Unreal scene. Reproduction means loading the map and applying the configuration. Distinguish a persistent map file from in-memory server scene state.

### D03. Remove Visible Road Markings

**Status:** requirement; implementation method is open.

Remove road lines and associated markings while preserving the road and navigation topology. `RoadLines`, `Decals`, and runtime textures are candidates to test. The claimed reason, “simplifying the scene,” is the user’s hypothesis; do not claim an FPS gain without measurement.

### D04. Full AV2 Camera Rig

**Status:** user clarification; calibration and conversion artifact-confirmed on 2026-09-19.

Use nine AV2 positions: seven ring and two stereo. Each has RGB and semantic sensors, for 18 streams at 2 Hz of simulation time. Position and orientation follow AV2 Sensor Dataset log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca`; its two official calibration Feather files and their SHA-256 values are preserved under `configs/av2/`. AV2's rear-axle ego origin is aligned to the Tesla Model 3 rear axle computed from CARLA wheel positions after the first synchronous tick. Axis conversion is explicit, and the quaternion-to-CARLA Euler round trip is numerically checked for every camera.

The AV2 translation is retained, then a documented uniform `+0.5 m` CARLA-local z mount adaptation is applied because the exact AV2 height exposed the Tesla hood in the front-centre view. The unadjusted pilot is retained as failed evidence; the adjusted one-view and 18-sensor runs contain no ego semantic tag in the bottom 10% of any image and passed visual review. CARLA receives the original resolution and horizontal FOV derived from `fx`; it cannot reproduce arbitrary `cx`, `cy`, or the complete AV2 `k1/k2/k3` model, so distortion is disabled and optical equivalence is not claimed. Evidence: `20260919T162113Z-av2-front-center-pilot-local-98cb54`, `20260919T162313Z-av2-front-center-clearance-bb5bae`, and `20260919T162408Z-av2-all-cameras-short-247e3f`.

### D05. Separate Ego Transform

**Status:** user clarification and PDF deliverable format.

Each completed drive has one `transforms.json` containing the vehicle position/orientation time series. Animal data is kept separate from ego pose. Initial state, trajectory, speed, and trigger are stored in scene configuration; include detailed actor logging only where analysis needs it.

### D06. A Real Animal With the Simplest Sufficient Motion

**Status:** user clarification; feasibility not yet confirmed.

Leg animation is unnecessary, but the object must look like an animal, exist in the 3D scene, move, and affect the scene. Define the effect before evaluation. Visibility, physical collision, and Traffic Manager response are different checks. If no suitable asset exists, discuss a changed approach. A pedestrian is valid for debugging but does not complete the animal requirement.

### D07. Three API-Only LLM Variants

**Status:** user clarification; API access/advertised model IDs and one bounded pre-CARLA generation smoke are artifact-confirmed on 2026-09-24.

Compare GPT-Astra, a Qwen model around 27B, and one around 8B. The sanitized zero-inference inventory `20260924T120821Z-api-model-inventory-5f0d01` authenticated `OPENAI_API_KEY` at `api.openai.com` and found `gpt-6-astra`; it authenticated `DASHSCOPE_API_KEY` at the Singapore Model Studio endpoint and found `qwen3.8-27b` plus `qwen3-8b`. The bounded pre-CARLA smoke `20260924T121813Z-api-generation-smoke-611d18` then made one JSON-mode request to `gpt-6-astra` and `qwen3-8b`; both outputs passed strict local SceneSpec validation and resolution. This is not yet an evaluation: `qwen3.8-27b`, retries, cost, structured-output enforcement and CARLA application remain untested. Different Qwen generations make this more than a parameter-count comparison, and conclusions must acknowledge that.

### D08. Disposable VM, External Memory

**Status:** user requirement.

Code and documents go to Git. Large results go to the Mac or external storage. Verify an independent copy before VM deletion. A new VM downloads the Docker image again; that is expected. Do not deploy local LLMs; use the GPU for CARLA.

**2026-09-16 implementation decision, user-selected:** use pull-based `rsync` from the Mac as the primary operational backup. The Mac connects with SSH alias `carla-vm`; runs are copied under `/Users/madness/Научка/CARLA/runs/<run_id>/` without `--delete`, then verified against their manifest. The stage-0 smoke-run copy passed this check. Google Drive remains a later final-delivery or secondary-copy option, not a substitute for measured and verified run export.

### D09. Separate Tasks and Automatic Recording

**Status:** user requirement.

Every task restores context through `AGENTS.md` and documents. Stage numbers are fixed. Scripts record measurements and metadata; the agent maintains explanations, decisions, status, and report. Markdown itself is not executable automation. Context transfer depends on updated files, not on promised memory between chats.

### D10. Private Development, Public Delivery

**Status:** agreed workflow plus PDF delivery requirement.

Development stays in private Git. Before the final step, inspect contents and history, then publish code only with authorization. Put report and dataset on Google Drive. Keep a local assignment copy; do not publish it automatically. Billing shutdown and VM deletion are independent of publication.

### D11. Require Both RGB and Raw-Semantic Evidence for Road-Marking Removal

**Status:** accepted and corrected after stage-1 evidence on 2026-09-17.

On base Town01, `World.enable_environment_objects(RoadLines_ids, False)` removed the RoadLines semantic class from saved raw segmentation images but not the yellow markings in captured RGB. `MapLayer.Decals` on Town01_Opt, the tested `apply_color_texture_to_object(..., Diffuse, TextureColor)` calls, and a 64×64 all-channel `apply_textures_to_object` call also failed the visible-RGB criterion; Decals additionally changed unrelated scene content. Conversely, direct RoadLines hiding on Town01_Opt passed a repeated visual review and a three-location confirmation: each RGB pair lost the visible yellow markings and raw class 24 became zero. Therefore a scene is never described as “without road markings” unless both RGB and raw semantic checks pass at its declared coverage. Current evidence: runs `20260917T110520Z-map-api-676d`, `20260917T111200Z-town01-opt-decals-5a62`, `20260917T145900Z-town01-texture-ead1`, `20260917T150510Z-town01-opt-direct-638d` (corrected visual verdict), `20260917T151600Z-town01-full-texture-1c2f`, and `20260917T153000Z-town01-opt-coverage-b6e3`.

This does not change D02: OpenDRIVE and Unreal authoring remain out of scope. It replaces the untested assumption that a `RoadLines`, `Decals`, or simple texture operation would complete D03; the operation is valid only on the actual map and coverage for which it passed.

### D12. Use Town01_Opt for the Runtime Marking-Free Scene

**Status:** accepted after Stage 1 evidence on 2026-09-17.

The required base map `Carla/Maps/Town01` was loaded and tested. Its captured RGB views did not pass road-marking removal. The installed `Carla/Maps/Town01_Opt` is an allowed candidate for layer/runtime operations and, after explicit testing, is selected for later route and recording work. After each Town01_Opt map load, apply `World.enable_environment_objects(RoadLines_ids, False)` to the 25 observed RoadLines environment objects.

The selection is limited to the declared three-observation coverage (straight road, intersection, traffic-control location); `get_crosswalks()` returned no point, so it is not a proof that every marking across the map is removed. Preserve the exact `Carla/Maps/Town01_Opt` name and run the RGB/raw-semantic and navigation checks in downstream runs. Evidence: `20260917T153000Z-town01-opt-coverage-b6e3`, with the earlier one-location review correction in `20260917T150510Z-town01-opt-direct-638d`.

### D13. Seeded Direct-Waypoint Routes for Stage-2 Selection

**Status:** accepted and artifact-confirmed on 2026-09-17.

For route selection, generate the complete finite `Map.generate_waypoints(2.0)` sample, then start from native map spawn points and form each route through direct `Waypoint.next(2.0)` edges. The deterministic seed is `20260917`; route files retain the spawn index, branch seed, every point's transform/road/lane identifiers, and each branch choice. The adopted set has five distinct 60-point routes and was independently revalidated by asking the predecessor for `next(2.0)` again for every edge. DebugHelper drawings use finite lifetimes and are explicitly cleared after saved views.

This replaces proposal P04's use of GlobalRoutePlanner for *route selection*. It does not prove that Traffic Manager accepts or follows these locations; Stage 2 drive validation must submit the stored routes and measure actual behaviour before this decision is used for data collection. Evidence: `20260917T194300Z-town01-opt-routes-final-c5b492`.

### D14. Texture-Safe DebugHelper Route Visualisation

**Status:** accepted and artifact-confirmed on 2026-09-18.

In the installed CARLA 0.9.16 renderer, `DebugHelper.draw_point` occludes the road material in a nadir RGB camera, including at a 0.10 m point size. A controlled probe held map, RoadLines operation, route, and camera fixed: no DebugHelper geometry and `draw_line`-only output kept the road texture intact; point-only output created repeated black rectangles. Therefore the complete waypoint sample is still temporarily submitted through `draw_point` for 0.5 simulation seconds, then explicitly cleared before any RGB sensor capture. Saved route previews use only `draw_line` primitives; the per-route filename and colour identify the path.

This replaces the previous route-preview rendering in `20260917T194300Z-town01-opt-routes-final-c5b492`; it does not change route geometry, map editing, or the later dataset camera protocol. Evidence: diagnostic `20260918T121243Z-debug-render-probe-295692` and corrected route run `20260918T121645Z-town01-opt-routes-clean-debug-95bdcf`.

### D15. Adaptive Route-Waypoint Spacing for Replacement Candidates

**Status:** user-approved spacing direction and all five route geometries on 2026-09-19.

Retain a connected 2 m reference chain for construction and audit, but propose a reduced sequential waypoint list at approximately 10 m spacing on straight sections and 2 m spacing within 12 m of detected heading-change events. Straight-through junctions do not by themselves trigger 2 m density. Saved RGB previews use `draw_line` crosses for the adaptive points and never `draw_point`.

The first candidate iteration densified every `is_junction` interval and was rejected during visual review because CARLA labels some long straight-through sections as junctions. The corrected candidate run reduces the straight control from 111 dense reference points to 23 proposed points while retaining 2 m coverage around actual turns. This spacing policy and the approved geometry set supersede D13's original 60-point route set for subsequent Stage-2 implementation. Traffic Manager compatibility and actual completion remain separate validations. Evidence: incomplete run `20260919T054900Z-route-candidates-adaptive-a1`, corrected run `20260919T055800Z-route-candidates-adaptive-a2`, and final approved revision run `20260919T062007Z-route-revision-ca00ee`.

### D16. Approval and Revision of the Adaptive Route Set

**Status:** all five geometries accepted by the user on 2026-09-19.

Preserve the first three candidate waypoint identities exactly. Extend route 4's deterministic path through a fourth full turn. Use the revised fifth geometry that fully crosses the outer automobile bridge, leaves its far bank, and then turns. Keep approximately 10 m spacing on straight sections and 2 m spacing within 12 m of detected turns while retaining the complete connected 2 m reference chain for audit.

The tested search found no connected Driving-waypoint candidate through the visually narrow bridge inside the town, so it is not selected for a vehicle/autopilot test. The final route-5 preview uses full-map framing and line-only DebugHelper rendering to avoid both point-billboard texture occlusion and out-of-map close-up artifacts. This decision originally did not claim that Traffic Manager could complete either revised route; that separate claim is now supported by D17. Evidence: complete run `20260919T062007Z-route-revision-ca00ee`; rejected and failed intermediate revisions remain registered.

### D17. Traffic Manager Instructions at Map Junctions

**Status:** accepted after Stage-2 drive validation on 2026-09-19.

Use `TrafficManager.set_route(vehicle, instructions)` for the approved routes. Reconstruct their stored 2 m waypoint identities and use the chain to verify connectivity and measure observed trajectory deviation, but derive one `Left`, `Right`, or `Straight` instruction for each contiguous `Waypoint.is_junction` group. The actor is registered with Traffic Manager in synchronous mode, and RoadLines hiding is reapplied after the map load. Completion requires proximity to the stored finish (≤8 m), at least 95% projected progress, zero collisions, no timeout/stuck result, and a stopped vehicle after autopilot is disabled.

This replaces use of `set_path` as the operational command for these routes. Two route-1 diagnostics showed that both adaptive and complete connected 2 m coordinate lists were accepted by `set_path` but later diverged at a branch. CARLA 0.9.16 documents both APIs and warns that topology must permit the supplied path/instructions. The final `set_route` run completed all five routes with 0.997–1.247 m maximum deviation and no collision. Evidence: incomplete `20260919T065121Z-tm-autopilot-pilot-ea602d` and `20260919T065327Z-tm-autopilot-pilot-282f01`; current complete run `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`.

### D18. Route Numbers Follow Increasing Complexity

**Status:** user-requested relabelling accepted on 2026-09-19.

Keep all five approved geometries unchanged, but relabel the complete bridge crossing followed by a turn as `route_04_bridge_then_turn` and the 508.150 m route with four turns as `route_05_four_turns`. Do not modify the earlier signed route run; preserve it as source and create a new signed revision that records the one-to-one identifier mapping. Re-run the five-drive Traffic Manager validation under the new identifiers.

Evidence: relabelling revision `20260919T154916Z-route-numbering-swap-b5e941`, which passed all geometry-preservation checks; complete renumbered drive validation `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`.

### D19. Frame-Keyed 2 Hz Recording Protocol

**Status:** accepted and artifact-confirmed on 2026-09-19.

Run the world and Traffic Manager synchronously at a 0.05 s fixed step and set all cameras to `sensor_tick=0.5`. Camera callbacks enter a queue keyed by CARLA frame ID. A sample is accepted only after every expected RGB/semantic callback for that frame has arrived and its timestamp matches the ego `ActorSnapshot` from the same `WorldSnapshot`; callback-time calls to `vehicle.get_transform()` are not used. Complete warm-up frames are explicitly discarded, in-flight callbacks are drained after sensor stop, and any missing, duplicate, dimension-mismatched, corrupt, or off-interval data fails validation.

RGB is lossless PNG. The semantic R-channel class ID is written unchanged to an 8-bit grayscale PNG, with a separate CityScapes palette preview. `transforms.partial.json` is rewritten after every accepted sample and is replaced by final `transforms.json` only after completion. The full short run accepted four timestamps 0.5 s apart with 18 aligned images and one ego pose each, zero duplicates or late events, and 108 readable PNG files including previews. Evidence: `20260919T162408Z-av2-all-cameras-short-247e3f`.

### D20. Stage-4 Baseline Matrix and Batching

**Status:** completed and externally checksum-verified on 2026-09-23.

Use the approved five `Town01_Opt` routes with the same Tesla, direct RoadLines hiding, synchronous Traffic Manager `set_route`, and nine AV2 RGB/semantic pairs as the baseline. The fixed initial matrix is `5 routes × 2 weather profiles × 1 repeat = 10 runs`: `clear_day` and `wet_cloudy_day`. The profiles save every actual CARLA weather parameter and are explicitly weather variations rather than seasons. The run order is reproducible from seed `2026092304`; the Traffic Manager seed is `2026092305`.

Before bulk recording, run the selected pilot under `clear_day`, validate it, and measure output. The provisional policy requires at least 100 GiB free before each drive, permits at most 100 GiB of locally unexported baseline results, and exports after two completed runs. This replaces proposal P05 only for the Stage-4 baseline; revise the budget only from a complete-route pilot result. Configuration: `configs/stage4_baseline_matrix.json`.

**2026-09-23 pilot interruption:** the user stopped the first full-route attempt after 77 complete samples (38.5 s) and 3,622,361,120 bytes. It was finalized as incomplete and local manifest verification passed. This is an observed partial-throughput point, not the required complete-route measurement and does not authorize a change to the matrix or a claim of Stage-4 acceptance.

**2026-09-23 complete shortened-route pilot:** after D22 superseded the source geometry, `route_05_two_turns`/`clear_day` completed in `20260923T161516Z-baseline-pilot-route05-two-turns-clear-day-895150`. It accepted 58 aligned samples over 28.500 s, completed the drive with zero collision, 1.246 m maximum deviation and a stopped vehicle, and passed dataset/baseline validation plus visual contact-sheet review. Recording took 170.993 wall seconds (2.160 s bounded-writer backpressure); summary output was 77.314 MB per accepted simulation second and the finalized 1,581-entry set is 2,205,036,691 bytes. This supports retaining the existing 100 GiB local-unexported guardrail and export-after-two policy; it does not yet satisfy off-VM preservation because the copy remains unverified.

**2026-09-23 temporary batch exception:** the user authorized recording the remaining nine cells before the next external export. `scripts/stage4_batch.py` made that bounded operational change: it retained the per-run 100 GiB free-disk check enforced by `stage4_baseline.py`, but deliberately did not stop after two completed runs. Every run received its own finalization and local manifest verification; a recorder, finalizer, manifest, or local-verification failure stopped the batch rather than silently skipping a cell. This was a temporary sequencing exception, not a replacement for the Stage-4 off-VM-copy acceptance requirement.

**2026-09-23 completion:** the first batch completed seven remaining cells, then was manually interrupted during one retry; that incomplete 385-file run was finalized and retained. A second batch successfully retried that cell and completed the final cell. Together with the initial pilot, this gives one successful run for every matrix cell. Rechecking all ten local manifests passed (9,303 signed entries across the accepted sets), and the user ran checksum-mode `rsync -nrc --itemize-changes` from the Mac against the whole VM `runs/` and `logs/` trees with no output. The complete stage-4 data therefore has an externally verified Mac copy, while the user-operated terminal result remains user-reported evidence. The temporary export-after-two exception is closed.

### D21. Bounded Asynchronous PNG Writer for Stage-4 Recording

**Status:** accepted for the next Stage-4 route-completion pilot after local benchmark on 2026-09-23.

Preserve the D19 data contract: each accepted 2 Hz point still has nine RGB PNGs, nine lossless grayscale raw semantic-ID PNGs, nine CARLA CityScapes-palette preview PNGs, and a same-frame ego pose. Detach the sensor buffers before asynchronous work, then encode PNGs in a four-worker bounded queue. The tick thread applies explicit backpressure when the queue reaches its configured limit; it never discards or silently skips a capture. The CARLA palette conversion remains local to the tick thread, because concurrent `carla.Image.save_to_disk()` caused a retained RPC-timeout failure.

The clean 120 s throughput benchmark `20260923T134157Z-async-writer-120s-throughput-28fd4a` accepted 238 samples over 118.5 s, generated 6,426 readable PNGs, passed timing/pose/ego-body validation, and its 6,441-entry manifest verified locally. Its recording-phase wall duration was 710.624 s with 71.187 s explicit writer backpressure. It intentionally drives past the route endpoint, so it is not a baseline acceptance test and its route-deviation metric is not applicable. Evidence: two retained failed implementation probes, successful 5 s smoke `20260923T134010Z-async-writer-local-palette-smoke-cbcacd`, and the 120 s benchmark.

### D22. Shorten Routes by Contiguous Cropping

**Status:** user-requested and artifact-confirmed on 2026-09-23.

Reduce actual driving time and 2 Hz recording volume by moving route starts later and finishes earlier. Preserve original waypoint coordinates, road/lane identities and the 2 m reference adjacency; retain 10 m straight and 2 m turn sampling with 12 m turn context. For routes 1–3 choose the closest dense points to 25% and 75% of original arc length. For route 4 choose the shortest slice with 40–50 working points, one or two complete turns, the entire recorded bridge crossing and at least 12 m after its exit. This yields one left turn before the bridge. For route 5 choose the shortest slice with 60–70 working points and two complete turns, retaining approach/exit context. This yields the original middle left/right pair. New start locations are lane waypoints rather than the original native spawn points and must pass actual spawning/driving validation.

Revision `20260923T160431Z-shorter-routes-b72a9d` contains lengths 110.000, 125.106, 122.838, 251.108 and 225.939 m with 12, 32, 32, 44 and 60 working points. Rename only the descriptive suffixes of routes 4–5 to `route_04_turn_then_bridge` and `route_05_two_turns`. Their dense source windows (inclusive) are 28–83, 32–93, 31–94, 34–158 and 19–132 respectively. The original signed source remains unchanged. `scripts/stage2_route_trim.py` reproduces selection and records source hashes.

All five shortened routes passed CARLA reconstruction, direct-`next(2.0)` adjacency, spawn, route completion, deviation, collision, timeout/stuck and post-finish-stop checks in `20260923T160409Z-shorter-routes-autopilot-b8548d`. Driving time excluding the 4 s stop observation fell from 186.70 to 88.85 simulation seconds over all five routes (52.41%). The same controller/seed was used as the historical comparison; no cameras were created. Actual new dataset size and full recorder wall time have not yet been measured.

This supersedes D16's adopted lengths/endpoints, D18's descriptive suffixes and D20's route source/pilot, while preserving route numbers, five-route coverage, weather matrix and all camera requirements. Stage-4 configuration now selects this validated revision; the four-turn/long-bridge geometries remain historical evidence.

### D23. Versioned SceneSpec and Restricted CARLA Executor

**Status:** accepted as the Stage-6 design after the Stage-5 primary-source review on 2026-09-24. The pre-API parser/validator/executor passed locally, then all three selected API variants completed the shared fixed pilot and six saved model SceneSpecs passed fresh-world CARLA execution on 2026-09-24.

Use a project-owned, versioned `SceneSpec` as passive data between an API-hosted LLM and CARLA. The model may select only operations, identifiers, spatial anchors, and parameters that the executor actually supports. A deterministic validator checks schema, enums, numeric bounds, blueprint availability, the fixed map/routes, spatial feasibility, and conflicts before any world mutation. A fixed executor maps accepted fields to allow-listed CARLA Python API calls; no model-produced Python or Scenic program is executed, and model output is never parsed with `eval()`.

After application, record and check the actual selected blueprints, transforms, visibility, requested event, and errors. Preserve the original request, raw response, parsed SceneSpec, resolved configuration, model/provider/settings, timing, retries, seeds, and outcome. A resolved configuration must replay without another LLM call. The map, five routes, and 18-sensor recorder remain controlled project components rather than model-editable fields unless a later explicit decision changes that boundary.

This accepts proposal P01 and adapts the common useful parts of ScenarioGen, TTSG, TrafficComposer, and ChatScene without importing their local-model, unsafe parsing, multimodal, or executable-DSL components. Local implementation evidence is `20260924T110210Z-local-straight-parked-vehicle-observer-fix-213a80`, its fresh-world replay `20260924T110353Z-local-straight-replay-ad721d`, and the two-vehicle `clear_day` case `20260924T110725Z-local-straight-composite-safe-af8031`. `20260924T123036Z-api-fixed-protocol-884ef7` then records all nine first attempts, and its `stage6_comparison.json` links every accepted model SceneSpec to a passing saved-provenance CARLA run. The bounded pilot does not establish provider-enforced strict-schema compliance, a statistically meaningful repeat rate, a provider price/cost, other routes/blueprints, or animal support.

### D25. Spend-Bounded First-Attempt Stage-6 Pilot

**Status:** accepted and artifact-confirmed on 2026-09-24; it is a pilot protocol, not a replacement for larger repeat studies.

Before the paid calls, fix exactly three model variants, three natural-language task types, one repeat, zero retries, a 60 s timeout and a 256-output-token ceiling. The resulting maximum is nine calls. The task set deliberately includes one valid simple SceneSpec, one valid composite SceneSpec and one moving-animal request that the current executor cannot support. Success means strict response parsing plus exact task correspondence; for executable specifications it additionally means a saved-provenance CARLA run with 18-camera validation, semantic-supported visibility and completed/no-collision route. A valid but misplaced SceneSpec is a failure; the adapter does not repair it. A correct structured animal refusal is a success for the impossible-request task and is not passed to CARLA.

The fixed run `20260924T123036Z-api-fixed-protocol-884ef7` has nine of nine first attempts passing. It preserves reported token usage and latency but assigns no cost because no dated provider price record was fetched. There are six passing saved-provenance CARLA executions, one per valid model/task response; a second GPT simple-scene replay completed after the orchestration handle returned and remains visible in the comparison instead of being selected away. This supersedes P06 only for this deliberately bounded Stage-6 pilot; later broader evaluation must declare its own budget and repeat count.

### D24. Narrow Pre-API Executor Envelope on the Straight Control Route

**Status:** accepted and CARLA-validated on 2026-09-24; expand only after new placement evidence.

For the user's initial Stage-6 work, the executor is deliberately limited to `Town01_Opt`, `route_01_straight`, the two measured Stage-4 weather profiles, and one to three static `vehicle.audi.a2` actors. The Tesla Model 3 is the fixed ego actor, not an LLM-selectable prop. Every prop position derives from a route-progress anchor, side and offsets; direct coordinates are forbidden in `SceneSpec`. In the tested route location, the right side stayed a driving lane through 55 m lateral probing, while the left-side 10 m placement was not driving lane and successfully spawned. A 35 m anchor nevertheless intersected static geometry and was rejected by CARLA. Therefore live preflight plus `try_spawn_actor` remains mandatory; a JSON-valid specification is not automatically executable.

The accepted local cases prove the selected one- and two-Audi placements, observer before/after views, 18-sensor visibility, no ego overlap/collision, completion of the 110 m route, clean world reload, and replay from stored `scene_spec.json`. They do not claim all anchors/offsets on this route, other vehicle blueprints, or any animal are valid. The actual constraints and fixtures are versioned in `configs/stage6_scene_editing.json` and `fixtures/stage6/`.

## Proposed Project Decisions

Implement these unless evidence calls for a revision. Do not attribute them to the assignment author.

| ID | Proposal | Validate before finalizing |
|---|---|---|
| P01 | Accepted as D23: LLM → validated SceneSpec → restricted CARLA executor | Stage 6 must validate the schema, operations, replay, and impossible requests |
| P02 | Superseded by D19: fixed 0.05 s world step, synchronous TM, frame-keyed 0.5 s sensor period | Revalidate at Stage-4 route duration and matrix scale |
| P03 | Superseded by D04: AV2 log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca` with preserved raw calibration | Reuse the signed calibration record in later dataset runs |
| P04 | Superseded by D13 for route selection; use direct `Waypoint.next()` routes and retain GlobalRoutePlanner only as a later fallback if Traffic Manager path submission requires it | Valid actor spawn, TM following, enough duration for events |
| P05 | At least two weather configurations per route | Time, disk, meaningful comparison, reproducible randomization |
| P06 | Around three LLM repeats per request/model | Cost and limits; fix count before running |
| P07 | Append-only pose log then final JSON conversion | Interruption recovery and no loss of final frame |

## Material Open Questions

| ID | Question | Resolve in | Do not treat as proven |
|---|---|---|---|
| Q01 | Git remote, external storage, access/quota | Stage 0 | Data survives Delete |
| Q02 | Actual map and road-marking coverage | Stage 1 | One Decals call removes every line |
| Q03 | Animal in package or compatible prebuilt extension | Early stage 1; decide before stage 7 | Python can import any FBX/GLB into packaged CARLA |
| Q05 | API endpoints, IDs, and access for three models | Before paid stage 6 work | A model in Codex is available through the project API |
| Q06 | Scene/weather/repeat matrix and data volume | Stages 3–4; revise before 6–8 | Earlier suggestion of 20 drives is mandatory |
| Q07 | Available physical/behavioural animal effect | Stage 7 | TM treats an arbitrary prop as a pedestrian |
| Q08 | Seasonality within API scope | Stages 1 and 4 | Rain and sunset model autumn/winter |
| Q09 | Publication readiness and Google Drive access | Stage 9 | Current accounts/connectors are available |

## Corrections to Earlier Chat Advice

- CARLA using the GPU supports proceeding, but does not prove recording from all cameras works.
- Town01_Opt is a candidate until confirmed in the selected image; Town01 remains the requirement.
- 50 waypoints and 100 m were suggestions. The only required minimum is 10 sequential waypoints; drives must still be meaningful.
- Five routes with five unique weather settings confounds weather with route. Comparisons need repeated route–weather pairs.
- Different models may produce the same scene. Record response origin separately from canonical scene configuration; do not treat duplicates as independent map versions.
- Asphalt-colour texture replacement may change RGB while retaining road markings in semantic output. It is not automatically removal.
- An animal moved with `set_transform` does not automatically have realistic dynamics, collisions, or trigger braking. Validate each effect.

## Adding Decisions

For each new decision record: ID, date, status, evidence, selected choice, alternatives, validation/artifact, and consequences. When changing a decision, mark the old one superseded and retain the reason. Keep only current state in `STATUS.md`.
