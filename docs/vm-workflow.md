# Mac and Disposable GPU VM Workflow

## Restore code and only required inputs

1. Confirm the intended VM/account, actual home, repository location and remote/branch. Preserve an existing worktree. Historical account was Ubuntu and path /home/Ubuntu/carlas_tasks; inspect rather than assume.
2. Fetch the selected code commit. Git supplies configuration, AV2 calibration, approved routes under inputs/ and small result metadata. Do not restore the full 30+ GB runs tree for new simulation.
3. Run `bash scripts/preflight.sh` to inspect OS/GPU/Docker/disk, then `bash scripts/setup.sh` to create the VM .venv and pinned CARLA client. This Linux/GPU setup is not the offline Mac setup. Restore credentials from the user's secure source, never chat or Git.
4. Restore only required external maps/assets or saved data, verify their hashes, and record actual client/server/image versions. Baseline image digest is in [animal probe config](../configs/stage7_animasim_probe.json); derived animal images need separate preparation.
5. Inspect owned containers/ports/process state before `bash scripts/run_carla.sh`. Default launch is pinned by Docker digest; baseline batches require that recorded image identity. A listener alone is not proof that CARLA RPC responds: launch probes RPC. Each batch stores a unique server lease containing the exact created container ID. Failure/interruption cleanup and `scripts/stop_carla.sh --lease FILE` target that ID, protecting an unrelated/replacement container. Confirm a short RGB capture and requested map before bulk recording; stop the owned server when finished. Batch --attach-server is an explicit alternative: it checks a healthy matching server and never stops that pre-existing server.

Recheck full environment only on recovery or meaningful changes. Use normal repository/Python permissions; inspect Docker access before sudo. Shell changes in this restructuring are offline-checked only until a VM pilot validates them.

## Git and rsync have different jobs

Git: code, settings, small input versions and registry/docs. Review changes, commit and push the selected work; verify the expected remote commit before deleting a VM. No automatic commit/push is implied by a simulation command.

rsync: completed or honestly finalized incomplete runs, large logs and selected raw chat evidence. Run transfers from the Mac. Example placeholders must be replaced with actual paths:

```sh
rsync -avP carla-vm:/ABSOLUTE/VM/PROJECT/runs/RUN_ID/ /ABSOLUTE/MAC/RESULTS/RUN_ID/
python3 scripts/verify_export.py /ABSOLUTE/MAC/RESULTS/RUN_ID /ABSOLUTE/MAC/RESULTS/RUN_ID
```

Do not add --delete. Source/destination trailing slashes mean run contents. Finish capture/queues and create manifest before transfer. The legacy verifier expects the project's digest/size/path manifest. With the copied source manifest, the self-path command validates destination bytes against manifest entries; it does not constitute a second copy. Preserve verification output/time and manifest digest; record actual external location and backup evidence in artifacts/index.csv.

A completed transfer or source-to-source check does not prove an external backup. New registry verification additionally requires manifest-covered execution-host identity and a distinct verification host; same-VM rehashes cannot mark an external copy verified. Mac storage is external to a VM; a second folder on that VM is not. Upload/public visibility requires separate authorization.

## Portable continuation

Transfer the small Git registry to a new VM to continue a series without images. Exact configuration/input identity and repeat matching govern skip decisions; new-format runs need verified identity/manifests; legacy runs without identity remain in the historical registry and cannot be imported as current runs. Read [experiments](experiments.md) for trust limits. Restore historical images only for analysis that needs them.

## End or delete a VM

Finish/finalize processes, preserve failures, verify code is remote, export every retained result and validate its actual external copy. Record exact continuation and any active PID/command/output in STATUS; preserve credential recovery outside the VM. Inspect ignored/untracked files so useful inputs are not missed.

Report readiness only with commit and external evidence. User-reported provider billing ends with irreversible Delete, not Stop. Delete/resource/pricing changes require explicit user instruction; this workflow does not perform them. Historical backup uncertainty remains in the registry rather than being promoted to verified.
