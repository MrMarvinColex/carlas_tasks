# Current State

Updated: **2026-10-12**, Europe/Moscow. Local Mac work; no GPU VM connected.

## Current outcome

**DONE — add the user-provided [Google Drive dataset link](https://drive.google.com/drive/folders/1VVr3LYjmNyNil5vb7l7p8LWWO4ljKxx5?usp=sharing) to the Russian and English reports.** The English delivery table now records the supplied link rather than "Not published" for the dataset. The web reader could not open the folder; contents, completeness and access remain unverified. No cloud files or sharing settings were modified.

The English submission table also now links the user-confirmed public [Git repository](https://github.com/MrMarvinColex/carlas_tasks); the Russian report already had this URL. The user requested no public-access checking; no further checks were performed after that clarification. No repository visibility change or push occurred.

**DONE — prepare the first assignment results for browser upload without duplicating file data.** `/Users/madness/Science/CARLA/google_disk` contains ordinary directories with hard-linked files: 10 baseline drives, six vehicle scenes and their API protocol, three deer replays and their API protocol, plus `report`. All 10,190 selected file links share their source device/inode and size (13,651,933,396 logical bytes); `.DS_Store` was excluded. [Selection and verification](../artifacts/google-disk-staging-2026-10-11.json). Editing a linked file edits the original; deleting the staging tree leaves originals intact. No upload or independent backup was performed. The complete five-route edited-scene series remains unperformed.

**Previous completed outcome:** preserve earlier changes as commits, correct audit findings and implement the reusable library foundation. [Handoff and bounded tasks](library-handoff.md); [check evidence](../artifacts/library-foundation-2026-10-02.json).

Original work: `2110973` portable inputs, `552481c` pure extraction, `046279c` execution supervision, `bf3695f` memory/history and audit. Follow-up: `f7205bd` fixes F1–F5; `ecef1a8` adds rig/sample/session contracts, bounded same-frame capture, one tick owner, ordered writing, cleanup, lossless capture validation and an installable package. Complete commit bodies explain rationale/limits.

All **123 offline tests passed from an isolated staged checkout**. Pipelines with 1/3/9 paired cameras, failure/cancellation/cleanup and writer ordering are covered. Nine AV2 camera calculations match their previous evidence exactly with synthetic vehicle geometry. Three-camera synthetic capture, wheel import and documentation/input checks are recorded in the evidence. None establishes live CARLA compatibility.

**Imported VM evidence (2026-10-05):** remote commit `158ae20` records dependency preparation, all 123 offline tests, a nine-pair three-sample readiness capture and one completed straight/clear-day drive (31 samples; 837 validated PNGs, no collision), using the existing live executors. [Session evidence](../artifacts/20261004T221357Z-vm-validation-e9e494.json), [acceptance configuration](../configs/vm_validation_20261005.json) and run-registry events are preserved. The documented VM session left no unfinished process or owned server; its runs had no verified external copies. This imported evidence is not a new execution on this Mac. The generic `record` backend remains synthetic-only.

## Exact continuation

User next action: include the updated reports in the delivered materials and verify the supplied Google Drive folder's uploaded contents/access. Local report changes do not update an already uploaded cloud copy. Staging alone is not delivery verification.

Library continuation, only when requested: implement **M1** in [library handoff](library-handoff.md): a CARLA backend for the existing `record` kernel, with bounded warmup/phase discovery, owned-resource cleanup and actual applied-rig/environment evidence. First exercise fake CARLA failures, then run one short GPU pilot. Read the interfaces and M1 references only; do not reread assignment history or implement all migration tasks together.

M2 then migrates route control/acceptance and new-format experiment finalization; M3 separates scene replay from generation. Existing stage loops and baseline-specific registry import remain operational during migration. New generic capture is opt-in and currently has only a synthetic backend.

## Preserved constraints

- No new GPU/CARLA/API execution, cloud upload, repository visibility change or VM deletion in this Mac task. The user authorized commit/push to `origin/Dev` on 12 October. First commit: `206f3cf`; initial push was rejected because `158ae20` was remote-only. Merge preserves both artifact/worklog histories and the remote run registry; normal push follows merge verification.
- Original routes/calibration, archive hashes, reports, chats and historical run/backup claims are preserved. New-format captured data is not a completed experiment or verified backup.
- A new VM restores Git inputs and the verified-copy registry, not the full runs tree. Follow [VM workflow](vm-workflow.md), including pushing Mac verification evidence back through Git when authorized.
- No unfinished task process remains. Record process state/log/identity here if future work is interrupted.
