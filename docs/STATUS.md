# Current Project Status

Last inspected: **2026-09-19 16:30 UTC**; user timezone: Europe/Moscow.

## Current Position

Stage 0 acceptance is complete. The actual project root is `/home/Ubuntu/carlas_tasks` (not the historical `~/carla_test_task` path), under user `Ubuntu`, branch `Dev`; the private `origin` is reachable and its former `00_-_stage` branch was renamed to `Dev` on 2026-09-17. `origin/main` remains at the historical `0e52c6a`; stage work is intentionally accumulated on private `Dev`.

The reproducible client uses `.venv` with Python 3.10.12 and `carla==0.9.16`. The local image is `carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953`; the server/container versions were both 0.9.16. Run `20260916T210617Z-carla-smoke-beb230` captured and visually inspected one 800×600 RGB PNG, wrote a manifest, and passed local manifest verification. Its default map was `Town10HD_Opt`; this does not satisfy the separate Town01 test in stage 1. The `carla-server` container created for that run was stopped; no CARLA container is running.

**External-copy evidence:** the user ran `rsync` from Mac via the `carla-vm` SSH alias to `/Users/madness/Научка/CARLA/runs/20260916T210617Z-carla-smoke-beb230/`. The dry run listed 7 entries; the transfer completed; Mac-side SHA-256 validation reported `OK` for `config.json`, `metadata.json`, and `rgb/front.png`. The destination and manifest are registered in `artifacts/index.csv`.

The stage-0 implementation is preserved in the private `origin/Dev` history (initially commit `ce26b8e`); no pull request, merge to `main`, visibility change, or publication was performed.

The maintained environment entry points are `scripts/preflight.sh`, `scripts/setup.sh`, `scripts/run_carla.sh`, and `scripts/stop_carla.sh`. `scripts/preflight.sh` was rerun successfully after the move at 21:27 UTC. The older `env_setup_and_tests` copies were removed because the client-less smoke test was superseded and the tmux helper was unrelated to the project.

**Stage-1 result:** `Town01` and `Town01_Opt` are present and loaded successfully in CARLA 0.9.16. The basic World/Actor/Blueprint lifecycle passed; weather changes were visible in RGB; the Town01 library contained 214 blueprints (41 vehicle, 52 walker, 19 sensor) and no names matching the documented animal-candidate pattern. This is evidence that an animal is not available through the exposed blueprint library, not proof that no compatible prebuilt extension exists.

**Stage-1 road-marking result:** base `Town01` direct RoadLines hiding is semantic-only in the captured RGB views, and Decals/texture variants failed. However, direct `World.enable_environment_objects(RoadLines_ids, False)` on the installed `Carla/Maps/Town01_Opt` removed the visible yellow markings in three identical-position RGB pairs and raw semantic class ID 24 at all three observations: straight road 604→0 pixels, intersection 512→0, and traffic-control location 550→0. A driving waypoint remained available at each location; `Town01_Opt` topology was 160 edges. The actual selected map for later runtime work is therefore **`Town01_Opt`**, recorded explicitly rather than silently substituted for the required Town01. This is tested coverage, not a map-wide claim: the API returned no crosswalk point, so crosswalk/stop-line coverage remains unclaimed. Exact results and visual reviews are in the six local run directories registered below.

The direct Town01_Opt one-location review was initially recorded incorrectly as a failure; the paired PNGs show that the markings had disappeared. Its correction and the independent three-location confirmation are preserved rather than rewriting history. A user-requested supplementary check of the old smoke view is not yet an observation: the old frame is from `Town10HD_Opt`, not the selected map, and its vehicle transform was not recorded. A new first-free-spawn reproduction attempt opened CARLA ports but the server did not answer `get_world()` within repeated 5–20-second timeouts, so no frames were created and the container was stopped. The new reusable probe is retained as untested code.

**Stage-2 route-selection result:** run `20260918T121645Z-town01-opt-routes-clean-debug-95bdcf` loaded `Carla/Maps/Town01_Opt`, re-applied direct hiding to its 25 returned RoadLines objects, and sampled the complete finite `Map.generate_waypoints(2.0)` result (3,266 waypoints). A seeded native-spawn-point procedure selected five distinct routes of 60 driving waypoints each, 114.841–121.110 m long. Every one of the 295 route edges was independently rechecked as a member of its predecessor's `Waypoint.next(2.0)` result. The run contains the complete network sample, five route JSON files, a route index, and clean temporary DebugHelper line views of each route; its debug shapes were cleared before exit. A controlled diagnostic proved that CARLA 0.9.16's `draw_point` primitive, not RoadLines hiding, created black road-texture occluders in the previous nadir RGB views. Full waypoint points are still submitted to DebugHelper for 0.5 simulation seconds, but are cleared before any RGB capture; route screenshots use `draw_line` only. This proves construction and map connectivity only: no ego actor, Traffic Manager, path submission, or drive completion has been run. No CARLA container is running. New data runs must be copied to the same Mac hierarchy and checksum-verified before the VM is treated as disposable.

**Stage-2 completed drive validation:** the user then requested that the less complex bridge route become number 4 and the four-turn route number 5. Immutable revision `20260919T154916Z-route-numbering-swap-b5e941` proves that only the identifiers/order changed; all geometry fields are byte-for-byte inherited in meaning from the approved source. One Tesla Model 3 was spawned at the start of each renumbered route in synchronous `Town01_Opt`, after reapplying direct hiding to 25 RoadLines objects. The final run `20260919T154938Z-tm-autopilot-renumbered-routes-aac495` completed all five routes, with finish distance 7.20–7.93 m (criterion ≤8 m), maximum route deviation 0.997–1.247 m (limit ≤15 m), zero collision events, no timeout/stuck result, and a stopped vehicle after each finish. Its 19 signed files passed local entry-by-entry verification. The earlier `set_path` diagnostics remain retained. This meets Stage-2 items 5–6; no cameras or dataset imagery were created. The CARLA container is stopped.

**Stage-3 local validation result:** official raw extrinsics and intrinsics for AV2 Sensor log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca` are preserved with source URLs and SHA-256. The recorder aligns the AV2 rear-axle origin to the Tesla rear axle, converts AV2 ego/optical axes into CARLA, and applies a declared +0.5 m height adaptation after an exact-height pilot exposed the Tesla hood. Run `20260919T162408Z-av2-all-cameras-short-247e3f` recorded four complete 2 Hz time points from all nine RGB/semantic pairs (18 sensors): 72 required images, 36 palette previews, and four same-frame ego poses. All 108 PNGs passed CRC/decode/dimension checks, intervals were 0.5 s, no sensor drops/duplicates/late events occurred, and contact sheets passed visual review with no ego body. Its 119 signed files occupy 165,463,137 bytes and its manifest SHA-256 is `8a203ea291a126682997bafbfb7816cabad7d1eb33cf6188ce0a10f1d2915e61`. This is a short rig check, not a complete Stage-4 route. The CARLA container is stopped.

**Next action:** copy `20260919T162408Z-av2-all-cameras-short-247e3f` to the selected Mac hierarchy and verify it against `manifest.sha256`; after that evidence is recorded, mark Stage 3 DONE and begin Stage 4 as a separate task.

## Stage Status

| Stage | Status | Known state / remaining work |
|---|---|---|
| 0. Environment and data safety | DONE | Bootstrap and repeat-safe setup, CARLA server/client RGB smoke test, run tracking/manifest, actual image digest, private Git remote, and verified Mac `rsync` copy are recorded; new-VM recovery remains untested |
| 1. Map and API | DONE | Town01 load/API/weather/basic actor checks passed. On explicitly selected Town01_Opt, direct RoadLines hiding passed RGB and raw-semantic checks at straight/intersection/traffic-control observations with sampled navigation intact. Blueprint catalogue has no animal candidate; compatible external asset status remains open for Stage 7. |
| 2. Routes | DONE | The bridge route is now №4 and the four-turn route №5. All five routes under these identifiers passed spawned TM/autopilot completion, deviation, collision, timeout/stuck, and post-finish-stop checks in `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`; two set_path diagnostics are retained. |
| 3. Cameras and recording | IN_PROGRESS | Calibration, conversion, 18 sensors, 2 Hz alignment, raw semantic IDs, throughput, validator, and visual review passed locally; required verified off-VM copy remains |
| 4. Baseline dataset | TODO | No recordings exist |
| 5. Literature review | TODO | Initial technical sources exist; the LLM-method review is not complete |
| 6. LLM scene editing | TODO | Providers, access, exact IDs, and budget are unconfirmed |
| 7. Animal | TODO | Asset availability is a material risk under the no-Unreal constraint |
| 8. Repeated drives | TODO | No baseline or edited recordings exist |
| 9. Delivery | TODO | A report skeleton exists; nothing has been published |

## Known Infrastructure

- Massed Compute full VM, Ubuntu 22.04.5 LTS.
- RTX A6000 49,140 MiB, 6 vCPU, 94 GiB RAM, 295 GiB filesystem; 246 GiB free at the stage-0 check. The user-reported rate remains $0.57/hour, Premium.
- SSH user: `Ubuntu`; actual working directory: `/home/Ubuntu/carlas_tasks`.
- Docker 29.1.5 works through passwordless `sudo`; image and digest are recorded above.
- The stage-0 `carla-server` test container was stopped at 21:06 UTC. Do not assume this state persists; check before a later stage.
- According to the provider-panel warning relayed by the user, stopping a container or VM does not end billing; deleting the instance does and is irreversible.

Full version information and limits: [environment.md](environment.md).

## Missing Access and Decisions

1. Secure API-key restoration after VM deletion; actual providers/IDs and spending limits.
2. Whether a compatible prebuilt animal asset can appear without Unreal editing. The installed blueprint catalogue has no candidate.
3. Route length, weather-condition count, and repeats for the Stage-4 baseline matrix after the Stage-3 timing/size measurement.

Do not ask the user for all of these at once. Check available facts independently and ask only for a decision required by the current stage that is absent from the project.

## Latest Data Check

- Dataset: the short Stage-3 rig sample exists and passed local validation; the complete Stage-4 baseline dataset is not created.
- `artifacts/index.csv`: contains the smoke artifact with `backup_status=verified`.
- Verified off-VM copy: `/Users/madness/Научка/CARLA/runs/20260916T210617Z-carla-smoke-beb230/`, confirmed by user-provided `rsync` and SHA-256 output at 21:19 UTC.
- Stage-0 scripts and documentation are preserved in private `origin/Dev` history from `ce26b8e`; the completed Stage-1 correction and validation are preserved at `0ade213` on the same branch.
- Six stage-1 probe sets are locally manifest-verified but **not copied externally**: `20260917T110520Z-map-api-676d` (6,307,929 bytes), `20260917T111200Z-town01-opt-decals-5a62` (1,813,284 bytes), `20260917T145900Z-town01-texture-ead1` (4,331,674 bytes), `20260917T150510Z-town01-opt-direct-638d` (1,783,290 bytes, corrected review), `20260917T151600Z-town01-full-texture-1c2f` (1,675,533 bytes), and `20260917T153000Z-town01-opt-coverage-b6e3` (5,374,757 bytes, successful three-location confirmation). Their total is 21,286,467 bytes.
- The locally verified 9,331-byte run `20260917T154728Z-town10hd-reference-marking-8cb727` is incomplete: it has configuration/metadata only because its Town10HD_Opt server never became API-responsive. It is separate from the six Stage-1 evidence probes and is not copied externally.
- The locally manifest-verified 15,313,829-byte Stage-2 route-selection run `20260918T121645Z-town01-opt-routes-clean-debug-95bdcf` is the adopted visual evidence and has `backup_status=not_copied`. It contains `network_waypoints.json`, `routes.json`, five route files, a clean map overview, and six line-only DebugHelper route PNGs. The earlier 12,884,530-byte run `20260917T194300Z-town01-opt-routes-final-c5b492` remains valid for route geometry but its RGB previews are superseded: `draw_point` obscured road textures. The isolated 5,421,733-byte diagnostic `20260918T121243Z-debug-render-probe-295692` preserves the controlled no-debug/line-only/point-only comparison. Neither run is copied externally.
- The 12,180,606-byte candidate run `20260919T055800Z-route-candidates-adaptive-a2` is locally manifest-verified; its first three geometries are preserved in the final approved set. The source geometry revision `20260919T062007Z-route-revision-ca00ee` was followed by immutable renumbering revision `20260919T154916Z-route-numbering-swap-b5e941`: bridge route is now №4 and four-turn route №5, with geometry unchanged. Its manifest SHA-256 is `6af7ad8fe6cc3ce740aed00c66867b412d602195b44e90aed15cb9d26438272e`. None is copied externally.
- Stage-2 driving evidence is local-only: the current successful five-drive run `20260919T154938Z-tm-autopilot-renumbered-routes-aac495` is 2,250,192 bytes, has manifest SHA-256 `a2581991bb20f5ef79e0dabb78f292f53041369ee197ada93fe7edf83f7e9a6b`, and passed local verification of 19 signed files. Two failed `set_path` diagnostics and two successful one-route `set_route` pilots are also finalized and registered. None is copied externally.
- Stage-3 evidence is local-only: full-rig run `20260919T162408Z-av2-all-cameras-short-247e3f` passed all machine and visual checks, contains 119 signed files, is 165,463,137 bytes, and has manifest SHA-256 `8a203ea291a126682997bafbfb7816cabad7d1eb33cf6188ce0a10f1d2915e61`. The successful one-view clearance pilot and three retained failed geometry/body pilots are separately registered. None is copied externally; this is the only remaining Stage-3 acceptance item.
- Ready to delete VM: **not confirmed**. Documentation on the Mac does not prove that existing server work is preserved.

## How to Update This File

After every work session, update the date, active stage, completed acceptance criteria, references to run IDs/logs/commits, unfinished processes, and exact next action. Move historical detail to `worklog.md`. Do not include secrets or large logs. State separately where an external copy is verified and where it is not.
