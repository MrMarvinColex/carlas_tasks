# Environment Entry Point

Use [VM workflow](vm-workflow.md) for setup/export/end of session and [archived environment](archive/assignment-2026/docs/environment.md) for historical hardware/version evidence, not live rental facts.

Current work is offline on Mac. Baseline execution uses Ubuntu 22.04/NVIDIA, offscreen Docker CARLA 0.9.16 and compatible isolated Python. Recheck client/server versions, image digest, GPU, disk, Docker permissions and repository path on a new VM. Read actual home; previous path was `/home/Ubuntu/carlas_tasks`.

Large animal assets/derived images are restored separately from Git; [scenes](scenes.md) links source/hash evidence. Restore API credentials securely; do not put them in documentation.
