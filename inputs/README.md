# Portable experiment inputs

Git tracks the small files required to start an experiment on a fresh VM.
`runs/` stores generated results and is not a runtime prerequisite for the
maintained configurations. Restore result directories selectively for analysis.

## Selected route set

`routes/town01_opt_short_v1/` contains the exact route index and five route JSON
files promoted from `20260923T160431Z-shorter-routes-b72a9d` (375,114 bytes).
`provenance.json` records historical manifest/acceptance hashes, route selection,
CARLA/image versions, and individual file signatures. Each promoted file was
checked against its historical manifest; the historical directory was unchanged.

The index and geometry intentionally retain historical absolute paths and
pending-drive labels. These are provenance, not runtime dependencies; the source
acceptance supersedes the generated pending-drive labels. Offline validation
does not read historical route validation runs or inspect dataset images.

To change geometry, create and validate a new named route set, record its
provenance, and explicitly select it in experiment configurations. Do not edit
this pinned baseline in place. Saved model scene descriptions may later be
promoted here with their originating attempt and hashes; full API logs stay in
the corresponding run archive. The tracked AV2 calibration and two raw Feather
source files already live in `configs/av2/` and are not duplicated here.

Offline validation verifies file integrity and saved geometry structure. It
does not establish connectivity against a live map, camera occlusion, or animal
asset availability; those still require a short GPU/CARLA run.
