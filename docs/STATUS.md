# Current State

Updated: **2026-10-02**, Europe/Moscow. Local Mac work; no GPU VM connected.

## Current outcome

**DONE — audit of the uncommitted research restructuring.** [Audit and priorities](reviews/restructuring-2026-10-02.md); [machine evidence](../artifacts/restructuring-audit-2026-10-02.json).

Memory/history separation and portable Git inputs are effective. Shared implementation extraction is partial. Open findings concern copy-verification state, repeated import, matrix reuse, an ambiguous wait timeout and incomplete primary VM handoff instructions. Runtime code was not changed by this audit.

All 92 existing offline tests passed; documentation/archive/input checks passed. Four temporary synthetic probes reproduced the reported behaviors. Existing tests do not cover these workflows or establish live CARLA compatibility.

## Exact continuation

The [reusable runtime proposal](proposals/reusable-research-runtime.md) describes one internal library package, common capture/session contracts and staged migration for camera/scene variants. It is a proposed direction; implementation has not started.

Review the audit, then correct registry lifecycle, per-cell reuse and wait semantics with regression scenarios. Complete the VM → Mac → new VM instructions, including committing/pushing updated registry evidence. Preserve reviewed changes in private Git as coherent commits.

Then restore a GPU VM from Git inputs, run one short route_01_straight/clear_day baseline pilot, validate recording and verify its Mac export before a matrix. Use [VM workflow](vm-workflow.md) with the audit's handoff correction until the guide is updated. Choose a camera/scene variant after the pilot.

## Preserved constraints

- October 1 migration rationale and original checks: [architecture](architecture.md), [validation record](../artifacts/restructuring-2026-10-01.json). Historical evidence: [archive](archive/assignment-2026/index.md).
- Restructuring changes remain uncommitted. The pre-existing user `.gitignore` edit is preserved. No push, publication or VM deletion occurred.
- No new rig, authored map or live experiment was validated. Historical backup claims remain unchanged; local data alone do not establish external preservation.
- No unfinished audit process remains. On future interruption record process identity, state/log path and exact continuation here.
