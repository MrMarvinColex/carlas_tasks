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

**Next action:** from the Mac, pull the full run to `/Users/madness/Научка/CARLA/runs/20260919T162408Z-av2-all-cameras-short-247e3f/`, run `scripts/verify_export.py` or an equivalent manifest check against that destination, then record the proof and mark Stage 3 DONE.

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
