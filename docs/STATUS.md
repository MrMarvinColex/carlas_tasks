# Current State

Updated: **2026-10-05**, Europe/Moscow. Prepared GPU VM at `/home/Ubuntu/carlas_tasks`.

## Current outcome

**DONE — install missing VM dependencies and validate the latest updates.** [Session evidence](../artifacts/20261004T221357Z-vm-validation-e9e494.json). Starting worktree was clean on `Dev`, commit `7b1a04b`. The commit containing this status preserves the test-fixture fix, acceptance configuration, small validation evidence and run registry. The user authorized committing and pushing these updates to `origin/Dev`.

- Installed `python3.10-venv`, `vulkan-tools`, FFmpeg 4.4.2; `.venv` contains CARLA 0.9.16 and editable `carla-research-tasks` 0.1.0. `pip check`, wheel build and isolated wheel import passed.
- All **123 offline tests passed** on the actual VM, plus input/docs, planning/dry-run, static SceneSpec, rig and three-camera synthetic checks. Hardened launcher mocks to discard ambient real server leases; all 123 tests passed again with an ambient lease sentinel, which stayed absent.
- Short live readiness: `20261004T221357Z-vm-validation-e9e494-rig-smoke`, three same-frame samples from nine RGB/semantic pairs; 54 sensor PNGs and 27 semantic previews. Dataset validation and local manifest verification passed. Separate RGB grid reviewed; original automatic contact-sheet warning records FFmpeg absence before its installation.
- Full live acceptance: `20261004T222412Z-baseline-route_01_straight-clear_day-r1-f5304f`, Town01_Opt/clear_day/Tesla, nine pairs at 2 Hz. **31 samples, 558 sensor PNGs, 279 previews; all 837 PNGs validated without warnings**. Same-frame pose/timestamp pairing, lossless semantic IDs, dimensions, timing, no duplicates and zero bottom-strip ego-body pixels passed. Route completed, zero collisions, maximum deviation approximately 1 m; vehicle stopped. RGB/semantic contact sheets reviewed.
- Runs are finalized with manifests and registered in [run registry](../artifacts/run_registry.jsonl). Full-run explicit registry reimport passed. Local integrity checks establish no external copy.

## Environment and process state

Ubuntu 22.04.5, kernel 6.8.0-107-generic, Python 3.10.12; RTX A6000 (49140 MiB), driver **580.126.20**. Driver was already working on the actual VM: no reinstallation/reboot was needed. Docker 29.4.0 and NVIDIA container toolkit 1.19.0 were reused. Passwordless `sudo -n docker` is required and supported by launch scripts; permissions were not changed.

Pinned CARLA image: `carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953`; actual image ID and client/server version equality are in session evidence.

Desktop stayed active throughout both live captures. Idle GPU memory was 35 MiB initially and 44 MiB after shutdown (under 0.1% of VRAM); no NVIDIA Xid/NVRM errors were found in the session kernel log. This proves the tested offscreen capture works with the desktop; it does not measure desktop-on/off throughput differences. Final free disk: approximately 227.7 GiB.

**No unfinished setup, capture or owned server remains.** Both captures left no dynamic actors and restored asynchronous world settings. Retry-02 supervisor completed with exit 0; the exact leased server was stopped and ports 2000/2001 are closed. Status/logs: `logs/20261004T221357Z-vm-validation-e9e494/`.

Preserved failed attempts: first sandbox-local supervisor lost its namespace without test results; host suite then passed. Validation attempt 01 inherited a real lease path into launcher fakes, so a fake-ID lease blocked launch. Retry 02 isolated the lease and passed; original state/log/evidence remains preserved. `tests/test_launch.py` now clears the inherited lease and the controlled ambient-lease regression passed. No CARLA driver failure was observed on the host.

## Limits and exact next action

- No live hosted-LLM calls: `.env` is absent and configured API-key variables are unset. API tests use fixtures/mocks. No local weights, animal image preparation or full matrix was requested.
- The generic `record` kernel remains synthetic-only; live CARLA backend M1 and later migrations are separate work in [library handoff](library-handoff.md). Existing live executors passed the checks above.
- Git preservation covers code, configuration and small evidence. Dataset images, raw logs, `.venv` and the Docker image remain VM-local and are excluded from Git. No VM deletion or off-VM run-copy verification occurred; all new run copies remain `not_copied`.

Exact next action: use this prepared `.venv` for the next requested experiment. The acceptance configuration is [one-cell VM check](../configs/vm_validation_20261005.json); its repeat 1 is complete, so its dry-run should report one completed cell. A newly requested measurement needs a new repeat/configuration identity rather than relaunching that completed repeat. For library development, explicitly resume M1 from its handoff; do not start it as an automatic continuation of VM setup.
