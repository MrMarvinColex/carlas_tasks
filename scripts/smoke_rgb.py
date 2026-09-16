#!/usr/bin/env python3
"""Capture one RGB frame, record CARLA client/server versions, and clean up its actors."""
from __future__ import annotations

import argparse
import json
import queue
import sys
import time
from pathlib import Path

import carla


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def update_metadata(path: Path, **values: object) -> None:
    content = json.loads(path.read_text())
    content.update(values)
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=2000, type=int)
    parser.add_argument("--timeout", default=30.0, type=float)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    vehicle = camera = None
    received: queue.Queue[carla.Image] = queue.Queue()
    try:
        world = client.get_world()
        spawn_points = world.get_map().get_spawn_points()
        if not spawn_points:
            raise RuntimeError("map has no vehicle spawn points")
        vehicle_bp = world.get_blueprint_library().filter("vehicle.*")[0]
        for transform in spawn_points:
            vehicle = world.try_spawn_actor(vehicle_bp, transform)
            if vehicle is not None:
                break
        if vehicle is None:
            raise RuntimeError("could not reserve a vehicle spawn point")
        camera_bp = world.get_blueprint_library().find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", "800")
        camera_bp.set_attribute("image_size_y", "600")
        camera_bp.set_attribute("fov", "90")
        camera = world.spawn_actor(
            camera_bp,
            carla.Transform(carla.Location(x=1.6, z=2.3)),
            attach_to=vehicle,
        )
        camera.listen(received.put)
        image = received.get(timeout=args.timeout)
        output = run_dir / "rgb" / "front.png"
        output.parent.mkdir(exist_ok=True)
        image.save_to_disk(str(output))
        if output.read_bytes()[:8] != PNG_SIGNATURE:
            raise RuntimeError("saved frame is not a readable PNG signature")
        snapshot = world.get_snapshot()
        update_metadata(
            metadata_path,
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=world.get_map().name,
            smoke_frame={"frame": image.frame, "timestamp": image.timestamp, "path": "rgb/front.png", "width": image.width, "height": image.height},
            state="running",
        )
        print(output)
    except Exception as exc:
        update_metadata(metadata_path, state="failed", smoke_error=str(exc))
        raise
    finally:
        if camera is not None:
            camera.stop()
            camera.destroy()
        if vehicle is not None:
            vehicle.destroy()


if __name__ == "__main__":
    main()
