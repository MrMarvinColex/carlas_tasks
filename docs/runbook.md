# Project Transfer, VM Operation, and Result Preservation

This document must become a tested operational guide. At transfer time it contains only procedures: setup/start/record/backup scripts do not yet exist. Add working commands here only after testing them, with date and log reference.

## 1. Initial Transfer From This Chat

1. Download the ZIP and save it on the Mac. It contains one top-level directory: `carla_test_task`.
2. Create or use a private Git repository. The remote URL is not yet provided. Move files into the repository root. If AGENTS/README/scripts already exist, compare and merge them; do not silently replace them.
3. Check `.gitignore`, the intended commit contents, and the absence of secrets. The original PDF is ignored by Git but included in the portable package. The English requirements summary is in `docs/requirements.md`.
4. Commit and push the documents to remote Git. Confirm the expected commit exists in the remote, not only locally.
5. Inspect `~/carla_test_task` on the current VM. If absent or empty, clone the repository. If non-empty, preserve and integrate existing work before cloning anything over it.
6. Open the server project root through VS Code Remote SSH. Begin a new Codex task from that root.
7. Ask the agent to recover context and complete stage 0. At startup it must confirm working directory, read documents, and distinguish the reported infrastructure check from uncompleted experiments.

Understanding check: the agent must know CARLA 0.9.16, Town01, 18 cameras at 2 Hz, API-only LLMs, unconfirmed animal availability, disposable VM, and fixed stages 0–9. It must know no project code is implemented. If it claims routes or a dataset already exist, correct it using `STATUS.md` before it acts.

## 2. Beginning Any Separate Task

- Read root AGENTS, current STATUS, requirements, and decisions.
- Check Git status, the requested stage, and existing processes. Do not start a second CARLA Server on occupied ports.
- Confirm the correct VM and project. Check free disk space before recording.
- Check prerequisites and prior artifacts. Never assume an external copy survived a deleted VM.
- Run a short test before a bulk operation. After every meaningful result, update work log and status.

“Stage 3” means the camera-and-recording stage, not automatically the rest of the assignment. If part is unavailable, retain an exact blocker and finish independent checks.

## 3. Recovery on a New VM

After stage 0 implementation, the recovery procedure must:

1. Create a VM with compatible GPU/OS and connect. Check SSH, Docker, and GPU access in containers; do not assume an unchanged IP or preinstalled toolkit.
2. Retrieve current code/documents from Git and only the previous-stage data required by the artifact registry.
3. Run the implemented setup to install pinned dependencies and pull the Docker image. Downloading the image again is expected.
4. Restore `.env` safely. Secrets are absent from Git and dataset archives; do not ask the user to paste keys into chat.
5. Record actual server/client versions, image digest, directories, and permissions. Start CARLA offscreen and retrieve a short test frame.
6. Resume the stage recorded in STATUS rather than rebuilding the project from scratch.

Until this procedure is tested, never state “recovery on a new VM has been verified.” Repeating setup on the same VM and recovering on a new VM are different evidence levels.

## 4. Structure of One Recorded Run

Proposed structure for stages 0–3:

```text
runs/<run_id>/
  config.json                 actual settings
  metadata.json               versions, commit, timestamps, run status
  calibration.json            raw and applied camera transforms
  scene.json                  environment and moving-object state
  route.json                  route used
  transforms.json             final ego-pose JSON
  rgb/<camera_name>/...       images
  semantic/<camera_name>/...  lossless class IDs
  previews/...                palettes, contact sheets, video
  logs/...                    diagnostics without secrets
  validation.json             completeness and alignment checks
  manifest.sha256             file list and checksums
```

Before finalization, a run is `running` or `incomplete`; after validation it is `complete` or `failed`. These are run states, not stage states. Interruptions, missing frames, API errors, and collisions need explicit reasons rather than disappearing from statistics.

Build a unique run ID from UTC time, a concise experiment label, and a suffix. Keep repeated attempts in separate paths. Show user-facing time in Europe/Moscow where useful, but store machine timestamps in explicit UTC/timezone form. Store simulation timestamps independently in seconds.

The final JSON contract and filenames must be fixed with the implementation. The stored protocol must relate every image to its pose, scene configuration, and exact LLM attempt.

## 5. Exporting Results

Before bulk collection, select one primary export path: rsync to the Mac or object/cloud storage. Verify it on a small set in stage 0. Google Drive for final delivery need not be the intermediate storage for every run.

If downloading from the VM, run the command below **in the local Mac terminal**. It is a template, not a ready command:

```sh
rsync -avP Ubuntu@SERVER_IP:carla_test_task/runs/RUN_ID/ /ABSOLUTE/MAC/BACKUP/RUN_ID/
```

Replace placeholders and check that the relative server path resolves from user `Ubuntu`’s home directory. Use a verified absolute path otherwise. Do not add `--delete`. The trailing slashes transfer the run contents into the target directory.

On the VM:

1. Finish recording, drain sensor queues, and close files. Actively changing data is not final data.
2. Run the dataset validator and record errors/final state.
3. Create a manifest relative to the run root: paths, sizes, SHA-256 checksums. Do not include the manifest itself in its own checksum set.
4. Transfer the run and manifest. Account for extra space when archiving; export the directory directly if a second complete archive will not fit.

At the destination:

1. Check that all expected files and sizes arrived.
2. Recompute SHA-256 and compare to the manifest. Do not accept only an rsync-complete message or cloud ETag as evidence of matching SHA-256.
3. Open final JSON and several images. Confirm data is available independently of the VM; for cloud storage, read/download from an external client.
4. Save the verification outcome and time. Update the artifact registry in Git, then push it.

## 6. Artifact Registry

`artifacts/index.csv` is a small Git-tracked table. It starts with a header and no invented rows.

| Field | Meaning |
|---|---|
| `artifact_id` | Unique registry record |
| `run_id` | Run that produced it; blank is allowed for documents |
| `stage` | Stage 0–9 |
| `kind` | dataset, logs, calibration, report, etc. |
| `created_at_utc` | Creation time in UTC |
| `git_commit` | Commit that produced the artifact |
| `source_relative_path` | Path inside project/run |
| `external_location` | Actual off-VM location; no tokens, signed URLs, or credentials |
| `manifest_sha256` | Checksum of the manifest file that identifies the set |
| `bytes` | Measured set size in bytes |
| `validation_status` | `pending`, `passed`, or `failed` data validation |
| `backup_status` | `not_copied`, `copied_unverified`, or `verified` external copy |
| `verified_at_utc` | External-verification time; blank before verification |
| `notes` | Limits and reference/path to verification outcome |

`backup_status=verified` means files match the manifest at the external destination. Do not set it after checking only the source. If data changes later, make a new version/manifest and verify again.

## 7. Ending a Session and Preparing for Delete

Check in order:

1. Important files are no longer changing; runs are finished or honestly marked incomplete/failed.
2. Code/doc changes are saved. Review untracked and ignored files so useful results are not missed due to `.gitignore`.
3. Code is pushed to remote and the actual commit is confirmed. Secrets are excluded.
4. Every needed result has an off-VM verified copy. It is known which temporary results the user allowed to discard.
5. STATUS contains the continuation point, constraints, registry references, and active processes. Updated documents are pushed.
6. The user has a secure way to restore credentials; do not archive `.env` blindly with public material.
7. Only then report readiness for deletion, naming the confirmed commit and external copies.

The user deletes the VM, or the agent does so only with a separate direct instruction. Based on the reported provider conditions, Stop does not end billing. If verification is impossible, state “not ready for deletion” and name the missing proof.

## 8. Final Publication

Before publication, check the required Google Drive + public Git deliverables, rights for external assets and the original PDF, secrets in files/history, complete instructions, and manifests. Do not publish logs containing private addresses or credentials. The operational runbook may need sanitizing before the repository becomes public.

A prepared archive or commit is not a published submission. Add actual verified links to the report and STATUS only after an authorized upload.
