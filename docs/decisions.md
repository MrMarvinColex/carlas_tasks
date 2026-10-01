# Current Decisions

Historical D01–D26 and corrections remain in [assignment decisions](archive/assignment-2026/docs/decisions.md). Read relevant entries only. These decisions replace the old memory workflow and assignment-only boundaries, not measurements.

## R01 — Research memory and code/data boundaries

**2026-10-01; user-authorized; local implementation and offline checks complete. Live GPU compatibility remains pending.** Mandatory AGENTS + STATUS + PROJECT, on-demand guides and preserved history replace large startup reading and overlapping narratives. Replace stale state; keep brief worklog entries and reports only when relevant. Startup budget: 15 KiB.

Code/configuration/small reusable inputs belong in Git; full outputs use rsync/manifests. Promote approved route JSON with provenance so VMs need no old images. Shared code belongs in `carla_tasks/`, with compatible script wrappers during migration.

Full problem, alternatives, reuse rules, validation and consequences: [architecture](architecture.md).

## R02 — Reproducible baseline and declared research variants

**2026-10-01; accepted by user.** Preserve the recorded CARLA/Town01_Opt/routes/AV2 baseline. New camera formats/layouts, maps and authored scenes are separate experiments. Unreal/editor work is a separately planned direction, not implemented here. API-hosted models and restricted passive SceneSpec remain defaults.

Use shared preparation and shallow overrides; save resolved configuration per run. Separate configuration identity from run/repeat identity. Reuse deterministic preparation when relevant inputs/versions match; never satisfy a requested measurement repeat with cached output.
