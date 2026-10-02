# Experiments and Continuation

## One implementation, explicit inputs

Define goal, changed variables, controls and acceptance before running. Reuse shared code; configurations contain parameters, not copies of implementation. Keep inheritance shallow: baseline plus declared overrides, resolved to a complete run configuration. Current stage configs remain complete JSON files; a general override resolver is future work.

Use versioned Git inputs for approved routes/calibration/small replay scenes. Give large inputs an external location and integrity check. Input identity must use relevant file contents, not only a path. Same map name does not prove unchanged authored geometry.

Separate experiment_id (study), configuration/input fingerprint (settings identity), run_id (execution) and repeat_index (requested measurement repeat). A matching successful repeat may satisfy a resume; it cannot satisfy a newly requested repeat. Failed/interrupted runs stay separate. Record revision/dirty state and actual environment with each run.

Identity schema 2 also records `measurement_fingerprint`: selected route geometry and weather plus shared settings, calibration, implementation and runtime. The full `config_fingerprint` still records all matrix inputs and detects in-flight drift. Adding another route/weather preserves unchanged measurements; editing selected inputs invalidates them. Source hashes and runtime options remain conservative equivalence boundaries. Schema-1 ledger rows retain exact full-fingerprint matching only; historical evidence is not upgraded by guessing missing hashes.

## Bounded process control

A tool/orchestration handle completing does not prove its child experiment ended. Check stored PID/process identity, progress and exit status. Use one managed invocation and bounded status output; avoid wide pgrep command lines or continuously recounted output directories. Never start a replacement merely because an outer tool returned.

Routine output should identify run, state, latest progress/time and output path. Detailed logs are files. Read a bounded tail on a new error; repeat it only when output/state changes. Supported Stage-3/4 capture and Stage-6/7 scene entry points share one exclusive recorder lock in the working copy; a competing command fails before capture/mutation. Batch coordination has its own lock so its workers can acquire the recorder lock normally. Process liveness does not equal successful validation; externally verified backup is another separate condition.

After interruption, recover STATUS plus configuration/process record, inspect actual files, then resume/retry explicitly. Do not reload the entire archive. Save failed attempts and exact reasons.

## Results and portable resume

The append-only registry at artifacts/run_registry.jsonl is separate from full datasets. Exact experiment/configuration/input/runtime identity plus route/weather and 1-based repeat govern resume. New-format completed runs can be imported only after their manifest, identity and baseline validation pass. Legacy runs without identity are refused rather than assigned a current fingerprint; preserve them in [artifacts/index.csv](../artifacts/index.csv).

A completed record needs an available valid local manifest or matching recorded verified external-copy evidence. Missing evidence blocks launch rather than silently skipping or rerunning. Running/unknown state also blocks automatic relaunch; terminal failed attempts can be retried. External verification records location, manifest hash, time and distinct origin/verification host identifiers, not an eternal availability guarantee. Before deletion/analysis/input reuse check actual files through [VM workflow](vm-workflow.md). Camera/timing/route or relevant recorder-source changes must not match old results. The batch recomputes identity before and after each recorder; input/source drift marks that attempt failed rather than accepting stale identity.

Deterministic route/calibration preparation may be reused when relevant inputs/versions match. Scene replay uses the stored accepted description/provenance. New API calls and new drives are required for requested latency/variability repeats. Seed equality is not deterministic-output proof.

## Local command entry

From the repository root:

```sh
python3 -m carla_tasks check-docs
python3 -m carla_tasks check-inputs
python3 -m carla_tasks plan --config configs/stage4_baseline_matrix.json
python3 -m carla_tasks scene-check fixtures/stage6/valid_parked_vehicle.json
python3 -m carla_tasks registry list --experiment-id baseline-av2-short-v1
```

check-docs checks startup budget, active local links and archive hashes without scanning runs/chats. scene-check supports static SceneSpec v1.0; animal v1.1 is a separate policy. Planning resolves identity and cells without launching simulations. Registry lists default to 20 latest rows.

For an identified completed run and a copied destination, replace the placeholders:

```sh
python3 -m carla_tasks registry import --run-dir runs/RUN_ID
python3 -m carla_tasks registry verify-copy --run-id RUN_ID --manifest-dir /SOURCE/MANIFEST_DIR --copy /MAC/RESULTS/RUN_ID --report artifacts/export_verifications/UNIQUE.json
python3 -m carla_tasks verify-export /SOURCE/MANIFEST_DIR /MAC/RESULTS/RUN_ID
```

verify-copy accepts a manifest-only source, verifies it matches registered run identity and checks actual destination bytes. It records destination-integrity evidence and updates the small registry only with matching source-host identity and a distinct verification host. A same-origin-VM copy cannot satisfy external-backup evidence. Check actual machine/storage context and present accessibility before deletion. Plain verify-export checks bytes but does not update registry backup status. Do not call a source on the VM an external destination.

Manage a real command with durable process state; after substituting the command/run path:

```sh
python3 -m carla_tasks process start --state logs/process-RUN_ID.json --log logs/process-RUN_ID.log -- .venv/bin/python scripts/stage4_baseline.py --run-dir runs/RUN_ID --route-id route_01_straight --weather-id clear_day
python3 -m carla_tasks process status --state logs/process-RUN_ID.json
python3 -m carla_tasks process wait --state logs/process-RUN_ID.json --timeout 30
```

Do not run that capture example on Mac; it needs a prepared run directory and live server. Durable process completion and dataset acceptance remain separate. Inspect the previous state before creating a retry path.

`process wait` returns exit 0 for completed, 1 for failed, 2 for command/input errors, 3 for timeout while still pending, and 4 for unknown supervision. Its JSON includes `wait_outcome`. Timeout neither kills nor relaunches the child. `process status` remains a read-only query. Wait briefly, use progress, and never interpret timeout as a successful experiment.


Run `python3 -m carla_tasks --help` from the repository root for the supported entry points. Input checks, matrix planning, registry metadata and export verification work without starting CARLA. Server probing and actual captures require the VM. Existing stage-named scripts remain compatible commands; shared functionality belongs in the package.

Before a costly batch validate one short run, free space and export destination. `scripts/stage4_batch.py --dry-run` reports pending cells without starting CARLA. Default execution creates its own pinned server and cleans it by lease; explicit --attach-server uses a healthy matching server and leaves it running. Never start or stop an attached server implicitly. Record API limits/retries before calls. Keep API latency, application time, capture wall time and simulation time separate. Machine summaries are evidence; worklog entries link them rather than reproduce every number.
