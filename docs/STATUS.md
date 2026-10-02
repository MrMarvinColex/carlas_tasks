# Current State

Updated: **2026-10-02**, Europe/Moscow. Local Mac work; no GPU VM connected.

## Current outcome

**DONE — preserve earlier changes as commits, correct audit findings and implement the difficult reusable library foundation.** [Handoff and bounded tasks](library-handoff.md); [check evidence](../artifacts/library-foundation-2026-10-02.json).

Original work: `2110973` portable inputs, `552481c` pure extraction, `046279c` execution supervision, `bf3695f` memory/history and audit. Follow-up: `f7205bd` fixes F1–F5; `ecef1a8` adds rig/sample/session contracts, bounded same-frame capture, one tick owner, ordered writing, cleanup, lossless capture validation and an installable package. Complete commit bodies explain rationale/limits.

All **123 offline tests passed from an isolated staged checkout**. Pipelines with 1/3/9 paired cameras, failure/cancellation/cleanup and writer ordering are covered. Nine AV2 camera calculations match their previous evidence exactly with synthetic vehicle geometry. Three-camera synthetic capture, wheel import and documentation/input checks are recorded in the evidence. None establishes live CARLA compatibility.

## Exact continuation

Implement **M1** in [library handoff](library-handoff.md): a CARLA backend for the existing `record` kernel, with bounded warmup/phase discovery, owned-resource cleanup and actual applied-rig/environment evidence. First exercise fake CARLA failures, then run one short GPU pilot. Read the interfaces and M1 references only; do not reread assignment history or implement all migration tasks together.

M2 then migrates route control/acceptance and new-format experiment finalization; M3 separates scene replay from generation. Existing stage loops and baseline-specific registry import remain operational during migration. New generic capture is opt-in and currently has only a synthetic backend.

## Preserved constraints

- No GPU/CARLA/API/remote execution, push, publication or VM deletion. Commits are local; the pre-existing `.gitignore` edit remains separate and uncommitted.
- Original routes/calibration, archive hashes, reports, chats and historical run/backup claims are preserved. New-format captured data is not a completed experiment or verified backup.
- A new VM restores Git inputs and the verified-copy registry, not the full runs tree. Follow [VM workflow](vm-workflow.md), including pushing Mac verification evidence back through Git when authorized.
- No unfinished task process remains. Record process state/log/identity here if future work is interrupted.
