#!/usr/bin/env python3
"""Booth view lag in the whole robot: the live camera, spoken fixture questions, and a viewer
on the MJPEG stream. Lag is the time a served frame was drawn minus its camera capture time;
detection fps comes from each turn.

    python -m bench.view_lag [--turns 6]     on the Jetson, via tools/jetson.py run
"""
import argparse
import json
import os
import statistics
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from robot.audio import paced, read_wav
from robot.camera import Camera
from robot.config import ROOT, SHARED
from robot.main import Robot

TOKEN = "bench"
QUESTIONS = ["intro-1", "desk-1", "joke-1", "conversation-1", "intro-3", "desk-2"]


def watch(port: int, stop: threading.Event) -> None:
    """A viewer that reads the stream until `stop`."""
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/?token={TOKEN}", timeout=10) as r:
        while not stop.is_set():
            r.read(65536)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--turns", type=int, default=6)
    a = p.parse_args()
    os.environ["ROBOT_VIEW_TOKEN"] = TOKEN
    camera = Camera()
    stamps: dict[int, float] = {}  # id(frame) -> capture time
    latest = camera.latest

    def stamped():
        frame, taken = latest()
        stamps[id(frame)] = taken
        return frame, taken

    camera.latest = stamped
    tmp = tempfile.TemporaryDirectory()
    robot = Robot(camera, Path(tmp.name) / "out", Path(tmp.name) / "memory")
    lags: list[tuple[float, float]] = []  # (served at, lag)
    shown = robot.video.source

    def timed():
        frame, boxes = shown()
        if frame is not None and id(frame) in stamps:
            lags.append((time.time(), time.time() - stamps[id(frame)]))
        return frame, boxes

    robot.video.source = timed
    stop = threading.Event()
    viewer = threading.Thread(target=watch, args=(robot.video.port, stop), daemon=True)
    viewer.start()
    time.sleep(3)
    turns = []
    for q in (QUESTIONS * 2)[:a.turns]:
        asked = robot.asked
        for chunk in paced(read_wav(ROOT / f"eval/dev/audio/{q}.wav"), 1.5):
            robot.hear(chunk)
        robot.lines.join()
        robot.check_health()
        turns += [robot.next_turn() for _ in range(robot.asked - asked)]
        time.sleep(turns[-1].audio_s + 1 if turns else 1)
    stop.set()
    robot.close()
    camera.close()
    tmp.cleanup()
    during = sorted(lag for t, lag in lags
                    if any(x.speech_start <= t <= x.done for x in turns))
    rows = [{"question": x.question, "detect_fps": round(x.detect_fps, 1),
             "first_audio_s": round(x.first_audio - x.speech_end, 3) if x.first_audio else None,
             "answer": x.answer} for x in turns]
    q = statistics.quantiles(during, n=100) if len(during) > 1 else [0] * 99
    summary = {"what": "view lag during spoken turns, live camera", "n_frames": len(during),
               "lag_p50_s": round(q[49], 3), "lag_p95_s": round(q[94], 3),
               "lag_max_s": round(during[-1], 3) if during else None,
               "detect_fps_min": min(r["detect_fps"] for r in rows) if rows else None,
               "detect_fps_p50": statistics.median(r["detect_fps"] for r in rows) if rows else None,
               "turns": len(rows), "release": os.environ.get("ROBOT_RELEASE"),
               "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
               "command": f"python -m bench.view_lag --turns {a.turns}"}
    print(json.dumps(summary), flush=True)
    stamp = f"{time.strftime('%Y-%m-%d')}-view-lag-{int(time.time())}"
    (SHARED / "results" / f"{stamp}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in [{"summary": summary}, *rows]))


if __name__ == "__main__":
    main()
