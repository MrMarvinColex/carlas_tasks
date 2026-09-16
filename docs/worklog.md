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
