# Delivery Plan: Fixed Stages 0–9

Purpose: each stage can be assigned to a new Codex task with “complete stage N.” Before work, read `AGENTS.md`, `STATUS.md`, `requirements.md`, and `decisions.md`. Do not renumber stages; refine substeps as needed. Stage state belongs only in `STATUS.md`.

For every stage: preserve evidence, update work log/status/report, and move valuable results off the VM. Names for future scripts and directories below are proposed structure, not implemented code.

## Dependencies and GPU-Cost Control

- Main chain: 0 → 1 → 2 → 3 → 4 → 8 → 9.
- Stage 5 is GPU-independent and should inform the final design of stage 6.
- Stage 6 requires verified operations from stage 1, API access, and an evaluation protocol. Stage 7 uses its architecture and the early asset check in stage 1.
- Stage 8 requires the baseline dataset from stage 4 and verified scene changes from stages 6–7.
- An early animal blocker does not prevent routes, sensors, or the review; it remains open and prevents stages 7–9 from being fully complete.
- Do literature work and report writing on the Mac whenever possible. Batch CARLA work. Do not treat an earlier six-day calendar estimate as a guarantee: less than a week remains before the working deadline on 16 September.

## Stage 0. Reproducible Environment and Data Safety

**Assignment coverage:** preparation for all items; beginning of 1.1–1.2.

**Inputs:** this documentation package; access to the current VM; user-reported successful launch of `carlasim/carla:0.9.16`. Git, storage, and LLM access are not yet confirmed.

**Work:**

1. Inspect `~/carla_test_task`, Git state, containers, and processes. Integrate the documents without destroying existing user files. Record the actual state.
2. Configure private Git using the user-provided remote and select external result storage. If neither is available, prepare the local structure and ask only for the missing decision.
3. Create reproducible dependency setup, an isolated Python environment, and CARLA start/stop scripts. Proposed names: `scripts/setup.sh`, `scripts/run_carla.sh`, `scripts/stop_carla.sh`; record final names in README.
4. Record Python, client library, server build, and image versions. Do not reinstall a working driver by default. Repeating setup must not damage data.
5. Run a small client connection test that obtains one RGB frame. Save versions and a log; this does not validate 18 cameras.
6. Implement common run tracking: unique run ID, configuration, log, metadata, and state. Prepare export, checksum manifest, and external-copy verification.
7. Transfer a small test set to the Mac or selected storage and verify size and checksums there. Record bootstrap/recovery commands and a safe `.env` restoration method without exposing keys.

**Result:** environment scripts, reproducible instructions, recorded dependencies, a short verified run, and a verified external copy.

**Acceptance:** startup and client connection can be reproduced; the test frame opens; repeated setup is safe; documentation contains required steps and external destinations; an off-VM copy is verified. If a truly new-VM recovery has not been tested, state that separately and test it on the next rental; do not delete the current VM merely to test it without user instruction.

## Stage 1. Map and API Capabilities

**Assignment coverage:** 1.1–1.4; early investigation of item 4 risk.

**Inputs:** working client, CARLA, and stage-0 result-storage mechanism.

**Work:**

1. List maps and load Town01. Check whether Town01_Opt exists and is justified for layer operations; save the actual map name and versions.
2. Exercise basic World/Actor/Blueprint operations in a small example. Verify weather changes in rendered frames, not only API-returned values.
3. Save baseline RGB and semantic frames from several places: a straight road, an intersection, and stop lines/crosswalks where present.
4. Inspect environment objects and road-marking categories. Test targeted object hiding, then layers if needed. Do not assume `RoadLines` or `Decals` covers the whole map.
5. Verify results visually and through raw semantic IDs. Record remaining markings, road/topology preservation, and waypoint availability. Do not call texture recolouring removal without semantic verification.
6. Search early for animals in blueprints, available assets, and documented compatible packages. A matching name does not prove rendering or collision. If no usable asset exists, record the risk and options without independently switching to Unreal.

**Result:** verified map-editing method, before/after frames, a catalogue of available operations/assets, and an animal-availability record.

**Acceptance:** Town01 is loaded; road markings are hidden in tested RGB/semantic observations while road geometry and navigation remain intact; the inspection coverage is described. If complete removal is not achieved, item 1.4 remains blocked. Animal availability has a clear status; its absence does not block the remaining engineering work.

## Stage 2. Five Routes and Autopilot

**Assignment coverage:** 1.5–1.6.

**Inputs:** Town01 and basic operations; unresolved road-marking limitations are explicit.

**Work:**

1. Sample the full road network at a declared resolution and display waypoints with DebugHelper. “All waypoints” means the complete finite sample at that resolution.
2. Select five distinct connected routes. Use verified public routes or construct them on the installed map; record their provenance.
3. Save waypoint/coordinate lists, start/end, road/lane identifiers where available, resolution, length, and selection seed. Every route must have at least 10 sequential points.
4. Spawn the vehicle, enable Traffic Manager, and verify path submission, synchronous mode, intersection behaviour, and no unintended post-finish continuation.
5. Implement finish, timeout, stuck/collision handling, and route-completion measurements. Drawn points do not prove the vehicle drove through them.
6. Run all five routes, saving trajectory, stop reason, and an overview image. Remove debug drawings before camera recording.

**Result:** five route files and validated autopilot runs.

**Acceptance:** every route has ≥10 connected waypoints and a valid spawn; actual driving is checked; deviations and failures are recorded. Arbitrary disconnected points do not qualify.

## Stage 3. Argoverse 2 Cameras and Synchronous Recording

**Assignment coverage:** 1.7–1.8.

**Inputs:** a short validated route, run metadata, and an export destination.

**Work:**

1. Select one published AV2 calibration; save its source, log ID, raw parameters, and retrieval conditions. Do not download the full Sensor Dataset just to obtain calibration data.
2. Define AV2 ego/sensor and CARLA vehicle/camera coordinate systems. Compute transforms with the actual vehicle-origin relationship; validate orientations and locations numerically and visually.
3. Create nine rigid RGB/semantic pairs. Preserve the portrait `ring_front_center` orientation. Document extrinsics, intrinsics, FOV, resolution, and projection limits honestly.
4. Use fixed-step simulation and synchronous Traffic Manager. Record every 0.5 seconds of simulation time; an initial candidate step is 0.05 seconds, pending validation.
5. Assemble images by frame ID and match them to ego pose from the same snapshot. Handle GPU-sensor delivery lag and drain queues after the final frame. Do not use a current transform in a delayed callback.
6. Save lossless RGB, raw semantic class IDs, and separate colour previews. Use class semantics from the installed version.
7. Produce final `transforms.json`, metadata, calibration, and an integrity report. Support interrupted runs without mislabeling them complete.
8. Begin with one view, then validate all 18 sensors over a short drive. Measure wall time, VRAM/RAM, bytes per simulation second, and recording throughput.

**Result:** a complete short dataset example, sensor configuration, and validator.

**Acceptance:** every accepted time point contains 9 RGB + 9 semantic images and an ego transform; simulation-time intervals are 0.5 seconds within a documented tolerance; frames align; files open; cameras do not look into the vehicle body. Account for all drops and excluded warm-up frames. The final JSON is valid and the sample has a verified off-VM copy.

## Stage 4. Baseline Dataset

**Assignment coverage:** 1.9.

**Inputs:** five routes and the validated 18-sensor rig; road-marking removal is complete or its limitation is explicitly accepted.

**Work:**

1. Fix the baseline run matrix and disk/time limits. A suggested start is each of five routes under two weather configurations; this is a project proposal, not a PDF requirement.
2. Use distinct weather parameters and reproducible randomization, saving actual values. Do not call rain or sunset “winter” or “autumn” without a seasonal simulation.
3. Save the baseline scene without road markings, camera rig, vehicle, routes, and control settings. It is the control condition for later edits.
4. Run drives, validate every run, and export in batches. Measure one run before extrapolating total size; reserve disk for temporary files and archives.

**Result:** baseline dataset over five routes and multiple weather conditions.

**Acceptance:** the chosen matrix is complete; all accepted records pass validation; failures are retained; weather settings are reproducible; off-VM copies are verified. The report includes samples and measured size.

## Stage 5. Literature and Repository Review

**Assignment coverage:** 2. No GPU required.

**Work:**

1. Find primary papers and author repositories on language-driven CARLA scene/scenario editing. Include close methods only when their difference is stated.
2. Record task, input/output, LLM role, world-editing method, CARLA/version support, code availability, license, Unreal dependence, and reproducibility.
3. Distinguish scenario generation, 3D-geometry editing, and post-processing of rendered images. Do not represent video/image post-processing as physical-scene editing.
4. Justify the project’s validated Python-API approach. Preserve links and access date; do not copy long source text.

**Result:** report section and source list in the knowledge base.

**Acceptance:** the review answers the assignment question, compares capabilities and limits, and explains applicability to this project. Select source count for substance; explicitly mark missing implementations and unverified claims.

## Stage 6. LLM-Driven Scene Editing

**Assignment coverage:** 3.

**Inputs:** verified stage-1 operations, stage-5 conceptual review, API access, and an agreed trial-spend limit. Without API access, implement and validate local parsing only; do not invent model outputs.

**Work:**

1. Select real model IDs for the three variants and record provider, date, generation/reasoning settings, and limits. Model IDs mentioned in chat are not confirmed access.
2. Define a versioned SceneSpec: target map, allowed operations, parameters, placement anchors, and seed. Specify unsupported actions and how impossible requests are handled.
3. Implement a common API interface, validation, bounds on object count/coordinates, world application, and scene reset. Save raw responses and every attempt; do not hide corrections.
4. Before measuring, fix equal prompts, success criteria, repeat count, timeouts, and retry rules. Three repetitions per request/model is an initial candidate; final volume depends on limits.
5. Validate meaningful object/environment edits, not only weather changes. Include simple, composite, and impossible requests to assess correct refusal.
6. Measure full API latency separately from validation and CARLA application. Measure time to first token only where streaming is actually supported. Record cost only when usage and pricing are available.
7. Validate JSON, executability, spatial correspondence, and visible result. Save before/after frames and errors. Treat API infrastructure as a latency factor, not only the model.

**Result:** executor, prompt set, reproducible edited-scene configurations, and a comparison table.

**Acceptance:** three accessible variants follow one protocol, or each unavailable variant is explicitly incomplete; metrics use saved attempts; scenes replay from configuration without another LLM call. Keep first-attempt success separate from success after corrections.

## Stage 7. Moving Animal

**Assignment coverage:** 4.

**Inputs:** a validated animal asset/blueprint and the stage-6 executor. If no asset is available, resolve that exact blocker within U02/U06 constraints before starting the stage.

**Work:**

1. Validate mesh/blueprint, license, package compatibility, and runtime use. For an external package, preserve source and version. Do not assume Python can import arbitrary FBX/GLB files into a packaged CARLA build.
2. Implement simple motion with a trajectory and speed in simulation time. Leg animation is optional. Validate height, collision geometry, and absence of teleport-like jumps.
3. Validate visibility in agreed cameras and identify the semantic class ID. Do not promise a dedicated animal class if the installed label system does not provide one.
4. Define before evaluation what counts as an effect: visible occlusion, physical collision, or measured vehicle response. Validate these separately.
5. Give different LLMs an equal set of requests for animal appearance, motion, timing, and speed. Save scene configuration, trigger, and trajectory. Keep a detailed actor log separately from the ego JSON if needed.
6. Compare request execution, correct placement/motion, visibility, and actual effect. Lack of Traffic Manager braking is a result, not a reason to claim a response.

**Result:** reproducible animal scenario and cross-model results.

**Acceptance:** a recognisable animal exists in the real scene, moves, appears in saved camera data, and has a measured stated effect; different LLMs follow a shared protocol. An unvalidated asset, pedestrian proxy, or post-render image does not complete the stage.

## Stage 8. Repeated Drives and Analysis

**Assignment coverage:** 5; repeat 1.5–1.9.

**Inputs:** baseline dataset, validated scene edits, and animal scenario.

**Work:**

1. Fix the scene-version set: baseline, item-3 changes, item-4 changes, and combined variant if needed. For each, preserve originating model/attempt. Do not select only attractive successful examples as evidence of LLM quality.
2. Recheck and visualize waypoints and applicability of the same five routes for every version. Do not silently change routes if an edit blocks passage.
3. Run the same route/weather matrix with the same rig and control parameters. Validate matched initial conditions; identical seeds do not ensure identical trajectories after scene changes.
4. Count LLM attempts separately from dataset drives. A saved scene can be replayed without a new API call.
5. Compare route completion, time, collisions, object visibility, data properties, and instruction fulfilment. Align frames by route position where needed, not just frame number.
6. Preserve accepted recordings, summaries, and constraints. Verify external copies.

**Result:** dataset for baseline and edited scenes with evidence-based analysis.

**Acceptance:** covers both item-3 and item-4 changes; all five routes follow the fixed protocol; failed drives are described; conditions do not change silently; data completeness is validated. A failed scenario may be a research result but does not replace a missing record where one was required.

## Stage 9. Final Delivery

**Inputs:** results from earlier stages or an explicitly accepted list of limitations.

**Work:**

1. Complete the report by PDF item: architecture, versions, methods, comparison, metrics, screenshots, failures, and conclusions. Remove or mark every unfilled field.
2. Prepare a reproducibility README and dataset-format description. Verify the documented commands against current code.
3. Prepare a public-Git set: exclude keys, private endpoints, large data, and the assignment PDF unless publication rights are confirmed. Check Git history for already-added secrets.
4. Prepare the report and dataset for Google Drive with manifests and checksums. Check quota and access. Do not assume Google Drive is connected.
5. After explicit instruction, publish the prepared materials and verify links and reader permissions. Store actual URLs in the status and report.
6. Prepare project handoff and safe rental shutdown using the runbook. Deleting the VM remains a separate user action or direct instruction.

**Result:** completed report, published code and dataset, verified links, and reproduction instructions that do not require the current VM.

**Acceptance:** every PDF item has evidence or an explicitly accepted limitation; code is public; report and dataset are available through verified links; the result can be restored without the current VM. Until publication is authorized and completed, mark the stage ready to publish rather than `DONE`.
