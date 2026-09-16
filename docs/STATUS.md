# Current Project Status

Context-transfer date: **2026-09-16**, user timezone: Europe/Moscow. This is the initial state for a new Codex task, not a fresh inspection of the remote server.

## Current Position

A portable documentation package has been prepared. No project code was implemented. The user reported a successful infrastructure check on the current VM: CARLA 0.9.16 started in Docker using the GPU in offscreen mode, then the test container was stopped. The image remains on the VM. Raw logs were not provided.

**Next action:** open the server-side `~/carla_test_task`, inspect its contents and applicable instructions, integrate this package without overwriting existing work, and complete the missing part of stage 0.

## Stage Status

| Stage | Status | Known state / remaining work |
|---|---|---|
| 0. Environment and data safety | IN_PROGRESS | Server launch is user-reported; bootstrap scripts, Git remote, and a verified external copy are not confirmed |
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
- RTX A6000 48 GB, 6 vCPU, 96 GB RAM, 300 GB SSD; user-reported rate: $0.57/hour, Premium.
- SSH user: `Ubuntu`; working directory: `~/carla_test_task`.
- Docker through `sudo`; image `carlasim/carla:0.9.16` is cached on the current VM.
- The user reported that the test container was stopped. Verify the current state; do not treat it as a permanent fact.
- According to the provider-panel warning relayed by the user, stopping a container or VM does not end billing; deleting the instance does and is irreversible.

Full version information and limits: [environment.md](environment.md).

## Missing Access and Decisions

1. Private Git remote URL and actual project Git state.
2. External storage destination, Mac path or cloud bucket, access, and validated transfer.
3. Secure API-key restoration after VM deletion; actual providers/IDs and spending limits.
4. Availability of Town01/Town01_Opt in the current image and a working method to hide all markings.
5. Whether an animal can appear without Unreal editing.
6. Specific AV2 calibration and alignment of its ego origin with the chosen CARLA vehicle.
7. Route length, weather-condition count, and repeats after the first timing/size measurement.

Do not ask the user for all of these at once. Check available facts independently and ask only for a decision required by the current stage that is absent from the project.

## Latest Data Check

- Dataset: not created.
- `artifacts/index.csv`: header only; no experiment artifacts registered.
- Verified external experiment-data copy: absent or unconfirmed.
- Code pushed to remote Git: unknown.
- Ready to delete VM: **not confirmed**. Documentation on the Mac does not prove that existing server work is preserved.

## How to Update This File

After every work session, update the date, active stage, completed acceptance criteria, references to run IDs/logs/commits, unfinished processes, and exact next action. Move historical detail to `worklog.md`. Do not include secrets or large logs. State separately where an external copy is verified and where it is not.
