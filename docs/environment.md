# Environment and Infrastructure Facts

This file describes the environment **as reported by the user on 16 September 2026**. The documentation-package author did not connect to the server. Replace assumptions with current checks after migration while keeping dates and log references.

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
| Working directory | `~/carla_test_task` | User-reported |
| Client | Mac + VS Code Remote SSH + Codex extension | User-selected workflow |
| NVIDIA driver | 580.126.09 | Check result relayed by user |
| CUDA shown by GPU tools | 13.0 | Does not prove that this CUDA Toolkit is installed in the container |
| Docker | 29.1.5, available through `sudo` | Check result relayed by user |
| NVIDIA Container Toolkit | `nvidia-container-cli` 1.18.1 | Check result relayed by user |
| CARLA image | `carlasim/carla:0.9.16`, downloaded | Digest not yet recorded |

## Checks Already Run by the User

1. CARLA 0.9.16 successfully started headless/offscreen in Docker.
2. The Unreal process used the GPU and approximately 1.66 GB VRAM in the test launch.
3. The server opened a client port; the exact bind, port, and launch command were not preserved in the chat.
4. The test container was then stopped; the pulled image remains on the current VM.
5. `vulkaninfo` was unavailable. This is not blocking because real rendering has already launched.

The VRAM figure is from a small test run; it cannot estimate 18 full-resolution cameras. Client Python, frame retrieval, Town01, synchronisation, and animal assets have not been confirmed by project artifacts.

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
