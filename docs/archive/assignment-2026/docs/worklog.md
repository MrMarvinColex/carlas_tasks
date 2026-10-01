# Work Log

This log preserves chronology. `STATUS.md` contains the short current state. Future scripts record measurements; the agent adds explanation and links. Do not enter expected results as completed work.

## 2026-09-15–2026-09-16 — Assignment Analysis in the Original Chat

**Type:** document study, discussion, and documentation review; not a server experiment.

- Read the two-page PDF. Identified items 1.1–1.9 and 2–5, submission materials, and deadline.
- Discussed CARLA 0.9.16/0.10.0, the distinction between a release and development branch, runtime changes, and Unreal authoring.
- The user clarified: all AV2 cameras, paired RGB/semantic sensors, ego transform, minimum sufficient animal complexity, and comparison of three model variants.
- Selected an approach based on saved scene configurations and verifiable CARLA operations.
- Refined early assumptions about road markings, animal assets, and route duration; their status is recorded in `decisions.md` and `knowledge.md`.

**Evidence:** local source PDF, requirement text and clarifications in `requirements.md`, source index in `knowledge.md`.

**Result:** scope defined. Project code and dataset were not created.

## 2026-09-16 — User-Reported Prepared VM

**Type:** reported by the user. Exact times of the checks were not supplied.

The user rented a Massed Compute VM with an RTX A6000 48 GB, Ubuntu 22.04.5, 6 vCPU, 96 GB RAM, and a 300 GB SSD. They checked the GPU/driver, Docker/NVIDIA toolkit, downloaded `carlasim/carla:0.9.16`, and successfully launched CARLA offscreen. Unreal used the GPU and approximately 1.66 GB VRAM; the server opened a client port. The test container was then stopped and the image remained cached.

**Evidence limitation:** raw logs and commands were not supplied. Recording from 18 cameras, Town01, routes, marking removal, and an animal are not confirmed.

**Consequence:** do not repeat the entire installation without inspecting current state. Preserve current measurements and complete the reproducible environment/external storage in stage 0.

## 2026-09-16 — Portable Migration Package Prepared

**Type:** local-document work; no VM connection and no project implementation.

- Created AGENTS, README, requirements, fixed stage plan 0–9, initial status, decisions, environment description, runbook, and knowledge base.
- Created the report scaffold with unfilled experimental results, an empty artifact registry, and an environment template with no keys.
- Added a reading order, acceptance criteria, evidence recording, and independent-copy checks before VM deletion for the next agent.
- Included a local copy of the source PDF and excluded it from Git by default.

**Document verification:** confirmed the presence of 15 files, resolution of 18 internal Markdown links, fixed stage numbers 0–9 and their acceptance criteria, coverage of assignment items 1.1–1.9 and 2–5 in the report, 14 user clarifications, no populated API keys, and no invented records in the artifact registry. `.gitignore` rules were checked in a separate temporary Git repository: secrets/data are excluded, while documents, registry, and `.env.example` remain trackable.

**Source check:** the SHA-256 of the copied PDF matched the original: `277b2a653cbe40481d4011784cef8bbf4003b0f05e1ff8bb0f3207e275d6e248`. Portable documents contain no absolute path to the computer where the package was prepared.

**Result:** portable context prepared. The archive and documents are not evidence that server stages were completed.

**Next action:** transfer the package into the project, inspect existing server work, and complete the remaining portion of stage 0.

## 2026-09-16 — English Translation of the Portable Documentation

**Type:** local-document update; no VM connection and no project implementation.

- Translated the operating instructions, project documentation, and report scaffold into English without changing established requirements, decisions, open questions, or experimental status.
- Kept the original Russian PDF as the verbatim source. Russian remains only where it is useful to support Russian user commands and language instructions.
- Preserved identifiers, stage numbering, requirement IDs, links, empty placeholders, and the distinction between verified facts, decisions, hypotheses, and uncompleted experiments.
- Rebuilt and verified the deliverable archive after translation.

**Result:** the package is ready for an English-document workflow while the user may continue giving Codex instructions in Russian.

## 2026-09-16 21:00–21:07 UTC — Stage 0 Environment Bootstrap and CARLA RGB Smoke Run

**Type:** completed and verified on the current VM, except external-copy verification.

- Confirmed the actual project root as `/home/Ubuntu/carlas_tasks` under user `Ubuntu`; branch `00_-_stage` and private `origin` were inspected. `origin/main` was reachable at `0e52c6a` before the stage-0 documentation/code edits.
- Inspected the actual VM: Ubuntu 22.04.5, RTX A6000 (driver 580.126.09, 49,140 MiB), Docker 29.1.5 with passwordless `sudo`, NVIDIA Container Toolkit 1.18.1, and 246 GiB free disk. Before the test no CARLA containers, CARLA processes, or listeners on ports 2000–2002 existed.
- Recorded local CARLA image `carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953` (image ID `98d224…83b5`).
- Added `scripts/setup.sh`, CARLA start/stop scripts, run metadata/manifest utilities, export verifier, and an RGB smoke client. The initial bootstrap correctly exposed a missing OS `python3.10-venv` dependency; it was installed, after which `.venv` was built with Python 3.10.12 and `carla==0.9.16`. A failed partial `.venv` exposed and led to a safe repair path that rebuilds only the default project-local virtual environment.
- Started temporary `carla-server`, ran `20260916T210617Z-carla-smoke-beb230`, captured `rgb/front.png` (800×600 RGBA PNG), visually inspected it, and stopped the container. Metadata records matching CARLA client/server 0.9.16 and default map `Carla/Maps/Town10HD_Opt`. The map was not changed, so this is not a Town01 result.
- The first local export-verifier run found a self-invalidating manifest caused by mutable metadata. The finalizer was corrected, the same artifact was re-finalized, and verification passed: 3 files match `manifest.sha256` (`8def61758b358578ea2a00a77f52e684aa0caf75b2219150dc4208c101ca87ca`), 1,112,700 bytes including the manifest.

**Artifacts:** local ignored run directory `runs/20260916T210617Z-carla-smoke-beb230`; registry row `stage0-smoke-20260916`. The frame is intentionally not committed. No external location exists yet.

**Result and limitation:** client startup and one rendered RGB frame are reproducible on this VM. Recovery on a new VM, 18-camera recording, Town01, and any external-copy claim remain untested. Stage 0 remains `IN_PROGRESS` solely because the user has not selected/authorized an off-VM storage destination.

**Next action:** export this small run to the user-selected destination, run `scripts/verify_export.py` there, record the destination and verification time, then close stage 0.

## 2026-09-16 21:19 UTC — Verified Mac Copy; Stage 0 Acceptance Completed

**Type:** user-operated external verification with supplied command output.

- The user created and tested SSH alias `carla-vm` from their Mac. It connected to the current VM as `Ubuntu` and reported the expected host and `/home/Ubuntu` home directory.
- A dry-run `rsync` listed 7 entries for `runs/20260916T210617Z-carla-smoke-beb230/`; the subsequent `rsync -avP` transfer completed to `/Users/madness/Научка/CARLA/runs/20260916T210617Z-carla-smoke-beb230/` without `--delete`.
- On the Mac, the user converted the run's three-column manifest into `shasum` check input. `config.json`, `metadata.json`, and `rgb/front.png` each reported `OK`. The transferred file total was 1,100,412 bytes; the manifest SHA-256 is `8def61758b358578ea2a00a77f52e684aa0caf75b2219150dc4208c101ca87ca`.

**Artifacts:** registry row `stage0-smoke-20260916` now records the external Mac location and `backup_status=verified`.

**Result:** Stage 0 acceptance is satisfied: startup/client RGB smoke, reproducible setup and run tracking, image/version evidence, and a verified off-VM test copy exist. Recovery on a newly rented VM was not tested and is explicitly not claimed.

**Next action:** commit and push the stage-0 scripts and updated documentation to the existing private Git remote. Do not automatically begin stage 1; Town01, marking removal, and animal capability remain separate untested work.

## 2026-09-16 21:20 UTC — Stage-0 Code Preserved in Private Git

**Type:** completed and verified Git operation.

- Reviewed the staged paths: only stage-0 scripts, `requirements.txt`, configuration template, documentation, report, and artifact registry were included. `.venv`, `logs`, and `runs` remained ignored and were not staged.
- Created commit `ce26b8e` (`Complete reproducible stage 0 setup`) and pushed it to the new private remote branch `origin/00_-_stage`. GitHub offered an optional pull request; none was created. `main` was not changed and repository visibility was not altered.

**Result:** code and documentation needed to recreate the stage-0 workflow are now preserved outside the VM, separately from the verified Mac artifact copy.

**Next action:** await a separate stage-1 request.

## 2026-09-16 21:26 UTC — Consolidated Environment Utilities

**Type:** project-structure cleanup; no CARLA run.

- Moved the useful read-only VM diagnostics from `env_setup_and_tests/00_preflight.sh` to `scripts/preflight.sh` and added it to the documented stage-0 entry points.
- Removed the old `01_carla_smoke_test.sh`: it pulled an image on every invocation, only checked port/log readiness, and produced neither a client RGB frame nor run metadata/manifest. Its purpose is covered by the tested `run_carla.sh` → `smoke_rgb.py` → `finalize_run.py` workflow.
- Removed `setup_tmux_comfort.sh`: it changed a user's personal `~/.tmux.conf` and had no bearing on CARLA reproducibility or project results.

**How checked:** reviewed all previous and retained script contents; old-path mentions remain only in this historical explanation. Shell syntax passed. The new `scripts/preflight.sh` was rerun at 21:27 UTC on the VM and reported the expected Ubuntu 22.04.5, RTX A6000/driver 580.126.09, Docker 29.1.5 with passwordless `sudo`, and no GPU process; it made no changes.

**Result:** one canonical `scripts/` directory now contains every maintained project utility. Historical scripts remain retrievable from Git commit `0e52c6a` if needed.

**Next action:** await a separate stage-1 request.

## 2026-09-17 10:53–15:08 UTC — Stage 1 Map/API Capability Probe

**Type:** completed and verified CARLA experiments on the current VM; requirement 1.4 remains incomplete.

**Goal:** load Town01, exercise basic API operations, inspect visible road-marking controls and early animal availability, and preserve before/after evidence.

- Rechecked the VM before the run: Ubuntu 22.04.5, RTX A6000 (driver 580.126.09), Docker 29.1.5, 246 GiB free disk, no competing CARLA container. Started one offscreen `carla-server` at a time and stopped the final container after the probes.
- Added `scripts/stage1_map_api.py`. It records all maps returned by the installed server, loads Town01, captures 800×600 RGB plus unmodified/raw and CityScapes-preview semantic PNGs at a generated straight road, junction, and traffic-control fallback (the map returned no crosswalk API point), tests basic vehicle actor creation/destruction, validates rendered weather change, and catalogues environment objects/blueprints.
- Artifact-confirmed: `Town01` and `Town01_Opt` are available. Town01 loaded as `Carla/Maps/Town01`; client/server were both 0.9.16. The actor lifecycle passed, weather differed in rendered RGB, and map topology had 160 edges. Town01 had 259 `RoadLines` objects; hiding them made raw semantic class 24 disappear at all three locations (605→0, 512→0, 565→0) with topology and sampled driving waypoints preserved. Visual inspection of the paired RGB frames found the yellow markings still present. The run therefore is `incomplete`, not a successful removal.
- Tested `Town01_Opt` as an allowed optional map-layer candidate. `MapLayer.Decals` left markings visible and made unrelated scene changes. Direct hiding of its 25 `RoadLines` objects likewise changed class 24 from 604 to 0 but left yellow RGB lines visible. These runs do not substitute Town01 for the assignment requirement.
- Added `scripts/stage1_texture_probe.py`. Its first attempt failed because environment-object names use `_SM_0` while texture API names omit that suffix; this failed run was retained. The corrected probe resolved all 259 material names and applied a 2×2 neutral Diffuse `TextureColor` without API errors. RGB inspection found no usable alteration to the target marking or the straight/intersection/traffic-control coverage; combined texture plus hiding still retained visible lines. No OpenDRIVE, Unreal asset, or texture file was edited.
- Added `scripts/stage1_full_texture_probe.py` after inspecting the installed Python API for its remaining texture operations. A 64×64 all-channel `apply_textures_to_object` call (Diffuse, Emissive, Normal, and AO/Roughness/Metallic/Emissive) succeeded on `Road_Marking_Town01_1`, but the target RGB pair retained yellow segments and raw class 24 remained 402→402. This is a further failed candidate, not evidence of a successful texture edit.
- The exposed Town01 blueprint library held 214 IDs (41 vehicle, 52 walker, 19 sensor) and no candidate animal ID under the documented name pattern. This is not proof that a compatible prebuilt animal extension is unavailable; it is a stage-1 risk result.
- Finalized all complete, incomplete, and failed probe directories with manifest hashes. Local manifest verification passed for the four main evidence sets: `20260917T110520Z-map-api-676d`, `20260917T111200Z-town01-opt-decals-5a62`, `20260917T145900Z-town01-texture-ead1`, and `20260917T150510Z-town01-opt-direct-638d`. Two interrupted Town01_Opt transitions and the initial texture-name failure remain retained as failed runs.

**Artifacts:** the five main local-only runs total 15,910,754 bytes and are registered in `artifacts/index.csv`; each has `backup_status=not_copied`. Visual verdicts are stored in each main run's `visual_review.json`. No external copy was made in this task.

**Result and limitation:** items 1.1–1.3/basic use are supported by stage-0/1 evidence. Item 1.4 is blocked: all tested runtime candidates (`RoadLines`, `Decals`, direct hide on Town01_Opt, and supported Diffuse texture replacement) fail the required visible-RGB removal. A semantic-only change is explicitly not treated as success. Stage 1 cannot be `DONE` under the present scope.

**Handoff update:** stage-1 scripts and documentation were committed as `470dbb0` and `31c4e94`. Later on 2026-09-17, the private branch was renamed from `00_-_stage` to `Dev`; both commits were pushed to `origin/Dev`, and the former remote branch was removed as part of that rename.

**Next action:** retained as historical handoff. The correction below supersedes its road-marking conclusion.

## 2026-09-17 15:08–15:35 UTC — Correction and Three-Location Town01_Opt Confirmation

**Type:** completed and verified CARLA evidence correction.

- The user pointed to the saved pair in `20260917T150510Z-town01-opt-direct-638d`: the yellow markings visible in `before/straight_road/rgb.png` are absent in `after_roadlines/straight_road/rgb.png`. Re-inspection confirmed that the previous visual-review conclusion was erroneous. The original review remains in the run; `visual_review_correction.json` records the correction and the run manifest was regenerated.
- Extended `scripts/stage1_map_api.py` so the isolated Town01_Opt direct-RoadLines probe captures and compares every available coverage location rather than only the straight road. It now records post-operation driving-waypoint checks and validates that raw RoadLines pixels were present before, zero after, RGB bytes changed, and navigation remains available.
- Created run `20260917T153000Z-town01-opt-coverage-b6e3` on `Carla/Maps/Town01_Opt`. Hiding its 25 RoadLines objects removed the visible yellow markings in each identical-position RGB pair. Raw semantic class 24 changed straight road 604→0 pixels, intersection 512→0, and traffic-control location 550→0. Driving waypoints remained available at all three locations; topology was 160 edges. `get_crosswalks()` returned no point, so no crosswalk/stop-line or map-wide removal claim is made.
- Local manifest verification passed for the corrected one-location run (12 signed files) and the confirmation run (23 signed files). The temporary CARLA container was checked and was not running after the work.
- Preserved the updated probe code, registry, report, decisions, and status in private `origin/Dev` commit `0ade213` (`Complete Stage 1 Town01_Opt road-line validation`).

**Artifacts:** six local-only Stage-1 probe sets total 21,286,467 bytes. The new successful evidence is `20260917T153000Z-town01-opt-coverage-b6e3`; its manifest SHA-256 is `8e22318a752ceb20eb63c8af79982de9ef8b13f9b0c1bd72268f4105de9f7853`. No off-VM copy exists yet.

**Result and limitation:** Stage 1 acceptance is satisfied. Town01 was loaded separately; later runtime work selects the explicitly named `Town01_Opt` because it is the tested variant that passes the declared RGB/raw-semantic/navigation coverage. Animal availability remains a recorded risk for Stage 7, not a Stage-1 blocker.

**Next action:** copy and hash-verify the six probes on the Mac, then start Stage 2 routes on Town01_Opt and apply the validated RoadLines operation after every map load.

## 2026-09-17 15:35–15:54 UTC — Attempted Supplemental Check of the Old Smoke View

**Type:** incomplete diagnostic; no image result.

- The user identified the yellow box grid and an adjacent crossing in `runs/20260916T210617Z-carla-smoke-beb230/rgb/front.png`. Inspection confirmed that this is a front-camera image from `Carla/Maps/Town10HD_Opt`, whereas the selected project map is `Town01_Opt`. The old smoke metadata has no vehicle transform, so an exact camera-pose replay is not provable.
- Added `scripts/stage1_reference_marking_probe.py`: it is designed to use the smoke script's first-free-spawn loop, first vehicle blueprint, and 800×600, 90-degree front camera at `x=1.6,z=2.3`; it captures RGB/raw semantic before and after hiding all RoadLines and records the newly used transform. It compiled, but has not yet reached a CARLA capture.
- Started one temporary CARLA container. Ports 2000–2002 opened and the Unreal process used the GPU, but repeated client `get_world()` attempts with 5–20-second timeouts did not receive an API response. No probe images or result JSON were created. The container was stopped rather than left consuming GPU resources.
- Finalized and locally verified the incomplete 9,331-byte run `20260917T154728Z-town10hd-reference-marking-8cb727`; it contains only configuration and metadata. This is not evidence about marking removal.

**Next action:** on a later API-responsive CARLA startup, rerun this supplemental Town10HD_Opt probe and inspect whether the yellow grid and crossing disappear. Keep its conclusion separate from the Town01_Opt Stage-1 acceptance evidence.

## 2026-09-17 19:38–19:45 UTC — Stage 2 Route Construction and DebugHelper Verification

**Type:** completed and locally verified CARLA route-selection experiment; autopilot driving is not included.

**Goal:** apply the selected Town01_Opt RoadLines operation, choose and persist five connected routes, and verify their geometry with temporary DebugHelper drawings before implementing Traffic Manager control.

- Rechecked the actual VM: RTX A6000, Docker through passwordless `sudo`, no competing CARLA container/listener, and 246 GiB free disk. Started one offscreen `carla-server`, used CARLA client/server 0.9.16, and stopped it after the run.
- Added `scripts/stage2_routes.py`. It loads the explicit `Carla/Maps/Town01_Opt`, hides the 25 returned RoadLines object IDs, switches temporarily to a 0.05 s synchronous world, and writes a complete sorted `Map.generate_waypoints(2.0)` sample. The selected map returned 3,266 waypoints.
- With seed `20260917`, sorted native spawn points, and direct `Waypoint.next(2.0)` calls, selected five routes. Every route has 60 driving waypoints (59 edges) and is 114.841–121.110 m long. For every stored edge the script independently reissued `predecessor.next(2.0)` and confirmed membership of the successor; all 295 checks passed.
- Wrote `routes.json`, five coordinate/order/start/finish/road/lane JSON files, `network_waypoints.json`, and `validation.json`. The final run has both a full-network DebugHelper view and a clean map-wide route view plus five close per-route views. Debug shapes were created with finite lifetimes and were explicitly cleared after capture.
- Visually inspected all five close top-down route images. They show the intended continuous paths: one straight route and four paths containing bends/turns. This is a visual geometry check only, not evidence that a vehicle can follow them.
- Two earlier same-session route-view iterations are retained locally (`20260917T193903Z-town01-opt-routes-b168cc`, `20260917T194057Z-town01-opt-routes-readable-d601e3`). The final run is adopted because it separates dense full-network drawing from route-only and close per-route views.

**How checked:** `scripts/stage2_routes.py` compiled with `py_compile`; `git diff --check` passed before final documentation edits. Run `20260917T194300Z-town01-opt-routes-final-c5b492` passed every machine validation: exact map, RoadLines operation, non-empty complete/driving samples, exactly five routes, ≥10 waypoints each, direct `next()` connectivity, distinct starts, valid overview PNGs, temporary debug state, and five valid per-route PNGs. It was finalized with manifest SHA-256 `99a2e111469b0efabbf93b12ca508598e2bdb940268766f9344a8ce2f2712654` and totals 12,884,530 bytes.

**Artifacts and external copy:** local ignored run `runs/20260917T194300Z-town01-opt-routes-final-c5b492`, registry row `stage2-town01-opt-routes-20260917`, `validation_status=passed`, `backup_status=not_copied`. No claim of an external backup is made.

**Decisions / limitations:** D13 supersedes GlobalRoutePlanner as the route-*selection* mechanism; direct waypoint adjacency is the recorded connectivity proof. It does not validate native actor spawning, Traffic Manager `set_path`, intersection decisions, completion, timeout, stuck detection, collision handling, or post-finish stopping. No camera rig or dataset recording was run.

**Next action:** implement and test Traffic Manager driving over these exact saved routes, starting with one short route before all five.

## 2026-09-18 12:12–12:22 UTC — Corrected DebugHelper Route Rendering

**Type:** completed and locally verified rendering correction; route geometry is unchanged.

**Trigger:** the user noticed black/missing road-texture areas around route markers in the Stage-2 top-down images.

- Created controlled diagnostic run `20260918T121243Z-debug-render-probe-295692` for the same Town01_Opt map state, RoadLines operation, route 04, and nadir camera. It captured no DebugHelper geometry, line-only geometry, and 0.10 m point-only geometry.
- Visual inspection showed intact texture with no debug geometry and with `DebugHelper.draw_line`; point-only rendering made a black rectangle at each sampled waypoint. This isolates the issue to CARLA 0.9.16's `draw_point` RGB rendering, not RoadLines hiding, the waypoint coordinates, or a missing map texture.
- Updated `scripts/stage2_routes.py`: the complete waypoint sample is still submitted to DebugHelper for 0.5 s of simulation time to meet the route-selection check, but all point shapes are cleared before an RGB sensor is spawned. Saved route visuals contain only 0.8 m colour-coded `draw_line` segments; point and text primitives are absent.
- Repeated the full route-selection probe as `20260918T121645Z-town01-opt-routes-clean-debug-95bdcf`. It regenerated the same seed-selected five 60-waypoint routes and passed every route/map/debug PNG check. The clean full-map and per-route views retain road texture while preserving clear coloured route lines. The temporary CARLA container was stopped after the run.

**How checked:** both manifests were recomputed entry-by-entry with zero mismatches. Diagnostic manifest SHA-256: `f0c6b58173f3e8f7bb3e0b35b16a8df3a7e22b06b0898e9b40d43f677cba6389` (5,421,733 bytes); corrected-route manifest SHA-256: `1c290c07aab099a8ff1db02012501db096856f54227471af51560ccceb9727d5` (15,313,829 bytes). The corrected run's `validation.json` status is `passed`.

**Artifacts and external copy:** registry rows `stage2-debug-render-probe-20260918` and `stage2-town01-opt-routes-clean-debug-20260918`; both are local-only with `backup_status=not_copied`. The 2026-09-17 route run and its artefact are retained, but its RGB preview is superseded for presentation only.

**Next action:** commit and push the texture-safe route-visualisation correction, then resume the still-unfinished Traffic Manager driving half of Stage 2.

## 2026-09-19 05:48–05:52 UTC — Diverse Adaptive Route Candidates

**Type:** completed and locally verified visual proposal; candidates are not adopted and no driving was run.

**Trigger:** the user rejected the original mostly straight routes and approved denser waypoint spacing near turns with wider spacing on straights.

- Added `scripts/stage2_route_candidates.py`. It enumerated 1,020 complete seeded paths from all 255 native spawn anchors using direct `Waypoint.next(2.0)` chains, classified sustained heading changes, and selected five deliberately different geometries with low overlap and separated starts.
- The corrected proposal contains a 220.061 m straight control, 253.109 m single-left route, 246.838 m single-right route, 313.048 m three-turn zigzag, and 350.302 m three-turn mixed route. Their dense 2 m references contain 111–181 waypoints and every one of 695 edges passed a repeated direct-successor check.
- Proposed adaptive subsets retain about 10 m spacing on straights and 2 m spacing within 12 m of detected turns. Counts are 23, 44, 45, 83, and 90, all above the assignment minimum. Saved paths use line segments and adaptive cross markers made only from `DebugHelper.draw_line`; visual inspection found intact road texture.
- The first run, `20260919T054900Z-route-candidates-adaptive-a1`, also densified every `is_junction` interval. Visual inspection showed excessive 2 m markers on straight-through junction sections, so it was finalized as incomplete and retained. The corrected `20260919T055800Z-route-candidates-adaptive-a2` densifies only real heading-change events and passed all machine and visual checks.
- Corrected-run manifest verification passed for all 16 entries. Its manifest SHA-256 is `24309b1c0d35bd763d3b4b1d47641c27226ac636c539fdcefa107c6479ac3429`; signed content totals 12,180,606 bytes. The temporary CARLA container was stopped.

**Artifacts and external copy:** both runs are registered in `artifacts/index.csv` and remain local-only with `backup_status=not_copied`.

**Decision / limitation:** the user approved the adaptive-spacing direction, not the five exact geometries. D13 and the original route table remain authoritative until visual approval. Neither candidate run spawned a vehicle or exercised Traffic Manager.

**Next action:** collect user feedback on the overview and five individual previews; revise or formally adopt the selected set before implementing autopilot drives.

## 2026-09-19 05:59–06:20 UTC — User-Directed Revision of Routes 4 and 5

**Type:** completed and locally verified geometry revision; routes 4–5 await user visual approval; no autopilot drive.

- Recorded the user's approval of adaptive candidate geometries 1–3 and reconstructed every dense waypoint identity from the approved run without reselection.
- Added `scripts/stage2_route_revision.py`. Route 4 continues its original deterministic branch sequence through a fourth turn: 508.150 m, 252 dense connected points, and 119 adaptive points.
- Route-5 exploration rejected an upper-road interpretation, failed attempts to force the old unapproved route through an incompatible directed continuation, and the narrow internal visual bridge because no connected Driving-waypoint candidate crossed that corridor. These failures remain as incomplete runs rather than being hidden.
- The final seeded search tested 1,275 complete paths against the outer automobile bridge, both-bank crossing, and a turn at least 16 m after the far bank. It found 237 candidates satisfying the complete criteria and selected a 495.316 m route with 244 dense points and 101 adaptive points, close to the 500 m design target.
- The final route-5 individual preview uses full-map framing. All saved previews use DebugHelper lines only; visual inspection found intact in-map textures and clearly showed the complete bridge crossing followed by a turn.

**How checked:** run `20260919T062007Z-route-revision-ca00ee` passed exact-map, RoadLines-hide, five-route, first-three-identity, four-turn, both-bank bridge, post-bridge-turn, direct-edge connectivity, adaptive-minimum, PNG, and no-point-primitive checks. Its 16 manifest entries passed entry-by-entry SHA-256 verification; manifest SHA-256 is `db2018bf734ce412e53d8b396d7053ae5f879d76ad95571b7ede42e8f6b63936` and signed content totals 12,442,715 bytes. The CARLA container was stopped and absence of containers was checked.

**Artifacts and limitation:** the final run and ten incomplete intermediate revisions are registered in `artifacts/index.csv`; all are local-only. Routes 4–5 still require user approval, and no ego vehicle, Traffic Manager path, completion threshold, or stuck check has run.

**Next action:** obtain user approval for the revised route-4 and route-5 previews, promote the complete replacement set, then implement one-route Traffic Manager validation before attempting all five.

## 2026-09-19 06:40 UTC — Final User Approval of the Five Route Geometries

**Type:** user decision recorded; no CARLA execution.

- The user explicitly approved revised routes 4 and 5. Together with the earlier approval of routes 1–3, all five adaptive geometries in `20260919T062007Z-route-revision-ca00ee` are now the authoritative Stage-2 route set.
- Updated current status, decisions, and the report route table. The older five 60-point routes remain historical evidence but are superseded for subsequent implementation.
- This approval completes route selection and DebugHelper review only. It does not provide evidence of a valid actor spawn, Traffic Manager path acceptance, vehicle motion, completion, timeout, stuck detection, collision handling, or post-finish stopping.

**Next action:** implement and validate one Traffic Manager/autopilot pilot on the approved route set, then run all five if the pilot passes.

## 2026-09-19 06:50–07:01 UTC — Stage 2 Traffic Manager Autopilot Validation

**Type:** completed and locally verified CARLA driving experiment.

- Added `scripts/stage2_autopilot_routes.py`. It reconstructs the approved waypoint IDs from `20260919T062007Z-route-revision-ca00ee`, rechecks every direct 2 m successor edge, reloads `Town01_Opt`, reapplies direct RoadLines hiding, spawns one Tesla Model 3 per route, and records every synchronous-world pose plus collision events.
- The first two route-1 diagnostic attempts used `TrafficManager.set_path`: first the adaptive locations and then the full connected 2 m chain. Both were accepted but selected a different later branch after 94 m and timed out. They were finalized as incomplete (`20260919T065121Z-tm-autopilot-pilot-ea602d`, `20260919T065327Z-tm-autopilot-pilot-282f01`), preserving the observed limitation.
- The final command derives one `Left`/`Right`/`Straight` instruction for each contiguous map-junction traversal and submits it through `TrafficManager.set_route`. A route-1 and route-2 pilot passed, then all five approved routes passed in `20260919T065802Z-tm-autopilot-approved-routes-106f97`.

**How checked:** all full-run checks passed: actual `Town01_Opt`, RoadLines operation applied to 25 objects, valid vehicle spawn and TM command, finish radius ≤8 m with ≥95% projected progress, maximum reference deviation ≤15 m, zero collisions, no timeout/stuck result, and explicit stopped vehicle after autopilot was disabled. Observed maximum deviations were 0.997–1.247 m; finish distances were 7.199–7.935 m. Local `verify_export.py` revalidated all five manifests; the full run contains 19 signed files and has manifest SHA-256 `607b8b527c62aef0565978b512ab80182c07c380d8ab26f9638bfe29122fbe86` (2,258,589 bytes including manifest).

**Artifacts and external copy:** all five drive-related runs are registered in `artifacts/index.csv`; they are local-only (`backup_status=not_copied`). No cameras or dataset imagery were created. CARLA was stopped after validation.

**Next action:** start Stage 3 by selecting an actual AV2 calibration and validating the nine RGB/semantic sensor pairs and 2 Hz pose/frame alignment on a short drive.

## 2026-09-19 15:49–15:50 UTC — User-Requested Route-Numbering Swap

**Type:** completed and locally verified identifier-only revision plus CARLA revalidation.

- The user requested that the bridge route become route 4 and the more complex four-turn route become route 5. Added `scripts/stage2_route_relabel.py`, which preserves the old signed run, copies only route documents into a fresh revision, changes the identifiers/order, and checks that every geometry-bearing field is unchanged.
- Revision `20260919T154916Z-route-numbering-swap-b5e941` passed all five geometry-preservation checks. It maps `route_05_bridge_then_turn` → `route_04_bridge_then_turn` and `route_04_four_turns` → `route_05_four_turns`.
- Re-ran all five Traffic Manager drives against that revision. The current final validation is `20260919T154938Z-tm-autopilot-renumbered-routes-aac495`; every route passed all existing completion/safety checks under its current identifier.

**How checked:** local manifest validation passed for 9 relabelling files and 19 drive files. The relabelling manifest is `6af7ad8fe6cc3ce740aed00c66867b412d602195b44e90aed15cb9d26438272e` (746,813 bytes); the new all-route drive manifest is `a2581991bb20f5ef79e0dabb78f292f53041369ee197ada93fe7edf83f7e9a6b` (2,250,192 bytes).

**Artifacts and external copy:** both new runs are in `artifacts/index.csv` and remain local-only. CARLA was stopped after the revalidation.

**Next action:** Stage 3 — select an actual AV2 calibration and validate nine RGB/semantic sensor pairs with 2 Hz frame/pose alignment.

## 2026-09-19 16:13–16:30 UTC — Stage 3 AV2 Rig and 2 Hz Recording

**Type:** locally completed technical implementation and validation; stage acceptance still awaits verified external copy.

- Retrieved only the two official calibration Feather files for AV2 Sensor log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca` from the documented public S3 bucket. Preserved the raw files, exact extracted values, URLs, retrieval condition, and SHA-256 under `configs/av2/`; no camera dataset was downloaded.
- Added pure coordinate-conversion helpers and tests, the frame-keyed synchronous recorder, and the PNG/dataset validator. The recorder derives the Tesla rear axle from wheel positions after one world tick, attaches RGB and semantic sensors at all nine converted poses, saves raw semantic IDs separately from palettes, writes partial transforms during capture, and measures wall/GPU/RAM/data throughput.
- Retained three failed one-view pilots. The first treated CARLA world wheel coordinates as actor-local. The second attempted inversion before the actor's first synchronous tick, when its transform was still identity. The third corrected the origin and passed frame/file checks, but visual review found the Tesla hood. The successful one-view pilot uses a declared +0.5 m local-z clearance adaptation and has zero ego pixels in the validated bottom strip.
- Full run `20260919T162408Z-av2-all-cameras-short-247e3f` used 18 sensors and accepted four time points. It produced 72 required RGB/raw-semantic images, 36 palette previews, four ego poses, two contact sheets, calibration/configuration records, validation, and resource measurements.

**How checked:** eight offline unit tests and Python compilation passed. The dataset validator parsed JSON, verified unique increasing frames, 0.5 s timing within 0.0001 s, same-frame sensor/pose timestamps, all expected paths and dimensions, PNG signatures/chunk CRCs/zlib streams, 8-bit raw semantic encoding, and zero ego-body pixels in the bottom 10%. All 108 PNGs passed; no callbacks were missing, duplicated, or late after stop. RGB and semantic contact sheets passed manual review. The finalized 119-entry manifest passed local entry-by-entry verification; manifest SHA-256 is `8a203ea291a126682997bafbfb7816cabad7d1eb33cf6188ce0a10f1d2915e61`, and the directory occupies 165,463,137 bytes.

**Performance:** accepted simulation span 1.500000022 s; wall duration 126.905 s; measured output before validation about 109.34 MB per accepted simulation second; sampled GPU memory peak 4,657 MiB; sampled host used-memory peak about 8.08 GB. These are short-run observations, not long-run guarantees.

**Artifacts and external copy:** the full run, successful one-view pilot, and three failed pilots are registered in `artifacts/index.csv`, all with `backup_status=not_copied`. The CARLA container was stopped. Stage 3 remains `IN_PROGRESS` only because its acceptance criterion requires a verified off-VM copy.

**Git preservation:** Stage-3 code, raw calibration sources, tests, registry entries, and documentation were committed as `3fbe0de` and pushed to private `origin/Dev`. Run metadata retains the truthful pre-commit `22c49c0` plus dirty-state indicator.

**Next action:** from the Mac, pull the full run to `/Users/madness/Научка/CARLA/runs/20260919T162408Z-av2-all-cameras-short-247e3f/`, run `scripts/verify_export.py` or an equivalent manifest check against that destination, then record the proof and mark Stage 3 DONE.

## 2026-09-23 11:28–11:36 UTC — New-VM Environment Recovery

**Type:** new-VM setup and short local smoke verification; historical data transfer is still in progress.

- Checked clean private `Dev` worktree at `0255434fbd779d9de735ee615c8aa21cabc7fc19`, `/home/Ubuntu/carlas_tasks`, and the preflight output. GPU, NVIDIA runtime, passwordless Docker, memory, and disk prerequisites passed. No CARLA image or containers existed initially.
- The first `scripts/setup.sh` attempt failed because the pre-existing `.venv` had no `pip` and the OS lacked `ensurepip`. Installed `python3.10-venv` through apt; the second setup succeeded with Python 3.10.12 and `carla==0.9.16`.
- Pulled `carlasim/carla:0.9.16`; its digest matched the recorded `aaf1df22...` digest. Started the offscreen server, captured one 800×600 RGB frame, finalized the run, verified all three manifest entries locally, and stopped the container. The frame was not visually reviewed.

**Evidence:** temporary run `/tmp/carla-recovery-runs/20260923T113354Z-new-vm-recovery-3f3dcb/` (manifest SHA-256 `4412e91afe7bafc312d52915e46f306c487086dcee0d490a80c40a79c76558fc`); server log `/tmp/carla-recovery-logs/carla-20260923T113324Z.log`. Run metadata records clean Git state, client/server 0.9.16, default `Town10HD_Opt`, frame 1459, and timestamp 14.433419645647518 s. These `/tmp` files are not externally backed up or registered as deliverable artifacts.

**Next action:** after the user's Mac-to-VM rsync completes, verify restored manifests and the historical Stage-3 short run. Obtain separate confirmation that its Mac copy passed the manifest check before closing Stage 3.

## 2026-09-23 12:01 UTC — Stage 3 Closure by User-Confirmed External Copy

**Type:** user-reported off-VM-copy evidence; local run validation remains artifact-confirmed.

- The user confirmed that an external copy of `20260919T162408Z-av2-all-cameras-short-247e3f` exists and explicitly instructed that Stage 3 be marked complete.
- No Mac-side `scripts/verify_export.py` output or SHA-256 comparison output was supplied in this session. Therefore the registry uses `backup_status=user_confirmed`, rather than `verified`; the complete run's local 119-entry manifest validation and SHA-256 `8a203ea291a126682997bafbfb7816cabad7d1eb33cf6188ce0a10f1d2915e61` remain the artifact-confirmed integrity evidence.

**Result:** Stage 3 is `DONE` at the user's direction. Its technical camera/recording acceptance was already complete; the external-copy existence is user-reported. Preserve or obtain the external manifest-verification output before any irreversible VM deletion or final delivery.

**Next action:** wait for a separately assigned Stage-4 task; do not start baseline recording automatically.

## 2026-09-23 12:30 UTC — Stage 4 Matrix and Full-Route Recording Pilot

**Type:** Stage-4 implementation and active experiment; no accepted baseline result yet.

- Fixed `configs/stage4_baseline_matrix.json`: five approved routes, `clear_day` and `wet_cloudy_day`, one repeat each (10 planned baseline runs). It records exact CARLA parameters, fixed simulation/sensor periods, Traffic Manager seed, disk guardrails, and a `route_05_four_turns` clear-day pilot. Weather labels are not seasonal claims.
- Added `scripts/stage4_baseline.py`, which applies the selected baseline scene after every map load, drives one route with Traffic Manager, records all 18 sensor streams at 2 Hz from same-frame snapshots, retains raw semantic IDs and palettes separately, writes partial transforms, tracks collision/timeout/stuck/completion metrics, then invokes the existing dataset validator after a completed drive.
- Local checks passed: the matrix has exactly 10 planned route-weather runs; the runner and dependent Stage-3 recorder/validator compile; 245 GiB were free before recording; the image digest matched the pinned image; and only one CARLA container was started.
- Retained failed diagnostic `20260923T123049Z-baseline-pilot-route05-clear-day-19873f`: its first runner revision incorrectly required calibration JSON insertion order to match camera order and stopped before sensors or frames were created. It was finalized `failed`; the check now compares camera sets.
- Active run `20260923T123315Z-baseline-pilot-route05-clear-day-retry-ba0f8c` is recording the 508.150 m `route_05_four_turns` in `clear_day`. It had accepted 56 complete 18-stream time points when this entry was written; do not infer final drive or validation success until it exits.

**Next action:** wait for this run to finish, inspect `drive_result.json` and both validators, finalize its manifest, stop CARLA, measure the output, then decide whether the remaining nine runs fit the fixed batch policy.

## 2026-09-23 13:13 UTC — Stage 4 Pilot Stopped at User Request

**Type:** incomplete experiment retained at the user's instruction.

- The user asked to stop the active full-route pilot. The recorder process and then the sole `carla-server` container were stopped; no further Stage-4 drive was started.
- Retry run `20260923T123315Z-baseline-pilot-route05-clear-day-retry-ba0f8c` had 77 complete, same-frame 18-stream samples in `transforms.partial.json`, covering 38.5 s of simulation time. Its output before finalization was 3,621,970,754 bytes; finalized directory size is 3,622,361,120 bytes. It has no final `transforms.json`, route result, or dataset validation and is therefore `incomplete`, not an accepted baseline drive.
- Finalized it with the explicit user-stop reason. Local manifest verification passed for all 2,110 signed files; manifest SHA-256 is `914e2bca06e417d0200571f128cd4f88d067f2116f3620e0ac2d2844c2f3d016`. The earlier no-frame runner diagnostic also passed its two-entry local manifest check (`5957c7944db104058be7d876a0c5b26a832b8b511561f4b46c05c4df883acb26`). Neither artifact has an external copy.

**Result:** Stage 4 remains `IN_PROGRESS`. The 10-run matrix and recorder exist, but no complete route dataset has been accepted. CARLA is stopped.

**Next action:** wait for user direction before restarting the pilot, reducing/optimising its output strategy, or changing the approved matrix.

## 2026-09-23 13:32–14:01 UTC — Stage 4 Bounded Asynchronous Writer Benchmark

**Type:** throughput optimisation and validation; not a baseline route-completion drive.

- Reworked `scripts/stage4_baseline.py` so CARLA buffers are detached at capture time and RGB, lossless raw semantic IDs, and CARLA CityScapes-palette previews are encoded in a bounded four-worker queue. The tick loop applies measured backpressure at the queue limit rather than dropping frames. Resource sampling was reduced to every ten accepted samples plus endpoints.
- Retained two failed implementation probes: `20260923T133242Z-async-writer-smoke-ab869f` called `carla.Image.save_to_disk()` concurrently and timed out after capture; `20260923T133736Z-async-writer-buffer-smoke-664bbb` used an incomplete manually reconstructed palette. They are finalized with manifests. The corrected 5 s smoke `20260923T134010Z-async-writer-local-palette-smoke-cbcacd` accepted eight samples, passed all 216 PNG checks and visual RGB/semantic contact-sheet review, and showed 2.656 s writer backpressure.
- The user-requested 120 s simulation-time benchmark `20260923T134157Z-async-writer-120s-throughput-28fd4a` recorded 238 samples over 118.500 s. It wrote 4,284 RGB, 2,142 raw semantic, and 2,142 palette-preview PNGs. All 6,426 PNGs passed CRC/decode/dimension/frame/timestamp/ego-body checks; no duplicate callbacks or collision occurred. Recording-phase wall time was 710.624 s, including 71.187 s bounded-writer backpressure; output at summary time was 8,785,235,973 bytes. The final local directory is 8,787,483,638 bytes; its 6,441-entry manifest passed local verification and has SHA-256 `5855146939f2fe225c472d304be524d3176fe5a124d1c14f5ebfcc3b23303873`.
- This run is explicitly a throughput benchmark, not baseline evidence. It continued after the 508.150 m route endpoint, so the route-deviation acceptance criterion is not evaluated; no baseline matrix cell is complete. The server was no longer running after recorder completion; `scripts/stop_carla.sh` confirmed no remaining `carla-server` container.

**Next action:** on user instruction, run a fresh route-completion pilot using the verified writer, validate it as a baseline record, and export it before continuing the matrix.

## 2026-09-23 16:04–16:07 UTC — Shorter Routes and Camera-Free Drive Validation

**Evidence type:** user-requested geometry revision; artifact-confirmed local CARLA tests.

- The user asked to retain the middle half of routes 1–3, crop route 4 to one/two turns and 40–50 working points, and crop route 5 to about two turns and 60–70 working points. The objective was shorter driving time and less recorded data. Added `scripts/stage2_route_trim.py` to choose contiguous slices of the signed September-19 reference chains and reuse the existing adaptive-spacing/turn-detection helpers; no new map search or camera rendering was required.
- First offline run `20260923T160409Z-shorter-routes-5e6883` generated geometry but failed its metadata update because `carla.__version__` does not exist. Retained and finalized it as failed. Replaced that lookup with installed-package metadata and created a fresh revision `20260923T160431Z-shorter-routes-b72a9d`.
- Source windows (inclusive) are 28–83, 32–93, 31–94, 34–158 and 19–132. New lengths are 110.000 / 125.106 / 122.838 / 251.108 / 225.939 m; working counts are 12 / 32 / 32 / 44 / 60. Route 4 retains one left turn before the complete original bridge plus 12 m exit margin, and is named `route_04_turn_then_bridge`. Route 5 retains the middle left/right pair, and is named `route_05_two_turns`. All dense waypoint fields other than local ordinal remain identical to the source slice.
- Ran existing `stage2_autopilot_routes.py` once for all five routes in `20260923T160409Z-shorter-routes-autopilot-b8548d`. CARLA reconstructed every waypoint and verified all 416 `next(2.0)` edges. Every new start spawned, every route completed, collision counts were zero, max deviations were 0.996–1.246 m, and every post-finish stop passed. The trajectory approached every retained turn centre within 0.292 m; route 4 passed the recorded bridge exit before braking. The driving phase took only 1.2–2.2 wall seconds per route without cameras, plus server/map setup.
- Same-controller/seed comparison against the historical five-route drive measured simulation driving times 30.35→16.05, 23.65→12.70, 28.10→15.35, 41.45→14.90 and 63.15→29.85 s. Total 186.70→88.85 s, a 52.41% reduction; the 4 s braking/stopped observation is excluded consistently. No new image-volume or recorder-wall-time claim is made. `duration_comparison.json` preserves the basis, image digest, controller seed and executed script hash.
- Updated Stage-4 source, route IDs and pilot plus the autopilot default to the validated revision. The original route manifest still passed all nine entries. New geometry (11 entries), drive (21 entries) and failed-generator (10 entries) manifests all verified locally. New runs remain local-only. Stopped CARLA after tests; no camera recording was started.

**Result:** all requested route reductions and efficient validation are complete. Stage 2 remains DONE; Stage 4 remains IN_PROGRESS. The next camera run should use `route_05_two_turns` and the revised matrix, followed by measurement/validation and export.

## 2026-09-23 16:15–16:21 UTC — Stage 4 Shortened-Route Baseline Pilot

**Type:** completed local baseline-matrix cell; external preservation still pending.

- Recorded the first current-matrix cell with `scripts/stage4_baseline.py`: `route_05_two_turns` under `clear_day`, using the shortened, drive-validated route revision and the bounded four-worker PNG writer.
- The drive completed at 217.939 m projected progress of its 225.939 m route (required 214.642 m), with 0 collisions, 1.246 m maximum deviation, and a passed post-finish stopped-vehicle check. It accepted 58 same-frame 18-sensor samples over 28.500 s of simulation time.
- The run contains 522 RGB, 522 raw 8-bit semantic-ID, and 522 CityScapes palette-preview PNGs. `validation.json` passed all timing, frame/pose alignment, count, PNG-integrity and ego-body checks; `baseline_validation.json` passed all route, collision and stop checks. RGB and semantic contact sheets were visually reviewed.
- The recording phase lasted 170.993 wall seconds, including 2.160 s explicit writer backpressure. Output at summary was 2,203,449,831 bytes (77.314 MB per accepted simulation second); final run size is 2,205,036,691 bytes. Finalization generated a 1,581-entry manifest with SHA-256 `1bb4bbace43e741cc94316f10748fb2b4d7f5ac6337554623b7fb1f34098249c`; local entry-by-entry verification passed.
- Stopped `carla-server` after completion. The artifact is registered as `stage4-baseline-pilot-short-route05-clear-day-20260923` with `backup_status=not_copied`.

**Result:** Steps 1–2 of the Stage-4 pilot workflow are complete locally. Step 3 requires a Mac-side copy and manifest verification; do not start a second baseline cell until this first copy is preserved.

**Next action:** from the Mac, use the documented `rsync` pull for `20260923T161516Z-baseline-pilot-route05-two-turns-clear-day-895150`, then run `scripts/verify_export.py` against the copied directory and record the result.

## 2026-09-23 16:31 UTC — Stage 4 Sequential Batch Prepared (Not Run)

**Type:** user-authorized operational preparation; no new CARLA experiment.

- The user authorized temporarily deferring the matrix policy of exporting after two completed runs and asked for a `tmux`-friendly script that records the nine remaining cells without chat supervision. The per-run free-disk safety threshold remains active.
- Added `scripts/stage4_batch.py`. It reads the fixed matrix, detects completed cells only from finalized passing `baseline_validation.json` records, deterministically orders the remaining cells from the stored seed, and never launches concurrent recorders. Each successful recorder invocation is finalized and locally manifest-verified before the next starts. A failure or Ctrl-C stops the batch and preserves/finalizes the current run; CARLA is stopped in the cleanup path. It writes a human-readable log and JSON result summary under `logs/`.
- Checked with `python -m py_compile` and `--dry-run`. The dry run made no writes or CARLA calls and found exactly one completed cell (`route_05_two_turns`/`clear_day`) and nine remaining cells. `git diff --check` passed.

**Result:** batch infrastructure is ready but no batch recording has been started. The external-copy requirement remains pending and is not waived.

**Next action:** user starts the documented command in a `tmux` window, then reports the batch summary path and exit status for review.

## 2026-09-23 16:33–17:03 UTC; closure recorded 21:01 UTC — Stage 4 Complete Baseline Matrix

**Type:** completed and validated Stage-4 dataset; external verification is user-reported with supplied checksum command output.

- The first `tmux` batch completed seven cells, then the user interrupted the eighth retry. The supervisor finalized that partial run as `incomplete`, generated its 385-entry manifest and locally verified it. The second batch completed the successful retry and final outstanding cell. Both batches stopped `carla-server` successfully.
- The ten accepted cells cover every route/weather pair once. All have `outcome=completed`, zero collisions, a stopped ego vehicle, route deviation no greater than 1.246 m, and passing `validation.json` plus `baseline_validation.json`. Their local manifests were rechecked after the batches: all 9,303 signed entries passed.
- Accepted totals are 339 2 Hz samples, 3,051 RGB + 3,051 raw semantic-ID + 3,051 palette-preview PNGs, 164.500 s accepted simulation span, 1,076.278 s recording wall time, 24.292 s writer backpressure and 12,904,099,739 finalized bytes. Clear and wet representative RGB/semantic contact sheets were visually reviewed. The long-route stopped pilot and the current interrupted retry remain registered as incomplete, not silently removed.
- The user copied the full `runs/` and `logs/` trees to `/Users/madness/Science/CARLA/runs_1/` and `logs_1/`. They supplied the Mac-terminal result of two checksum-mode `rsync -nrc --itemize-changes` comparisons, each with no difference output. The artifact registry records this as externally verified while explicitly identifying the proof as user-supplied.

**Result:** Stage 4 is `DONE`: the chosen matrix is complete, every accepted record validates, failures are retained, weather settings are recorded in the fixed matrix, and the data/log copies are checksum-verified off VM. No CARLA or validator process is active.

**Next action:** begin Stage 5 only on a separate request; it is a literature/repository review and needs no CARLA recording.

## 2026-09-24 10:22 UTC — Stage 5 Literature and Repository Review Complete

**Type:** documented primary-source review; no CARLA, model API, or author code execution.

- Reviewed the user's detailed analysis of ScenarioGen, TTSG, TrafficComposer, and ChatScene against assignment item 2 and the project's CARLA 0.9.16, `Town01_Opt`, fixed-route, API-only, and restricted-executor constraints.
- Replaced the report placeholder with a compact four-work comparison covering method, LLM role, CARLA/code status, reported evidence, limitations, and concrete project use. The report explicitly separates runtime scenario construction from Unreal geometry authoring and rendered-image post-processing.
- Added the four primary publication/repository pairs to the knowledge source index and recorded the shared conclusion: use a passive versioned SceneSpec, strict validation, a fixed allow-listed executor, post-application checks, and replay from resolved configuration.
- Accepted that architecture as D23. This is a design decision informed by literature, not an implementation or CARLA experiment. The source code was inspected but not run, author-reported metrics were not independently reproduced, and the animal-asset blocker remains outside the capability of the reviewed methods.

**Result:** Stage 5 meets its acceptance criteria and is `DONE`. Evidence is in `report/report.md` section 2, `docs/knowledge.md` section 8 and sources S18–S21, and `docs/decisions.md` D23.

**Next action:** Stage 6 begins by verifying available API providers/model IDs and the trial-spend limit, then implementing and locally testing the SceneSpec/validator/executor/replay path before model comparison calls.

## 2026-09-24 11:09 UTC — Stage 6 Pre-API SceneSpec and CARLA Validation

**Type:** local implementation and CARLA validation; no LLM endpoint, key, provider lookup or internet dependency.

- Added `configs/stage6_scene_editing.json`, strict passive `SceneSpec`/refusal parsing in `scripts/stage6_scene_spec.py`, a fixed allow-listed CARLA executor in `scripts/stage6_local_scene.py`, and deterministic valid/invalid/refusal fixtures. The model-facing format contains route-relative anchors only; it cannot carry Python, Scenic, direct world coordinates, `NaN`, duplicate keys or unrecognised fields.
- Added seven Stage-6 unit checks. They passed together with the existing eight Stage-3 checks. The validator distinguishes syntactically bad JSON, policy violations, structural spatial conflicts, live map/blueprint failures and a correct structured animal refusal.
- Validated the selected narrow envelope on `Town01_Opt`/`route_01_straight`: the one-Audi wet scene `20260924T110210Z-local-straight-parked-vehicle-observer-fix-213a80` and its fresh-world replay `20260924T110353Z-local-straight-replay-ad721d` passed camera validation (3 aligned 2 Hz samples, 81 PNGs), semantic-supported visibility, zero collisions, route completion and stopped ego. The same saved SceneSpec reproduced the actual transform and result. The two-Audi `clear_day` scene `20260924T110725Z-local-straight-composite-safe-af8031` also passed.
- Retained and finalized five failed diagnostics rather than discarding them: two sandbox-loopback client failures, a right-side target that remained on a driving lane, an observer camera callback wait fixed before the accepted run, and a point that conflicted with static geometry. The live map showed that a JSON-valid position is not necessarily spawnable; `try_spawn_actor` stays a mandatory feasibility check. A local structured moving-animal refusal is preserved in `20260924T110820Z-local-animal-refusal-85c432`.
- Every accepted local run has a manifest and local self-verification. No external copy exists yet, and the API-comparison portion of Stage 6 has not started.

**Result:** Stage-6 work items 1–4 from the attached plan are complete for the initial straight-route envelope. Stage 6 remains `IN_PROGRESS` because provider/model IDs, credentials/access, spending limit, shared API prompt protocol, model attempts, latency/cost and comparison are still absent.

**Next action:** after connectivity returns, verify provider access and a trial-spend limit before any API request; then implement the adapter without widening the verified SceneSpec capability list.

## 2026-09-24 12:10 UTC — Stage 6 API Access and Model Inventory

**Type:** authenticated provider-access check; no text generation, CARLA connection, or model-comparison attempt.

- Added `scripts/stage6_api_access_check.py` and three unit checks. It reads local `.env` without printing secrets, makes only authenticated model-list requests, and records endpoints, HTTP status, latency and model identifiers in a run directory. The Model Studio parser handles its documented `output.models` response separately from OpenAI-compatible `data`.
- The sandboxed access probe `20260924T120700Z-api-access-check-5610fb` failed before authentication because the sandbox blocks provider networking. The elevated retry `20260924T120719Z-api-access-check-elevated-31c96f` authenticated both credentials but was finalized incomplete because version one did not retain Model Studio model IDs. Both manifests are retained.
- The corrected run `20260924T120821Z-api-model-inventory-5f0d01` passed: OpenAI returned 132 model IDs including `gpt-6-astra` in 1.075 s; Alibaba Model Studio authenticated at the Singapore endpoint and returned 161 Qwen IDs including `qwen3.8-27b` and `qwen3-8b` in 2.192 s. Its three-entry manifest was independently rechecked. No text, structured response, token usage, cost, CARLA operation or model-quality result was produced.
- Updated `.env.example` with the authenticated provider settings and initial IDs only; `.env` remains ignored, unprinted and untracked.

**Result:** provider credentials, one DashScope region and advertised target model IDs are now artifact-confirmed. Stage 6 remains `IN_PROGRESS`: a spend limit, common API adapter, fixed prompts, actual completions, validation, timing/cost and comparison are not yet present.

**Next action:** establish a small explicit spend limit, then add one common adapter and make the first constrained `SceneSpec` completion without starting CARLA.

## 2026-09-24 12:19 UTC — Stage 6 Bounded API Generation Smoke

**Type:** two paid API requests, one per provider; strict local validation only, no CARLA process.

- Added `scripts/stage6_api_generation_smoke.py` with three unit checks. It makes at most one request per selected provider, caps output at 16–256 tokens (192 used), saves prompt/request/raw response/usage/timing, and never writes the API key. OpenAI uses the documented Responses JSON mode; DashScope uses its OpenAI-compatible chat JSON mode with thinking disabled for this small request.
- `20260924T121813Z-api-generation-smoke-611d18` passed for OpenAI `gpt-6-astra` and DashScope `qwen3-8b`. OpenAI reported 250 input and 146 output tokens, 5.817 s API latency; DashScope reported 265 prompt and 138 completion tokens, 4.508 s. Both responses were parsed and resolved without manual correction into the same permitted parked-Audi target transform. Their raw responses are retained locally; no secret appears in the run.
- The run deliberately did not start CARLA, so it proves generation and local validation only. It does not prove provider-enforced strict schemas, Qwen-27B behaviour, actual price, repeated success, visual effect, or executor/CARLA success. Its 12-entry manifest was rechecked locally.

**Result:** the first paid Stage-6 model responses are artifact-confirmed and safe to pass onward only through the existing validator. Stage 6 remains `IN_PROGRESS`.

**Next action:** refactor this bounded smoke path into the common API adapter, fix prompts/retry/timeout settings, then run one saved generated SceneSpec through the already-tested CARLA executor.

## 2026-09-24 12:30–12:45 UTC — Stage 6 Fixed API/CARLA Pilot

**Type:** completed local Stage-6 pilot; paid API generation plus CARLA execution; external copy still pending.

- Added `configs/stage6_api_protocol.json` and `scripts/stage6_api_adapter.py`. The protocol was fixed before paid calls: `gpt-6-astra`, `qwen3.8-27b`, `qwen3-8b`; simple/composite/impossible-animal prompts; one repeat, zero automatic retries, 60 s timeout and 256 output-token ceiling. The adapter records only sanitized request data, raw provider response, extracted JSON, strict local validation, timing and reported usage; it never executes model text. Exact task matching rejects a syntactically valid but incorrectly placed object.
- `20260924T123036Z-api-fixed-protocol-884ef7` completed all nine planned first attempts. Every SceneSpec passed syntax, policy and exact-request validation; each animal request returned the required `unsupported_capability` refusal. Reported API latency spans 3.465898–10.565166 s. Usage is retained but cost is `not calculated`, because no dated provider price record was retrieved. A wrapper return occurred while the last Qwen request was finishing; safe resume read the eight already saved attempt results and only wrote the missing result, without reissuing them.
- Extended `scripts/stage6_local_scene.py` with `--api-attempt-result`, which binds a replay to a passed saved adapter result and carries provider/model/usage/API/local-validation timing into the CARLA evidence. `20260924T123330Z-api-provenance-local-check-627a7b` first validated that binding without a CARLA connection.
- Executed all six accepted model SceneSpecs in fresh `Town01_Opt` worlds. Each has before/after RGB, three aligned 2 Hz 18-sensor samples (81 PNGs), semantic-supported parked-vehicle visibility, zero collision, completed 110 m route and stopped ego. Selected CARLA application/validation wall time is 39.186744–41.130043 s. The first GPT simple-scene process completed after the orchestration handle returned; its extra passing replay is preserved and registered rather than discarded or substituted.
- Added `scripts/stage6_build_comparison.py`; `stage6_comparison.json` and `.csv` link every API attempt to execution evidence and leave cost explicitly uncalculated. Twenty focused Stage-6/Stage-3 checks and `py_compile` passed. The protocol run, provenance check and seven execution runs were finalized and all nine manifests rechecked locally (61, 7, then seven sets of 100 signed files). `.env` was confirmed ignored and untracked. CARLA was stopped.

**Result:** the technical pilot satisfies the Stage-6 acceptance criteria locally: the three accessible variants followed one saved protocol, all first attempts are visible, scenes replayed from saved configurations without new API calls, and the comparison retains latency/usage/validation/execution evidence. It is intentionally one repeat only, does not infer provider cost, does not prove provider-enforced strict schemas, and does not validate animal behaviour or a statistical model ranking.

**Next action:** make an external copy of `20260924T123036Z-api-fixed-protocol-884ef7` plus the six selected passing CARLA runs, verify each copy with `scripts/verify_export.py`, then record destinations/check time in the artifact registry. Do not mark those records externally backed up before receiving the verification output.

## 2026-09-24 12:59 UTC — Stage 6 External Copy Confirmed

**Type:** user-reported external checksum verification; no VM-side data mutation.

- The user ran `rsync -avP` from the Mac for the full `/home/Ubuntu/carlas_tasks/runs/` and `logs/` trees to `/Users/madness/Science/CARLA/runs_1/` and `logs_1/`.
- They then supplied Mac-terminal output for `rsync -nrc --itemize-changes` over both source/destination pairs. Both comparisons returned no itemized differences. This is direct checksum-mode evidence reported by the user, not an agent-operated Mac check.
- Updated the nine new Stage-6 pilot registry rows with their actual Mac locations and `backup_status=verified`. No source artifact, model response, API key or VM resource was changed.

**Result:** the Stage-6 technical pilot and its selected external preservation requirement are complete. The next independent stage is the moving-animal asset decision/validation.

## 2026-09-24 13:13 UTC — Stage 7 Initial Animal-Asset Audit

**Type:** local package inspection and source review; no CARLA server, image modification, asset download, LLM call, or scene change.

- Confirmed that no CARLA container is running and that the locally installed server image remains `carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953`.
- Used a temporary Docker container with `--rm --network none` to inspect `/workspace/CarlaUE4/Content` by filename. Its animal-name search found `DogHouse` assets only; Blueprint roots did not contain an Animal directory. This supplements, but does not replace, the prior live blueprint-catalogue observation of 214 IDs with zero animal candidates. It does not prove that every arbitrarily named hidden mesh is absent.
- Read the official 0.9.16 prop-authoring procedure. A raw external mesh must be imported through the Unreal Editor, registered, and included in a newly made CARLA package. That path violates U02, so an FBX/GLB download is not a valid runtime-only solution.
- Investigated one possible cooked boar pack only at its public source. It declares itself an untagged pre-release and pins its content pack to exact CARLA 0.9.15. It supplies no 0.9.16 compatibility evidence, so it was not downloaded, installed, or used as a candidate.

**Result:** Stage 7 is `IN_PROGRESS`, with the exact blocker narrowed to a licence-clear prebuilt animal package/blueprint that explicitly supports CARLA 0.9.16. No animal scenario has been created and Stage-7 acceptance is not met.

**Next action:** continue source discovery without changing the image; only then run the isolated spawn, RGB, semantic, height and collision probe. If no exact-version package exists, request a user decision about relaxing the runtime-only constraint or retain item 4 as an explicit limitation.

## 2026-09-24 13:24 UTC — Stage 7 AnimaSim Source Verification

**Type:** public-source and local read-only installation-path verification; no asset archive download, image mutation, CARLA server, scene change, or LLM call.

- Verified Git refs for `danwahl/animasim`: tag `v0.2.1` resolves to the current public commit. The release API lists `animasim-carla-0.2.1.tar.gz`, 243,116,126 bytes, with SHA-256 `4462ef4099a7057764c7d9fdf5788efdf0ddd6daad156e55440c55a8a834e071`; the author's release text explicitly calls it a cooked standalone CARLA 0.9.16 package.
- Read the versioned CARLA README, manifest and `spawn_deer.py`. They declare twelve `static.prop.<animal>` blueprints, including `static.prop.deer`. The objects are unanimated static meshes tagged `Dynamic`; there is no dedicated Animal semantic class. The README distinguishes author-side cooking from consumer-side import and says consumers use `ImportAssets.sh` with a stock 0.9.16 build.
- Confirmed inside a temporary `--rm --network none` instance of the pinned Docker image that `/workspace/ImportAssets.sh` and `/workspace/Import/` exist. The script only enumerates `Import/*.tar.gz` and extracts them; this supports a derived-image test that leaves the official base image unchanged.
- Confirmed the AnimaSim repository code licence is MIT and the declared Quaternius source-model page marks the Ultimate Animated Animal Pack CC0. The archive contents and attribution files still require local inspection after download.

**Result:** AnimaSim is a plausible, exact-version, prebuilt Stage-7 candidate and removes the earlier source-availability blocker. It is not yet validated in this project: do not claim import success, blueprint availability, visual quality, semantic pixels, collision, Traffic Manager response, or motion until the isolated probe completes.

**Next action:** on user approval, download only the pinned release archive into a temporary staging directory, verify its published SHA-256 and contents, build a separate derived CARLA image, and run `static.prop.deer` through the minimal spawn → RGB → raw-semantic → height/bounding-box → collision test.

## 2026-09-24 13:55 UTC — Stage 7 AnimaSim Runtime Validation

**Type:** derived-image CARLA API probe; no Unreal Editor/build and no LLM call.

- Downloaded the public AnimaSim v0.2.1 archive into an isolated temporary directory. Its 243,116,126 bytes and SHA-256 exactly matched the release (`4462ef4099a7057764c7d9fdf5788efdf0ddd6daad156e55440c55a8a834e071`). Archive contents included the cooked AnimaSim package and deer assets.
- Built local derived image `carlasim/carla:0.9.16-animasim-v0.2.1` (`sha256:2d6fb34a8e78b159b225ff206473854f040c3e8612dba3c6e22ae85d52f5b9b9`) using only `/workspace/ImportAssets.sh`. Labels retain the pinned base digest and the archive hash; the base image was not changed. The live 0.9.16 blueprint library exposed all 12 documented imported animal IDs, including `static.prop.deer`.
- Added `configs/stage7_animasim_probe.json` and `scripts/stage7_animal_probe.py`. They limit this pre-LLM probe to Town01_Opt route 1, clear weather and one front-centre RGB/semantic pair, preserve raw semantic IDs, persist route-relative actor commands/snapshots, and enforce grounded height, full endpoint reach, per-tick movement bound and collision trace.
- Retained three finalized diagnostics: actor API `semantic_tags` was empty for the imported prop (`20260924T133953Z-animasim-deer-front-probe-dbb71d`); the next run initially used class 20 before direct enum inspection identified CARLA `Dynamic=21` (`20260924T134221Z-animasim-deer-front-probe-retry-65ee88`); the corrected eight-sample run had not reached the 12 m endpoint (`20260924T134700Z-animasim-deer-front-probe-dynamic21-d324b4`). They are registered rather than overwritten.
- The grounded accepted run `20260924T135331Z-animasim-deer-front-probe-grounded-d91894` passed all checks. It recorded 14 aligned 2 Hz RGB/raw-ID/preview pairs. `static.prop.deer` was visually reviewed in RGB and preview, gained 1,187–1,544 raw Dynamic=21 pixels above baseline, had bbox-min/ground difference 0.0 m, and completed the 12 m trajectory at 2 m/s with 139 0.05 s commands, maximum 0.100006 m requested step and 0.0000076 m endpoint error. A deliberately driven ego collision sensor recorded `static.prop.deer`; no Traffic Manager response was tested. CARLA client/server were 0.9.16. The 55-file manifest passed a local source-to-source hash check; output is 38,025,444 bytes and local-only.
- Updated `scripts/stop_carla.sh` so the expected image is supplied by `CARLA_IMAGE`, retaining its refusal to stop a differently imaged container. Both derived-image servers were stopped successfully after their probes.

**Result:** the asset feasibility gate is complete. AnimaSim deer is now the only verified Stage-7 animal capability, with explicitly kinematic (unanimated) motion and direct collision geometry. Stage 7 remains `IN_PROGRESS`: its SceneSpec/executor extension and common GPT/Qwen protocol are not yet implemented.

**Next action:** add only deer type, route-relative trajectory, speed and start-time fields to the strict SceneSpec; then use identical model requests and test the accepted specifications before starting Stage 8 full-rig drives.

## 2026-09-24 14:08 UTC — Stage 7 Strict SceneSpec and Three-Model Replay

**Type:** bounded API protocol plus saved-provenance CARLA replays; no model code execution.

- Added `configs/stage7_scene_editing.json`, `scripts/stage7_scene_spec.py` and a fixture. Version 1.1 is a separate strict extension and leaves Stage-6 v1.0 untouched. It accepts only the measured deer, 32 m route anchor, named +6 m to -6 m lateral crossing, 2 m/s and 0 s start; only an integer seed varies. It rejects direct coordinates, asset IDs, code, controllers, animation and traffic reaction fields. `scripts/stage7_animal_probe.py` can apply a separately validated SceneSpec and records its digest/provenance; it never executes response text.
- Added fixed protocol `configs/stage7_api_protocol.json` and `scripts/stage7_api_adapter.py`. Run `20260924T140505Z-api-verified-deer-crossing-e6313d` made exactly three first-attempt JSON-mode calls: OpenAI `gpt-6-astra`, DashScope `qwen3.8-27b` and `qwen3-8b`. All HTTP responses and strict task checks passed. API latencies were 7.506985, 3.334434 and 6.004154 s; usage was retained but price deliberately was not calculated. The resulting SceneSpecs were identical outside seed (GPT 1; both Qwen 42).
- Replayed each saved passed SceneSpec in the derived AnimaSim image: `20260924T140639Z-api-gpt-deer-crossing-9284ba`, `...-api-qwen27-deer-crossing-4146e3` and `...-api-qwen8-deer-crossing-9490d8`. All three passed grounded spawn, 14 aligned front-centre RGB/raw-ID/preview observations, Dynamic semantic effect, bounded complete trajectory and direct collision checks. Dynamic=21 delta ranges were 1,187–1,544; 1,194–1,543; and 1,185–1,544 pixels respectively. RGB and semantic preview from the GPT replay were visually reviewed.
- Added `scripts/stage7_build_comparison.py`; its `stage7_comparison.json` binds API timing/usage/response digest to replay metrics and declares scope/limitations. All four final manifests passed local source-to-source verification (24 entries for API, 58 each execution). The three replays and API record are registered as local-only artifacts. CARLA was stopped.

**Result:** Stage 7 is `DONE`. The project has a real, licence-traced animal and a safe LLM-to-CARLA path for only the measured capability. This does not demonstrate leg animation, full-rig edited recordings, Traffic Manager braking or an open-ended model-quality comparison.

**Next action:** Stage 8 should replay the saved animal SceneSpec on the selected equivalent routes/weather with the existing full nine-position RGB/semantic rig, then compare against the baseline matrix.

## 2026-09-24 14:40 UTC — Stage 7 Completion and Backup Confirmation

**Type:** project-state closure; no CARLA, API, asset, or VM operation.

- The user confirmed that a Stage-7 backup was made and requested completion to be recorded before committing and pushing the implementation.
- Retained Stage 7 as `DONE`: its acceptance was already artifact-confirmed by the grounded AnimaSim probe, constrained three-model protocol, and saved-provenance replays.
- Marked the nine Stage-7 registry entries `backup_status=user_reported`. No external destination, transfer output, or manifest comparison was supplied, so no entry is called `verified` and `external_location` remains unrecorded.

**Result:** Stage 7 is formally closed with user-reported external preservation and artifact-confirmed local manifest validation. The next independent task remains Stage 8 full 18-sensor edited drives and comparison to matching baseline cells.

## 2026-09-24 15:10 UTC — Standalone Final Report Draft

**Type:** user-directed scope closure and report preparation; no CARLA, model API, dataset mutation, publication, or VM operation.

- Recorded the user's decision not to run Stage 8. Kept it `TODO` rather than presenting an unperformed comparison as complete; Stage 9 is now `IN_PROGRESS`.
- Added `report/final_report_ru.md`, a standalone 2,300-word Russian Markdown report. It contains no calendar dates, internal stage names/numbers, title page, or result table. It uses logical sections, plain language, route-selection details, local limitations, a final conclusion, and repository links.
- Selected only artifact-confirmed visuals and made five portable composites in `report/assets/final_report/`: RoadLines before/after, route-selection overview, nine-camera RGB/semantic sheets, an LLM-generated two-Audi scene, and deer RGB/semantic motion. The source runs were not modified; the report copies total about 4.7 MiB.
- The route image is explicitly captioned as the visual-selection geometry before operational shortening/reordering. The animal section explicitly limits the evidence to kinematic motion, a front-centre probe and direct collision geometry, not leg animation, a full-rig edited-drive dataset or Traffic Manager braking.

**Checks:** all five image links resolve locally; the Markdown has no table rows, date strings or `stage`/`этап` wording; `git diff --check` passes. Pagination depends on the renderer, but 2,300 words plus five figures is expected to fit the requested 3–8-page range in a normal report layout.

**Result:** the requested report draft is ready for user review. It is not committed, pushed or published yet.

## 2026-09-24 15:33 UTC — Final Report Private-Branch Handoff

**Type:** user-authorized Git commit and push; no report publication, repository-visibility change, external upload, CARLA run, or model API call.

- Staged only the standalone report, its five PNG figures, and the related README/status/decision/worklog/working-report updates.
- Rechecked the staged diff for whitespace errors and reviewed its file/size summary before committing.
- Created commit `347d8a6` (`docs: add final Russian report`) and pushed it from local `Dev` to the existing private `origin/Dev` branch.

**Result:** Git reported `5e8af47..347d8a6  Dev -> Dev`. The report is preserved in the private remote. User review and any later public delivery remain separate actions requiring explicit direction.

## 2026-09-24 21:03 UTC — Pre-Deletion Preservation Audit

**Type:** local read-only integrity and Git-remote audit; no VM, CARLA, dataset, API, or publication operation.

- Confirmed a clean worktree at `543a348` and zero ahead/behind commits on `Dev`; authenticated `git ls-remote` returned the same `543a3483b8656bd60a7948cd8e3a3cf65559bc31` for `origin/Dev`.
- `git fsck --full` found no corruption. Its dangling-tree notices are unreachable historical objects and do not affect the checked-out or remote branch.
- Enumerated 94 directories in `runs/`; each has `manifest.sha256`. Recomputed the source hashes using `scripts/verify_export.py RUN RUN` for every directory: all 94 passed, covering 20,867 signed files. Nine early intermediate/diagnostic directories are not registry rows, but are retained under `runs/` and so included by the selected whole-tree export.
- Measured the current Mac transfer sources: `runs/` 27 GiB, `logs/` 156 KiB, and `/home/Ubuntu/.codex/sessions/` 294 MiB (28 files). `.env` is present and ignored; Git tracks no `.env`, PEM, or key file paths. No CARLA/stage workload appeared in the process audit.
- The Mac destinations cannot be inspected from this VM. A completed `rsync` alone is therefore not recorded as checksum verification in this entry; the user must preserve zero-difference `rsync -nrc --itemize-changes` output for all three transferred trees before deleting the VM.

**Result:** the VM-side source data and private `Dev` history are internally consistent and the latest remote commit is confirmed. External preservation remains user-operated and awaiting Mac-side checksum comparison output.

**Next action:** run the documented Mac comparisons; if each has no itemized differences, fetch/clone `origin/Dev` on the Mac and the VM may be deleted at the provider panel without any repository/publication action.

## Template for the Next Entry

```text
Date and time with time zone:
Stage / assignment item:
Evidence type: completed and verified / reported / hypothesis
Goal:
What changed:
Commands or links to working scripts (without keys):

How it was checked:
Actual result, including errors:
Artifacts and external copy:
Decisions / limitations:
Next concrete action:
```

When correcting an erroneous entry, add a dated clarification and link; do not hide history. If a measurement is absent, write `not measured`. For complex runs, a short entry with a link to machine logs is enough.
