# Work Log

This log preserves chronology. `STATUS.md` contains the short current state. Future scripts record measurements; the agent adds explanation and links. Do not enter expected results as completed work.

## 2026-09-15–2026-09-16 — Assignment Analysis in the Original Chat

**Type:** document study, discussion, and documentation review; not a server experiment.

- Read the two-page PDF. Identified items 1.1–1.9 and 2–5, submission materials, and deadline.
- Discussed CARLA 0.9.16/0.10.0, the distinction between a release and development branch, runtime changes, and Unreal authoring.
- The user clarified: all AV2 cameras, paired RGB/semantic sensors, ego transform, minimum sufficient animal complexity, and comparison of three model variants.
- Selected an approach based on saved scene configurations and verifiable CARLA operations.
- Refined early assumptions about road markings, animal assets, and route duration; their status is recorded in `decisions.md` and `knowledge.md`.

**Evidence:** local source PDF, requirement text and clarifications in `requirements.md`, source index in `knowledge.md`.

**Result:** scope defined. Project code and dataset were not created.

## 2026-09-16 — User-Reported Prepared VM

**Type:** reported by the user. Exact times of the checks were not supplied.

The user rented a Massed Compute VM with an RTX A6000 48 GB, Ubuntu 22.04.5, 6 vCPU, 96 GB RAM, and a 300 GB SSD. They checked the GPU/driver, Docker/NVIDIA toolkit, downloaded `carlasim/carla:0.9.16`, and successfully launched CARLA offscreen. Unreal used the GPU and approximately 1.66 GB VRAM; the server opened a client port. The test container was then stopped and the image remained cached.

**Evidence limitation:** raw logs and commands were not supplied. Recording from 18 cameras, Town01, routes, marking removal, and an animal are not confirmed.

**Consequence:** do not repeat the entire installation without inspecting current state. Preserve current measurements and complete the reproducible environment/external storage in stage 0.

## 2026-09-16 — Portable Migration Package Prepared

**Type:** local-document work; no VM connection and no project implementation.

- Created AGENTS, README, requirements, fixed stage plan 0–9, initial status, decisions, environment description, runbook, and knowledge base.
- Created the report scaffold with unfilled experimental results, an empty artifact registry, and an environment template with no keys.
- Added a reading order, acceptance criteria, evidence recording, and independent-copy checks before VM deletion for the next agent.
- Included a local copy of the source PDF and excluded it from Git by default.

**Document verification:** confirmed the presence of 15 files, resolution of 18 internal Markdown links, fixed stage numbers 0–9 and their acceptance criteria, coverage of assignment items 1.1–1.9 and 2–5 in the report, 14 user clarifications, no populated API keys, and no invented records in the artifact registry. `.gitignore` rules were checked in a separate temporary Git repository: secrets/data are excluded, while documents, registry, and `.env.example` remain trackable.

**Source check:** the SHA-256 of the copied PDF matched the original: `277b2a653cbe40481d4011784cef8bbf4003b0f05e1ff8bb0f3207e275d6e248`. Portable documents contain no absolute path to the computer where the package was prepared.

**Result:** portable context prepared. The archive and documents are not evidence that server stages were completed.

**Next action:** transfer the package into the project, inspect existing server work, and complete the remaining portion of stage 0.

## 2026-09-16 — English Translation of the Portable Documentation

**Type:** local-document update; no VM connection and no project implementation.

- Translated the operating instructions, project documentation, and report scaffold into English without changing established requirements, decisions, open questions, or experimental status.
- Kept the original Russian PDF as the verbatim source. Russian remains only where it is useful to support Russian user commands and language instructions.
- Preserved identifiers, stage numbering, requirement IDs, links, empty placeholders, and the distinction between verified facts, decisions, hypotheses, and uncompleted experiments.
- Rebuilt and verified the deliverable archive after translation.

**Result:** the package is ready for an English-document workflow while the user may continue giving Codex instructions in Russian.

## Template for the Next Entry

```text
Date and time with time zone:
Stage / assignment item:
Evidence type: completed and verified / reported / hypothesis
Goal:
What changed:
Commands or links to working scripts (without keys):

How it was checked:
Actual result, including errors:
Artifacts and external copy:
Decisions / limitations:
Next concrete action:
```

When correcting an erroneous entry, add a dated clarification and link; do not hide history. If a measurement is absent, write `not measured`. For complex runs, a short entry with a link to machine logs is enough.
