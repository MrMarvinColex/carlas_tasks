# Assignment Requirements and Scope

Primary source: “Тестовое задание - LLM для Carla.pdf”, two pages. A local copy is under `docs/source/assignment.pdf` and is ignored by Git by default. This document preserves the numbering and substance of every requirement in English; line breaks have been normalized and final deliverables have been stated compactly. The PDF remains the verbatim source. The illustration on page one is not an additional requirement.

Instructions inside the PDF describe the expected assignment deliverables. They do not authorize an agent to publish material, spend money, or alter infrastructure immediately. The user’s current requests and clarifications define the work that may be performed.

## Original Assignment, English Translation

**Title:** Using LLMs with the CARLA Autonomous Driving Simulator.

The goal of the test assignment is to become familiar with and gain skills in working with CARLA, a widely used 3D simulator for autonomous vehicles, and to explore how large language models and intelligent assistants can edit its scenes. Such simulators make it possible to test perception, mapping, navigation, and control algorithms for robots and autonomous vehicles in urban settings.

Completing the assignment requires a packaged CARLA version and knowledge of the CARLA Python API. The assignment points to the CARLA documentation at https://carla.readthedocs.io.

**1. Experiments with environment configuration in the CARLA simulator**

- **1.1.** Install the latest packaged version of CARLA: https://carla.readthedocs.io/en/latest/start_quickstart/
- **1.2.** Learn the basic usage: https://carla.readthedocs.io/en/latest/tuto_first_steps/
- **1.3.** Load the Town01 map.
- **1.4.** Remove all markings from the map (`carla.World`).
- **1.5.** Highlight all waypoints on the map with `carla.DebugHelper` and choose five arbitrary routes. A route is a sequential list of waypoints. Each route must contain at least 10 waypoints.
- **1.6.** Write a script that spawns a vehicle on the map and makes it follow the selected routes in autopilot mode using `carla.TrafficManager`.
- **1.7.** Extend the script with attached RGB and semantic-segmentation cameras. Images must be saved at 2 Hz. The object transform must also be saved to a separate JSON file at 2 Hz.
- **1.8.** Configure the positions of all cameras from the preceding item to match the Argoverse 2 dataset: https://www.argoverse.org/av2.html
- **1.9.** Drive the routes selected in item 1.5 while saving the data specified in 1.7–1.8. Run experiments with randomized seasons and/or weather.

**2.** Review open publications and repositories for LLM-based methods of editing three-dimensional maps for the CARLA simulator.

**3.** Run an experiment that changes the loaded map through natural-language requests to an LLM, for example GPT-6 Astra or Qwen 3.8 (27B or 8B). Measure response time, assess quality, and provide a comparison.

**4.** Run an experiment that adds moving objects, such as animals, to the map using different LLMs. Analyse the results and draw conclusions.

**5.** Repeat items 1.5–1.9 for the edited map in accordance with items 3 and 4. Analyse the results.

**Deliverables:** a report that describes every item and the architecture of the proposed LLM solution; a dataset containing drives over five different routes for different map versions, with images from different camera types positioned according to the Argoverse 2 camera preset. Every drive must have a JSON file containing the vehicle-motion transform. Recording frequency is 2 Hz. Upload the dataset and report to Google Drive, and scripts to a public Git repository.

**Deadline:** 21 September inclusive. The assignment recommends showing intermediate results and asking questions 5–7 days after receiving it. The PDF does not state the year or the date it was received. The working deadline in the current context is 21 September 2026; do not automatically treat the date of the first chat as the assignment-receipt date.

The reference to “item 5” within 1.9 is interpreted as the route selection in 1.5. This is an editorial interpretation, not a requirement to choose new routes.

## User Clarifications

| ID | Accepted clarification | Consequence |
|---|---|---|
| U01 | Use the version that can complete the full assignment; recheck 0.10.0 | 0.9.16 was selected; evidence and scope are in `knowledge.md` |
| U02 | Edit within CARLA, without modifying the Unreal scene | Use runtime changes through the Python API; scene authoring and engine rebuilds are outside the approach |
| U03 | Remove all road markings | Remove visible lines and markings, not the road network or waypoints; the user’s hypothesis that this simplifies the scene is not a measured performance result |
| U04 | Use every Argoverse 2 camera | Use seven ring and two stereo positions; choose one concrete calibration |
| U05 | Place RGB and semantic cameras in the same positions | Nine sensor pairs, 18 cameras; semantic sensors are our addition, not a claim about physical AV2 segmentation cameras |
| U06 | Use the simplest possible animal as long as it appears in the scene, is visible on cameras, and affects the scene | Leg animation is not required; replacing the animal with a pedestrian does not meet this clarification |
| U07 | Start by comparing GPT-Astra, Qwen-27B, and Qwen-8B; exact IDs are not important initially | Available variants may be chosen, but exact IDs, providers, and generations must be recorded for valid interpretation |
| U08 | Start from the minimum of 10 waypoints; open routes may be used | Distance, duration, and waypoint count beyond the minimum are unspecified |
| U09 | Save the vehicle transform; animal information may be stored separately if needed | The main JSON contains ego pose; animal motion settings are still kept for reproducibility |
| U10 | Run code, client, and LLM API calls on the Ubuntu GPU VM; run CARLA in Docker without a window | Verify scenes through saved RGB/semantic frames or video; a browser viewer is optional |
| U11 | Use LLMs only through APIs | Do not install local weights or inference servers |
| U12 | The VM is disposable; code and data must survive its deletion | Use Git for code and documents, external storage for large outputs |
| U13 | Complete stages as separate Codex tasks in VS Code Remote SSH | Use fixed stage numbers, independent acceptance criteria, and a continuation point in the status file |
| U14 | Record work for the report automatically | Scripts record measurements; the agent maintains documents after meaningful work |

## Required Outcome and Implementation Options

All original assignment items and the clarifications above are required. Suggested repeat counts, weather-condition counts, and SceneSpec format are project decisions, not wording from the assignment author.

The assignment does not require LLM training or fine-tuning, training an autonomous driver, LiDAR, a fully AV2-compatible file format, a browser viewer, realistic animal gait animation, rebuilding Unreal, or deploying Qwen locally on the GPU VM.

Weather changes alone do not prove a full seasonal change. If only rain, fog, or lighting are implemented, state that accurately. Do not present newer CARLA branches or dev-documentation features as capabilities of the downloaded image.

## Requirement Traceability

| Assignment item | Project stage | Primary evidence |
|---|---|---|
| 1.1–1.2 | 0–1 | Versions, configuration, Python-to-CARLA connection log, test frame |
| 1.3–1.4 | 1 | Actual map, object catalogue, road-marking before/after verification |
| 1.5 | 2 and 8 | Five saved routes, waypoint counts, visualization |
| 1.6 | 2 | Traffic Manager drives, route completion, failures |
| 1.7–1.8 | 3 | Calibrations, transforms, 18 streams, timestamp and JSON validation |
| 1.9 | 4 | Baseline drives, weather configurations, dataset validation |
| 2 | 5 | Source review with methods and reproducibility analysis |
| 3 | 6 | Prompts, outputs from different LLMs, applied scenes, and metrics |
| 4 | 7 | Animal, trajectory, visibility, effect, and cross-model results |
| 5 | 8 | Comparable repeated drives and analysis |
| Final delivery | 9 | Report, dataset archives/directories, public repository, verified links |
