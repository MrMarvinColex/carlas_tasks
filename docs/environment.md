# Environment and Infrastructure Facts

This file began as a user report. The entries labelled **artifact-confirmed** below were checked on the current VM on 2026-09-16 21:01–21:07 UTC; retain the user report where a fact was not independently checked.

## Current Server VM

| Parameter | Value | Evidence |
|---|---|---|
| Provider | Massed Compute, full VM | User-reported |
| Plan | Premium, $0.57/hour | User-reported; not a current billing check |
| GPU | NVIDIA RTX A6000, advertised 48 GB VRAM | User-reported |
| Terminal-reported GPU | 49,140 MiB, compute capability 8.6 | Check result relayed by user |
| CPU / RAM / SSD | 6 vCPU / 96 GB / 300 GB | User-reported |
| OS | Ubuntu 22.04.5 LTS | User-reported |
| SSH user | `Ubuntu` | User-reported; preserve case |
| Working directory | `/home/Ubuntu/carlas_tasks` | Artifact-confirmed; differs from the historical path in the transfer package |
| Client | Mac + VS Code Remote SSH + Codex extension | User-selected workflow |
| NVIDIA driver | 580.126.09 | Check result relayed by user |
| CUDA shown by GPU tools | 13.0 | Does not prove that this CUDA Toolkit is installed in the container |
| Docker | 29.1.5, available through `sudo` | Check result relayed by user |
| NVIDIA Container Toolkit | `nvidia-container-cli` 1.18.1 | Check result relayed by user |
| CARLA image | `carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953` | Artifact-confirmed; local image ID `98d224…83b5`, 20,705,974,366 bytes |

## Checks Already Run by the User

1. CARLA 0.9.16 successfully started headless/offscreen in Docker.
2. The Unreal process used the GPU and approximately 1.66 GB VRAM in the test launch.
3. The server opened a client port; the exact bind, port, and launch command were not preserved in the chat.
4. The test container was then stopped; the pulled image remains on the current VM.
5. `vulkaninfo` was unavailable. This is not blocking because real rendering has already launched.

The VRAM figure is from a small test run; it cannot estimate 18 full-resolution cameras. Client frame retrieval is now confirmed by the stage-0 smoke run; Town01, synchronisation, 18 cameras, road markings, and animal assets remain untested.

## 2026-09-16 Stage-0 Actual Check

- **artifact-confirmed:** Ubuntu 22.04.5, kernel 6.8.0-90-generic; 94 GiB RAM with 92 GiB available; 246 GiB free of a 295 GiB filesystem.
- **artifact-confirmed:** NVIDIA RTX A6000, driver 580.126.09, 49,140 MiB VRAM, compute capability 8.6; no GPU process at check time. Docker 29.1.5 and NVIDIA Container Toolkit 1.18.1 are usable via passwordless `sudo`.
- **artifact-confirmed:** no CARLA container or listener on ports 2000–2002 existed before the smoke run. The temporary `carla-server` was stopped afterwards.
- **artifact-confirmed:** Python 3.10.12 client environment at `.venv`, with `carla==0.9.16`. Installing `python3.10-venv` was required because the original OS image lacked `ensurepip`.
- **artifact-confirmed:** run `20260916T210617Z-carla-smoke-beb230` connected to CARLA, recorded matching client/server 0.9.16 versions, saved an 800×600 RGB PNG, and passed its local manifest check. Its default map was `Carla/Maps/Town10HD_Opt`; no Town01 operation was performed.

## Selected Execution Model

- CARLA Server: Docker on the GPU VM, offscreen rendering.
- Python client, route generation, dataset capture, and LLM API calls: same VM in an isolated Python environment.
- LLMs: external APIs only. Do not reserve GPU for local Qwen or download model weights.
- Viewing: saved RGB/semantic frames, contact sheets, and video. A browser live viewer is optional.
- The user reports that `http://<IP>:300` in the provider panel is for ThinLinc/remote desktop. It is not a CARLA URL.
- Offscreen rendering and no-rendering mode are different. Camera images require rendering to remain enabled; verify real world settings.

Do not expose CARLA ports publicly merely because client and server share the VM. Choose and record the Docker network/bind/ports during implementation. Ports 2000/2001 are standard candidates, not verified facts. Do not alter firewall rules unless necessary.

## First Checks for the New Task

Record without secrets: OS/GPU/driver/Docker versions, free disk and RAM, image ID/digest, project-related containers, actual launch command and ports, Python/dependency versions, CARLA server/client versions, sync settings, and Git state.

Check whether `~/carla_test_task` already contains working scripts. Read and validate them before creating a second incompatible startup workflow.

Billing, access, and running-process facts belong to a specific VM and date. Recheck them on any new rental; never put certificates, keys, or private endpoints in public documentation.

## Billing and Deletion

The user reports that **Delete**, not Stop, is needed to stop billing. Deleting the VM is irreversible; the Docker image, working directory, `.env`, and unexported data disappear. Follow the [preservation procedure](runbook.md) and check the provider’s current warning before acting.

At the user-reported rate, 10 hours cost $5.70 and 24 hours cost $13.68, excluding possible additional charges. This is arithmetic from the stated rate, not a billing guarantee. Batch GPU work; review literature and write the report without the paid VM whenever possible.

## Not Yet Determined

- Private repository URL and development branch.
- External result-storage destination and current credentials.
- API providers, exact model IDs, keys, budget, and rate limits.
- Python/client wheel and final pinned dependencies.
- Image digest, container name, startup arguments, and volume mounts.
- Actual data volume and render throughput with 18 sensors.

Add final tested commands to the README and runbook only after they succeed on the server.
