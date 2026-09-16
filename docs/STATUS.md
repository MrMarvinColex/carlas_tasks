# Current Project Status

Last inspected: **2026-09-16 21:19 UTC**; user timezone: Europe/Moscow.

## Current Position

Stage 0 acceptance is complete. The actual project root is `/home/Ubuntu/carlas_tasks` (not the historical `~/carla_test_task` path), under user `Ubuntu`, branch `00_-_stage`; the worktree was clean before this stage's edits. The private `origin` is reachable and `origin/main` resolved to `0e52c6a` before these stage-0 changes.

The reproducible client uses `.venv` with Python 3.10.12 and `carla==0.9.16`. The local image is `carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953`; the server/container versions were both 0.9.16. Run `20260916T210617Z-carla-smoke-beb230` captured and visually inspected one 800×600 RGB PNG, wrote a manifest, and passed local manifest verification. Its default map was `Town10HD_Opt`; this does not satisfy the separate Town01 test in stage 1. The `carla-server` container created for that run was stopped; no CARLA container is running.

**External-copy evidence:** the user ran `rsync` from Mac via the `carla-vm` SSH alias to `/Users/madness/Научка/CARLA/runs/20260916T210617Z-carla-smoke-beb230/`. The dry run listed 7 entries; the transfer completed; Mac-side SHA-256 validation reported `OK` for `config.json`, `metadata.json`, and `rgb/front.png`. The destination and manifest are registered in `artifacts/index.csv`.

The stage-0 implementation is preserved in private remote branch `origin/00_-_stage` at commit `ce26b8e`; no pull request, merge to `main`, visibility change, or publication was performed.

**Next action:** begin stage 1 only when separately requested. New data runs must be copied to the same Mac hierarchy and checksum-verified before the VM is treated as disposable.

## Stage Status

| Stage | Status | Known state / remaining work |
|---|---|---|
| 0. Environment and data safety | DONE | Bootstrap and repeat-safe setup, CARLA server/client RGB smoke test, run tracking/manifest, actual image digest, private Git remote, and verified Mac `rsync` copy are recorded; new-VM recovery remains untested |
| 1. Map and API | TODO | Town01, road-marking removal, and animal assets have not been tested in this project |
| 2. Routes | TODO | No routes or validated drives are included |
| 3. Cameras and recording | TODO | No AV2 log/calibration is selected; 18 cameras are untested |
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
2. Availability of Town01/Town01_Opt in the current image and a working method to hide all markings.
3. Whether an animal can appear without Unreal editing.
4. Specific AV2 calibration and alignment of its ego origin with the chosen CARLA vehicle.
5. Route length, weather-condition count, and repeats after the first timing/size measurement.

Do not ask the user for all of these at once. Check available facts independently and ask only for a decision required by the current stage that is absent from the project.

## Latest Data Check

- Dataset: not created; the stage-0 smoke artifact is not a dataset.
- `artifacts/index.csv`: contains the smoke artifact with `backup_status=verified`.
- Verified off-VM copy: `/Users/madness/Научка/CARLA/runs/20260916T210617Z-carla-smoke-beb230/`, confirmed by user-provided `rsync` and SHA-256 output at 21:19 UTC.
- Stage-0 scripts and documentation were committed and pushed to private `origin/00_-_stage` at `ce26b8e`.
- Ready to delete VM: **not confirmed**. Documentation on the Mac does not prove that existing server work is preserved.

## How to Update This File

After every work session, update the date, active stage, completed acceptance criteria, references to run IDs/logs/commits, unfinished processes, and exact next action. Move historical detail to `worklog.md`. Do not include secrets or large logs. State separately where an external copy is verified and where it is not.
