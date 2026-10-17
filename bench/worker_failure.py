"""Inject worker failures into the full Jetson robot with isolated test memories.

Run through tools/jetson.py run worker-failure -- -m bench.worker_failure --revision SHA.
"""
import argparse
import faulthandler
import gc
import json
import os
import platform
import tempfile
import time
from pathlib import Path

import numpy as np

from robot.brain import MODEL
from robot.camera import FileCamera
from robot.config import SHARED
from robot.main import Robot


def trial(arm: str, memory: Path, out: Path) -> dict:
    camera = FileCamera()
    robot = Robot(camera, out / arm, memory=memory, wake_word=False)
    row = {"arm": arm}
    injected = RuntimeError(f"injected {arm} failure")

    def fail(*args):
        raise injected

    try:
        camera.show(Path("eval/dev/live/closet-night.jpg"))
        if arm == "healthy":
            robot.ask("What is Qdrant Edge?")
            turn = robot.next_turn()
            assert turn.answer and turn.audio_s > 0, "healthy robot produced no speech"
            row["answer"], row["audio_s"] = turn.answer, turn.audio_s
        else:
            robot.recognition.pause()
            robot.jobs.join()
            robot.check_health()
            faulthandler.dump_traceback_later(30, exit=True)
            started = time.monotonic()
            if arm == "transcribe":
                robot.scribe = fail
                now = time.time()
                robot.lines.put((np.zeros(1600, np.float32), now, now, now,
                                 camera.latest(), None, None))
            else:
                robot._look = fail
                robot.jobs.put(("look", camera.latest()))
            try:
                robot.next_turn(timeout=5)
            except RuntimeError as error:
                assert error.__cause__ is injected, repr(error)
                row["reported"] = str(error)
            else:
                raise AssertionError("worker failure was not reported")
            row["report_s"] = time.monotonic() - started
    finally:
        started = time.monotonic()
        try:
            robot.close()
        except RuntimeError as error:
            if error.__cause__ is not injected:
                raise
            row["close_reported"] = str(error)
        finally:
            camera.close()
            faulthandler.cancel_dump_traceback_later()
        row["close_s"] = time.monotonic() - started
    assert all(not thread.is_alive() for thread in robot.threads)
    assert not robot.recognition.thread.is_alive() and not robot.speaker.thread.is_alive()
    assert robot.brain.proc.poll() is not None
    assert robot.lines.unfinished_tasks == robot.jobs.unfinished_tasks == 0
    row["ok"] = True
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    stamp = f"{time.strftime('%Y-%m-%d')}-worker-failure-{int(time.time())}"
    out = SHARED / "sessions" / stamp
    result = SHARED / "results" / f"{stamp}.jsonl"
    head = {"summary": "worker_failure", "revision": args.revision,
            "machine": platform.node(), "release": os.environ.get("ROBOT_RELEASE"),
            "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "model": MODEL,
            "python": platform.python_version(), "command": "python -m bench.worker_failure "
            f"--revision {args.revision}", "complete": False}
    result.write_text(json.dumps(head) + "\n")
    with tempfile.TemporaryDirectory() as memory:
        for arm in ("healthy", "transcribe", "work"):
            row = trial(arm, Path(memory), out)
            with result.open("a") as file:
                file.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
            gc.collect()  # release model sessions before reopening the same test shards
    with result.open("a") as file:
        file.write(json.dumps({**head, "complete": True, "n": 3}) + "\n")
    print(f"results: {result}", flush=True)


if __name__ == "__main__":
    main()
