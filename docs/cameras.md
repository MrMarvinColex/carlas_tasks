# Cameras, Routes and Recording

## Reproducible baseline

Five approved shortened routes are versioned in [inputs/routes/town01_opt_short_v1](../inputs/README.md), with source/hash provenance. Historical driving evidence: `20260923T160409Z-shorter-routes-autopilot-b8548d`. Input promotion does not rerun CARLA adjacency/spawn/driving checks; a changed map needs fresh checks.

The camera source is AV2 Sensor log `54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca`, preserved in [calibration](../configs/av2/54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca/calibration.json) with raw source/hash metadata. Nine RGB/semantic pairs use seven ring and two stereo positions. Baseline timing is 0.05 s world step and 0.5 s sensor period; capture frequency uses simulation time.

AV2 ego axes are x-forward/y-left/z-up; CARLA vehicle axes are x-forward/y-right/z-up. Optical axes require a separate conversion. Align AV2's rear-axle origin to the Tesla rear axle after a synchronous tick. Apply the declared +0.5 m local-z mount adaptation: exact-height placement exposed the hood in retained failed pilots. This is not exact AV2 translation equivalence. CARLA uses source dimensions and horizontal FOV derived from fx; arbitrary principal point/distortion equality is not claimed.

## Checks before and after capture

Offline: validate source units, transform direction, quaternion order, rotations/handedness, derived FOV and actual requested sensor count. On VM: inspect all views, verify coordinate conventions/pose pairing, dimensions, semantic IDs, timestamp interval, sensor drops/duplicates and ego-body occlusion. Remove DebugHelper output before recording; draw_point previously produced black road occluders.

Callbacks are grouped by frame and matched with the same snapshot pose. Drain final queues and finish one complete transforms.json. Raw semantic PNGs are lossless class IDs; palettes are previews. Keep writer queues bounded with explicit backpressure rather than silent drops. Record writer timing separately from simulation time.

## New rigs and formats

Declare the changed layout, resolution, sampling and storage format as an experiment; preserve the baseline. Share recorder/validation mechanics rather than copying stage scripts. The library now has a versioned perspective RGB/semantic rig contract and a shared recorder/validator that derive streams from it. Their offline synthetic path supports variable camera count; live CARLA integration remains M1 in [library handoff](library-handoff.md). Existing live executors still use the AV2 preset.

Start with a short recording on one route/weather and validate before a matrix. Switching semantic IDs to lossy storage is incompatible with data invariants. Format changes need decode and frame/pose completeness checks, not only file counts.

Detailed historical evidence and sources: archived [knowledge sections 4–6](archive/assignment-2026/docs/knowledge.md), [working report](../report/report.md) and [artifact registry](../artifacts/index.csv). Do not reread the full history for routine camera changes.
