# Current Decisions

Historical D01–D26 and corrections remain in [assignment decisions](archive/assignment-2026/docs/decisions.md). Read relevant entries only. These decisions replace the old memory workflow and assignment-only boundaries, not measurements.

## R01 — Research memory and code/data boundaries

**2026-10-01; user-authorized; local implementation and offline checks complete. Live GPU compatibility remains pending.** Mandatory AGENTS + STATUS + PROJECT, on-demand guides and preserved history replace large startup reading and overlapping narratives. Replace stale state; keep brief worklog entries and reports only when relevant. Startup budget: 15 KiB.

Code/configuration/small reusable inputs belong in Git; full outputs use rsync/manifests. Promote approved route JSON with provenance so VMs need no old images. Shared code belongs in `carla_tasks/`, with compatible script wrappers during migration.

Full problem, alternatives, reuse rules, validation and consequences: [architecture](architecture.md).

## R02 — Reproducible baseline and declared research variants

**2026-10-01; accepted by user.** Preserve the recorded CARLA/Town01_Opt/routes/AV2 baseline. New camera formats/layouts, maps and authored scenes are separate experiments. Unreal/editor work is a separately planned direction, not implemented here. API-hosted models and restricted passive SceneSpec remain defaults.

Use shared preparation and shallow overrides; save resolved configuration per run. Separate configuration identity from run/repeat identity. Reuse deterministic preparation when relevant inputs/versions match; never satisfy a requested measurement repeat with cached output.

## R03 — Implement difficult library contracts before migrating consumers

**2026-10-02; user-authorized; offline foundation implemented, live migration pending.** Preserve prior work in coherent commits first. Correct audited registry/identity/wait/handoff behavior separately. Keep one installable `carla_tasks` package; define concrete rig, detached sample, backend, sink and ownership contracts around a tested common recording loop. One simulation owner and bounded queues make frame alignment, cleanup, writer ordering and failure evidence explicit. Route completion differs from a sample cap; capture integrity differs from experiment acceptance.

The kernel is exercised through a synthetic backend and the real PNG/pose writer on Mac. Legacy live loops retain behavior while their pure AV2 adaptation delegates to the package. The new capture format is versioned and opt-in; it does not fabricate legacy baseline validation or registry identity. Migrate one actual backend/route consumer before scene/provider extraction, with a GPU pilot before switching defaults. Detailed interfaces, rejected complexity, task order and acceptance are in [library handoff](library-handoff.md). No separate library repositories or speculative plugin framework.
