# Restructuring Audit — 2026-10-02

**Scope:** review the uncommitted October 1 migration against smaller agent context, reliable continuation, portable VM inputs and less experiment coupling. Runtime code was not changed. [Machine evidence](../../artifacts/restructuring-audit-2026-10-02.json) records the checks and temporary synthetic reproductions. No live CARLA, Docker, model API, remote storage or historical dataset was used.

## Assessment

Memory/history separation and promotion of reusable inputs directly solve the original problem. English translation alone could not resolve conflicting current/historical facts or mandatory report reading. The execution architecture is less mature: supervision and registry mechanisms grew faster than the central capture/scene executors were simplified. Preserve the selected boundaries and close specific lifecycle gaps before adding more infrastructure.

At audit entry, mandatory Markdown was 9,327 bytes versus the original 107,035: a 91.3% reduction. This measures startup text, not total conversation tokens, compactions or billing. The 15 KiB guard, ten archive snapshots, four input configurations, approved routes and AV2 calibration passed checks. All 92 existing tests passed in 7.551 seconds. The additional scenarios below still reproduced defects: passing tests establish only the covered behavior.

## Findings

### F1 — High: a known-bad copy remains verified

**Artifact-confirmed, synthetic reproduction.** `registry verify-copy` appends a registry event only on success (`carla_tasks/__main__.py:143–157`). If the same destination was previously verified and now fails its checksum, the failed report is separate and the registry still says `verified`. Resume continues to accept that proof (`carla_tasks/registry.py:123–125`).

Using `CliTests.make_copy`: verify the copy, replace its data with different bytes of identical size, and verify again to a new report. Actual results: second check `failed`, current copy state `verified`, cell state `complete`.

Record verification failures and invalidate proof for the matching destination. This is known contradictory evidence, beyond the documented risk of later inaccessible storage. Failure at a different new destination should not erase valid proof for an existing copy. Cover both transitions.

### F2 — Medium: reimport loses valid backup evidence

**Artifact-confirmed, synthetic reproduction.** `RunRegistry.import_run` always appends `external_copy: {status: unknown}` (`carla_tasks/registry.py:189–197`). Importing an identical run after verified export replaces that proof in `latest()`.

The probe created a manifest-covered new-format run, imported it, copied and verified it with a mocked distinct verification host, then imported the unchanged run again. Copy status became `unknown`; after the original local path was removed, resume became `unavailable` despite the valid copy.

Make import idempotent for matching run identity, manifest and execution host. Preserve matching export evidence and reject conflicting identities. Test import → verify → import → fresh-VM continuation.

### F3 — Medium: matrix expansion invalidates unchanged measurements

**Artifact-confirmed, synthetic reproduction.** One fingerprint covers all selected weather profiles and route geometries (`carla_tasks/experiments.py:242–254`). Adding rainy weather changed an unchanged completed clear-weather cell from `complete` to `pending`. Route expansion has the same structural issue. Increasing repeat count is already handled correctly.

Separate the complete study manifest from each effective measurement identity: selected route, selected weather, rig, timing, seed and relevant implementation/runtime semantics. A new requested repeat remains a new measurement; adding a matrix cell should preserve matching prior cells.

The probe also confirmed that a server-port change or source comment changes identity. Those are conservative choices rather than unconditionally incorrect behavior. Preserve full provenance and define equivalence deliberately; simply dropping code/runtime hashes would weaken reproduction, especially for throughput/latency studies.

### F4 — Medium: wait timeout has an ambiguous completion contract

**Artifact-confirmed interface behavior.** `process wait` returns shell exit code zero on timeout while its JSON correctly reports `running` and child `exit_code: null` (`carla_tasks/__main__.py:113–124`). A caller reading JSON can handle this; a caller interpreting successful wait-command completion as child completion can repeat the original orchestration mistake.

A temporary running-state file and 0.01-second timeout reproduced this without launching an experiment. Specify distinct completed, failed, pending and unknown outcomes, with an explicit timeout result. The CLI contract and guide should agree. A process record is a useful control, not an absolute guarantee against creating another attempt path.

### F5 — Medium: the primary transfer example omits the new registry handoff

**Documented workflow gap.** The [VM guide](../vm-workflow.md) demonstrates rsync plus the standalone hash verifier and recording evidence in `artifacts/index.csv`. That command does not update the new JSONL registry. Portable resume later depends on that registry's verified-copy evidence when the local run is absent. Additional commands exist in [experiments](../experiments.md), but the reader must assemble the complete sequence.

Provide one ordered path: VM finalization and registry preservation → Mac receives registry and run → Mac verifies destination and updates proof → updated registry/report are committed and pushed → new VM fetches and previews resume without images. Define the operational registry's authority and the historical CSV/artifact catalog's separate role; avoid manually duplicating current backup states.

## Architectural judgment

The strongest changes are short mandatory memory, on-demand history, versioned Git inputs, and separating baseline choices from durable synchronization/evidence rules. Checksummed archival preserves failures and research history. Pure geometry/image/validation logic is now usable without CARLA. Progress files, durable exit records, RPC readiness and exact-container ownership address real failure modes.

The package has 17 files and 2,316 lines, including moved implementation; ten new test files contain 952 lines. These numbers alone do not establish overengineering. The imbalance is that capture/scene scripts still import each other while control now spans process state, progress, metadata, batch summaries and a registry. Each view needs explicit authority and recovery semantics. Stage 4 still obtains sensor helpers from Stage 3; Stage 6/7 still depend on both. The scan found 38 stage-module import edges, including compatibility wrappers, so that count is not a count of defects. A general rig and reusable recorder remain correctly documented as deferred work.

Bounded output is partly a usage convention: `CommandRunner` forwards all child output (`scripts/stage4_batch.py:50–62`). The managed wrapper captures it, but direct batch invocation remains noisy. One concise default path with explicit verbose diagnostics would better support the context goal. No real-session post-migration token or repeated-launch benchmark has been measured.

AGENTS, PROJECT, STATUS and README retain some overlapping navigation/rules. Their current size is acceptable; treat 15 KiB as a ceiling, not a target to fill. Keep STATUS about the next action and unresolved work; keep this audit outside mandatory startup.

## How the work was conducted

Documentation cleanup, input promotion, mechanical extraction, timing fixes, server lifecycle, supervision and result identity were combined in one uncommitted change. That increased the review surface. The prior [validation record](../../artifacts/restructuring-2026-10-01.json) also records a temporary missing document target during concurrent assembly. Complete referenced artifacts before final integration checks. Retesting after substantive changes was justified; expanding scope and coordination added iterations.

The next improvement should close the identified gaps and follow one actual camera/scene task, extracting the recorder components it needs. A larger generic experiment framework is not currently justified. Preserve reviewed changes in coherent commits: memory/history, portable inputs, mechanical extraction, then execution/registry behavior with regression scenarios. This makes review and rollback more precise.

## Follow-up acceptance

1. Failed re-verification cannot leave that destination currently verified; identical reimport preserves valid proof.
2. Matrix expansion retains matching prior cells; changed capture conditions and requested repeats require the appropriate new measurements.
3. Timeout is explicitly pending, with a documented interruption/recovery path.
4. A Git-only checkout can preview resume after the complete Mac export/registry handoff.
5. Then perform one short GPU baseline pilot and verify its Mac export before a matrix.

These are recommendations and uncovered cases, not implemented fixes. Historical reports, previous validation artifacts and runtime code were preserved. Live capture compatibility remains unverified.
