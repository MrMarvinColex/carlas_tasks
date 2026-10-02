"""Bounded, read-only CARLA RPC health probe; client import is deliberately lazy."""
from __future__ import annotations


def server_status(host: str = "127.0.0.1", port: int = 2000, timeout_seconds: float = 2.0) -> dict[str, object]:
    try:
        import carla
        client = carla.Client(host, port)
        client.set_timeout(timeout_seconds)
        server_version = client.get_server_version()
        world = client.get_world()
        return {"ready": True, "host": host, "port": port,
                "server_version": server_version, "client_version": client.get_client_version(),
                "map_name": world.get_map().name}
    except ImportError:
        return {"ready": False, "reason": "CARLA client is unavailable; use the VM runtime environment"}
    except RuntimeError:
        return {"ready": False, "host": host, "port": port, "reason": "CARLA RPC is not responsive"}
