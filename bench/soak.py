#!/usr/bin/env python3
"""Live soak: the whole robot on the live camera with no speech, for a set time. Every minute it
logs the detection rate, sightings stored, process RSS, and swap; tegrastats runs alongside.

    python -m bench.soak [minutes]        on the Jetson, through tools/jetson.py run
"""
import json
import os
import platform
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

from robot.camera import Camera
from robot.config import SHARED
from robot.main import Robot

DARK = 20.0  # mean frame brightness (0-255) below which the room is too dark to test


def swap_mb() -> float:
    info = dict(line.split(":") for line in Path("/proc/meminfo").read_text().splitlines())
    return (int(info["SwapTotal"].split()[0]) - int(info["SwapFree"].split()[0])) / 1024


def sample(robot: Robot, camera: Camera, since: float, seen: int, start: float) -> dict:
    return {"t_min": round((time.time() - start) / 60, 2),
            "detect_fps": (robot.detections - seen) / (time.time() - since),
            "points": robot.memory.shard.info().points_count,
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "swap_mb": swap_mb(), "light": float(camera.latest()[0].mean())}


def soak(robot: Robot, camera: Camera, minutes: float, out: Path) -> None:
    """Sample once a minute until the deadline; every row is written as it comes, so an
    interrupted soak leaves its evidence."""
    start = since = time.time()
    seen = 0
    while (now := time.time()) < start + minutes * 60:
        time.sleep(max(0.0, min(since + 60, start + minutes * 60) - now))
        row = sample(robot, camera, since, seen, start)
        since, seen = time.time(), robot.detections
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)


def main(minutes: float) -> int:
    camera = Camera()
    memory = Path(tempfile.mkdtemp())  # deleted after the run: it holds frames of people
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-soak-{int(time.time())}.jsonl"
    head = {"summary": "soak", "minutes": minutes, "machine": platform.node(),
            "release": os.environ.get("ROBOT_RELEASE"),
            "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "swap_start_mb": swap_mb()}
    robot = None
    try:
        time.sleep(2)
        frame = camera.latest()[0]
        light = float(frame.mean()) if frame is not None else 0.0
        out.write_text(json.dumps({**head, "light_start": light, "complete": False}) + "\n")
        if light < DARK:
            print(f"too dark or no frame ({light:.1f}): no soak")
            return 2
        robot = Robot(camera, SHARED / "sessions" / f"soak-{int(time.time())}", memory=memory)
        soak(robot, camera, minutes, out)
        if robot.detect_failed:  # detection stopped after its retries: not a complete soak
            print("detection failed during the soak")
            return 1
        with out.open("a") as f:
            f.write(json.dumps({"summary": "soak", "complete": True}) + "\n")
        return 0
    finally:
        try:
            if robot:
                robot.close()
        finally:
            try:
                camera.close()
            finally:
                shutil.rmtree(memory, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 30))
