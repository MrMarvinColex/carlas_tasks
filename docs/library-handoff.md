# Library Foundation and Implementation Handoff

**2026-10-02; implemented offline foundation, live migration pending.** The user authorized implementing the difficult reusable parts and leaving bounded tasks for later models/developers. This is the working entry point for that continuation, not mandatory startup context. [Decision R03](decisions.md) records the rationale; [validation evidence](../artifacts/library-foundation-2026-10-02.json) records actual checks.

## Outcome and scope

One installable Python package now owns rig specifications, pure AV2 adaptation, frame assembly, the recording loop, resource ownership and lossless capture writing/validation. The same pipeline was exercised with 1, 3 and 9 camera pairs. Existing stage executors still run their established loops; only their AV2 camera calculation delegates to the new pure implementation. The new generic recorder has **no live CARLA backend yet** and is not the default experiment runner.

The library is intentionally small: one package, standard-library-only offline core, no plugin framework, deep config inheritance, provider registry or separate library repositories. Version 0.1 contracts are a reviewed starting point; demonstrate a failing scenario before redesigning them. Do not build placeholder abstractions for tasks that have no consumer.

## Dependency direction and existing interfaces

```text
CLI / compatible stage wrappers
             |
experiment orchestration (identity, attempts, acceptance, registry)
             |
recording.record(backend, rig, policy, sink, hooks)
       |             |                |
backend boundary  frame assembly   dataset sink
       |             |                |
CARLA objects    detached bytes     PNG + ordered poses
```

The package never imports stage scripts. A boundary test enforces static imports; do not bypass it with dynamic loading or sys.path tricks. Optional simulator imports belong in the future backend. Model calls belong in generation, outside scene replay and the frame loop.

| Module | Implemented contract | Read with |
|---|---|---|
| [rigs](../carla_tasks/rigs.py) | `Pose`, `CameraSpec`, `RigSpec`; `resolve_av2_camera/rig` | [rig tests](../tests/test_rigs.py) |
| [capture](../carla_tasks/capture.py) | `Snapshot`, detached `ImagePacket`, `CapturedSample`, bounded `FrameInbox` | [assembly tests](../tests/test_capture.py) |
| [recording](../carla_tasks/recording.py) | `RecordingBackend`, `RecordingSink`, `PreparedSession`, `CapturePolicy`, `OwnedResources`, `record` | [pipeline tests](../tests/test_recording.py) |
| [capture_io](../carla_tasks/capture_io.py) | `CaptureDirectory`, `validate_capture` | Same pipeline tests |
| [experiments](../carla_tasks/experiments.py) / [registry](../carla_tasks/registry.py) | Matrix vs measurement identity; repeat and copy lifecycle | [experiment tests](../tests/test_experiments.py), [registry tests](../tests/test_registry.py), [CLI tests](../tests/test_cli.py) |

Rig v1 means CARLA vehicle coordinates, metres, Euler roll/pitch/yaw in degrees, perspective projection, paired RGB/semantic streams and one shared cadence. Camera count and dimensions are declared, not inherited from AV2. The AV2 adapter receives actual vehicle rear axle and bounding box as arguments; pure calculation does not establish those measurements. It preserves projection limitations in evidence. The sample [three-camera rig](../configs/rigs/three_camera_v1.json) is an offline example, not a physically verified vehicle installation.

`PreparedSession` contains the applied rig, initial snapshot, first capture frame and environment evidence. Applied rig changes must be resolved explicitly before capture; silent camera relocation is rejected. `RigSpec.frame_stride` requires an integral sensor/world period ratio. Only the backend's `advance()` ticks after preparation, exactly once per call. Hooks receive the previous snapshot before that tick; each recorded pose comes from the resulting snapshot. No latest-pose lookup when a delayed image arrives.

The backend must establish sensor phase during bounded warmup. The kernel never assumes that absolute `frame % stride == 0`. `first_capture_frame` must be after the initial snapshot and within one sensor period. Packets from earlier warmup frames are ignored; missing required frames, duplicates, wrong timestamps/dimensions, unexpected cadence, callback conversion errors and buffer overflow fail capture. Callbacks must route exceptions to `inbox.fail`; do not let CARLA swallow them silently.

Resources are registered immediately after acquisition and released in reverse order on success, setup failure, runtime failure or cancellation. Register world restoration **before** a mutating operation that could fail; existing `configure_synchronous_world` both applies settings and ticks before returning, so a new backend cannot defer registration until after that helper succeeds. Register stop-listening after actor destruction callbacks so listeners stop first. Cleanup failures are retained alongside the primary error. External containers/worlds/actors are never assumed owned.

`CapturePolicy.max_samples` is a cap. Optional `stop_after_sample(snapshot)` requests a stop on a complete sample boundary. Results distinguish `termination=condition` from `sample_limit`; neither means an accepted route without its controller's evidence. This accommodates routes whose completion frame is not known in advance. A requested repeat always runs a new simulation.

Sensor and writer buffers have separate byte/count limits; the writer blocks further ticks when full, commits frames in acquisition order and drains before finalization. Limits cover retained source buffers, not the whole process RSS: encoding temporaries and concurrently executing callbacks add memory. Measure real peak usage before tuning AV2 throughput. Cancellation is checked between ticks; sensor waits have a timeout. Python cannot kill a blocked writer thread, so filesystem hangs require process supervision. Do not add silent packet dropping or unbounded writer queues to conceal pressure.

## Capture output and experiment acceptance

`CaptureDirectory` requires a fresh directory, preferably `runs/RUN_ID/capture/`. Its format is explicitly `research-capture-v1`:

- `rig.json` and `capture_config.json`: resolved rig, policy, initial pose/phase and backend evidence.
- `images/CAMERA/{rgb,semantic}/FRAME.png`: RGB without channel swapping mistakes; lossless raw semantic IDs from CARLA's BGRA red channel.
- `samples.jsonl`: ordered, flushed records after all images of each sample are written.
- `transforms.json`: complete journal snapshot published only after successful capture/writer drain/resource cleanup.
- `capture_result.json`, or `capture_failure.json` with error and cleanup evidence. Failure evidence prevents validation even if a finalization operation partially succeeded.

This format does not pretend to be historical Stage-3/4 transforms. `capture-check` verifies declared streams, poses, cadence, dimensions and PNG data. It does **not** verify route coverage, collisions, visual ego occlusion, scene success, full run manifest or external backup. M2 must explicitly integrate those acceptance checks before creating a complete registry entry. Partial images/poses remain diagnostic evidence and must not be automatically retried into the same output directory.

## Run the offline acceptance example

From the repository root, with Python 3.9+ and a **new** output directory:

```sh
python3 -m carla_tasks rig-check configs/rigs/three_camera_v1.json
python3 examples/record_synthetic.py --output /tmp/carla-synthetic-UNIQUE --samples 3
python3 -m carla_tasks capture-check /tmp/carla-synthetic-UNIQUE
python3 -m unittest discover -s tests -p 'test_recording.py'
```

The example creates synthetic pixels/poses, marks them as such and never registers an experiment. It requires neither CARLA nor network access. Change the rig JSON, not the recording loop, to exercise another camera count.

Packaging metadata lives in `setup.cfg`; `pyproject.toml` selects setuptools and `setup.py` supports older offline toolchains. In a chosen virtualenv, an editable install is optional: `python -m pip install --no-deps --no-build-isolation -e .` (requires already installed setuptools/wheel). Repository configs/inputs/docs stay in Git, outside the wheel. No dependency installation is needed for source-tree offline work. Packaging checks should copy only these three packaging files plus `carla_tasks/` to a temporary build directory: older pip versions copy the entire input tree, including ignored runs, for non-editable builds. Inspect wheel metadata and import it outside the checkout; exit code alone missed an empty wheel from unsupported metadata during development.

## Ordered follow-up tasks

Complete and commit one task at a time. Read this document plus the listed modules/functions; do not reload assignment history. Keep local changes separate from live acceptance. Capture checks already pass: repeat the full suite after meaningful integration changes, not after every read/status query.

### M1 — CARLA backend and one short pilot

**Depends on:** current foundation. **Read:** recording/capture/rigs interfaces, `scripts/stage4_baseline.py:calibration_and_sensors`, `scripts/stage3_recording.py:pose_from_snapshot`, runtime settings helpers. Keep routes, API calls and batch scheduling out of this task.

Implement one `RecordingBackend` with a lazy CARLA import. First accept a prepared world/ego with explicit ownership, or a preparation callable that registers acquisitions in `OwnedResources`; do not introduce a generic dependency container. Apply the requested fixed delta/substep constraints. Spawn every stream in `rig.streams` with rigid attachment and required dimensions/FOV/cadence/lens settings. Reject unsupported/mismatched required attributes rather than silently ignoring them. Preserve actual actor attributes/transforms, client/server/image/map and vehicle geometry in evidence. Check generic rig origins/optical axes against the actual vehicle box and validate visual occlusion in the pilot.

Use a bounded warmup deadline/frame limit. Observe at least two common emission frames for all streams, validate the measured period against stride and establish the next capture frame relative to the stopped world's current snapshot. Do not infer phase from wall time or advance simulation in a listener/background thread. A sensor phase disagreement is an explicit unsupported setup/error. During handoff, keep callbacks bounded and discard only known pre-recording frames. Detach bytes inside callbacks and latch conversion failures. `advance` verifies the returned world snapshot frame equals `world.tick()` and extracts ego from that snapshot.

**Local acceptance:** fake CARLA objects exercise partial spawn failure, missing attributes, wrong sensor phase, callback failure, one tick per advance and full cleanup after setup/tick errors. Reuse `record` and `CaptureDirectory`; do not create a second loop/writer. **VM acceptance:** one small stationary/moving three-camera recording, complete capture validation, inspect physical orientation/ego occlusion, then an AV2 pilot with preserved actual calibration evidence. Record exact limitations if no VM is available. No automatic matrix rollout.

### M2 — Baseline route/controller and experiment integration

**Depends on:** M1 local contract; live acceptance gates switching defaults. **Read:** `stage2_autopilot_routes.py:RouteDefinition/load_route/nearest_route_state`, Stage-4 weather/route/collision/acceptance/finalization logic, experiments/registry.

Mechanically move route and weather functionality into focused package modules. Keep legacy wrappers delegating and preserve geometry/control behavior first. Route control and accepted scene actions use `before_step`; completion is sampled by `stop_after_sample`. Save the full trajectory/collision evidence needed for route coverage, not just sampled camera poses. Distinguish route reached, collision, timeout and sample cap. Add a rig-aware experiment entry that fingerprints the fully resolved rig plus selected route/scene/assets and actual implementation/runtime dependencies; do not assume the old AV2-only manifest already identifies custom rigs.

Add a validator for route coverage/collisions/ego occlusion and a finalizer that covers new capture files, resolved/applied configs and environment in the run manifest. Extend registry import to accept an **explicitly versioned** new experiment format after those checks; it currently expects baseline-specific files. Preserve the old import path. Do not fabricate `baseline_validation.json` around synthetic capture or add a shortcut to mark it complete. One CLI route serves baseline and variants; stage paths become thin compatibility wrappers after parity checks.

**Acceptance:** one baseline pilot and one three-camera pilot on the same controlled route/weather; same-frame poses and lossless IDs; requested repeat adds a drive; another matrix weather does not invalidate unchanged cells; failed/capped route cannot resume as complete; Mac verification survives Git-only restore on another VM. Use [VM workflow](vm-workflow.md).

### M3 — Scene actions, then generation adapters

**Depends on:** M2. First move validated static scene execution from `stage6_local_scene.py` without changing policy; then animal actions from `stage7_animal_probe.py`. Actors belong to the session, motion uses the common tick hook, and image visibility/semantic acceptance stays separate from spawn success. Store actual adaptations and scene evidence. Retain both static v1.0 and animal v1.1 policy boundaries; the current `scene-check` handles static scenes only.

Only after replay is independent, extract provider calls/provenance from `stage6_api_adapter.py`. A generation command stores every request/reply/attempt/settings/timing and produces validated passive SceneSpec. Replay consumes a saved accepted scene without another API call. Never execute model-generated code; retain allowlists and credentials outside Git/logs. Test provider adapters with stored/synthetic responses; real calls require the intended API task/environment. Commit scene replay and generation extraction separately.

### M4 — Remove remaining cross-script imports and tune measured costs

**Depends on:** successful migrated consumers. Use `rg` to locate remaining `from stage...` imports, replace consumers with package APIs, and retire duplicate implementations only after their callers have migrated. Do not delete compatibility commands referenced by evidence. Enforce the dependency boundary in tests. Measure GPU callback latency, encoding, disk writes, peak memory and API latency separately before adding codecs/caches/concurrency. Keep requested repeats independent of reusable deterministic preparation.

Authored Unreal maps/build assets, asynchronous multi-rate sensors, fisheye/depth modalities, distributed orchestration and a general preset override system are separate future requirements. They are not hidden tasks inside M1–M4.

## Commit rationale and recovery

Original accumulated changes were preserved separately: `2110973` portable inputs; `552481c` pure extraction; `046279c` execution supervision; `bf3695f` memory/history and audit. `f7205bd` corrected audit F1–F5. `ecef1a8` added this library foundation. These are local commits; no push/publication occurred. The pre-existing `.gitignore` edit remains uncommitted and separate.

The split makes it possible to review behavior changes independently from archived documentation and input payloads. Full commit bodies explain validation/limits. Do not amend earlier evidence or silently upgrade historical run identities. Schema-2 measurement identity and the new capture format have distinct version boundaries; neither rewrites historical results.

After each task, replace STATUS with exact facts/next action and a brief linked worklog entry. Keep implementation detail here or in the relevant module tests, not in mandatory startup files. Save code/config/inputs and small proof through Git; move only needed large output with rsync. Do not launch a retry based on outer tool completion or treat local success as verified off-VM preservation.
