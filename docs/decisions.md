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

**Status:** user clarification.

Use nine AV2 positions: seven ring and two stereo. Each has RGB and semantic sensors, for 18 streams at 2 Hz of simulation time. Position and orientation must follow one selected real calibration after coordinate conversion; a symmetric arbitrary layout is insufficient. The exact calibration source is still open. Do not claim optical equivalence without verifying intrinsics and projection model.

### D05. Separate Ego Transform

**Status:** user clarification and PDF deliverable format.

Each completed drive has one `transforms.json` containing the vehicle position/orientation time series. Animal data is kept separate from ego pose. Initial state, trajectory, speed, and trigger are stored in scene configuration; include detailed actor logging only where analysis needs it.

### D06. A Real Animal With the Simplest Sufficient Motion

**Status:** user clarification; feasibility not yet confirmed.

Leg animation is unnecessary, but the object must look like an animal, exist in the 3D scene, move, and affect the scene. Define the effect before evaluation. Visibility, physical collision, and Traffic Manager response are different checks. If no suitable asset exists, discuss a changed approach. A pedestrian is valid for debugging but does not complete the animal requirement.

### D07. Three API-Only LLM Variants

**Status:** user clarification; providers and IDs remain open.

Compare GPT-Astra, a Qwen model around 27B, and one around 8B. `gpt-6-astra`, `Qwen/Qwen3.8-27B`, and `Qwen/Qwen3-8B` were candidates in the discussion; real API access is unverified. A public model card does not guarantee an endpoint. Different Qwen generations make this more than a parameter-count comparison, and conclusions must acknowledge that.

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

## Proposed Project Decisions

Implement these unless evidence calls for a revision. Do not attribute them to the assignment author.

| ID | Proposal | Validate before finalizing |
|---|---|---|
| P01 | LLM → validated SceneSpec → restricted CARLA executor | Schema must cover real operations and impossible requests |
| P02 | Fixed world step, synchronous TM, sensor period 0.5 s | 18-camera performance, frame delivery, physics substeps |
| P03 | One concrete AV2 calibration with preserved raw data | Source/log ID, ego origin, rotations, intrinsics compatibility |
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
| Q04 | Specific calibration and vehicle origin | Stage 3 | Copying xyz without conversion reproduces AV2 |
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
