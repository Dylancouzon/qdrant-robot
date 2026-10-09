#!/usr/bin/env python3
"""Booth view cost on the live camera: detection and tracking at camera rate while llama-server
decodes, first with no view, then with a curl viewer on the MJPEG stream. Records detection fps,
decode tok/s, process CPU, the view thread's CPU, and JPEG draw-and-encode time.

    python -m bench.view_bench [--seconds 60] [--fps 15]     on the Jetson, via tools/jetson.py run
"""
import argparse
import json
import os
import platform
import subprocess
import threading
import time
import urllib.request

import cv2
import numpy as np

from robot.brain import URL, Brain
from robot.camera import Camera
from robot.config import SHARED
from robot.detect import Detector, Tracker
from robot.view import Screen, View, draw

TOKEN = "bench"


def decode_loop(stop: threading.Event, rates: list[float]) -> None:
    """Keep llama-server decoding 128 tokens per request; record its decode tok/s."""
    body = json.dumps({"prompt": "Tell me a long story about a robot at a conference.",
                       "n_predict": 128, "ignore_eos": True, "cache_prompt": False}).encode()
    while not stop.is_set():
        req = urllib.request.Request(f"{URL}/completion", body,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rates.append(json.load(r)["timings"]["predicted_per_second"])


class Robotish:
    """The robot's detection loop alone: the newest frame at `fps`, tracked under a lock; the
    view source is that frame with the confirmed tracks it matched."""

    def __init__(self, camera: Camera, fps: float):
        self.camera, self.fps, self.detect, self.tracker = camera, fps, Detector(), Tracker()
        self.lock, self.stop, self.frames = threading.Lock(), threading.Event(), 0
        self.shown: tuple = (None, [])
        self.view_cpu: list[tuple[float, float]] = []  # (wall, view thread CPU) per frame
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        due = time.time()
        while not self.stop.wait(max(0.0, due - time.time())):
            due = max(due + 1 / self.fps, time.time())
            frame, _ = self.camera.latest()
            if frame is None:
                continue
            with self.lock:
                self.tracker.update(self.detect(frame), frame.shape[1], time.time())
                boxes = [(*t.det.box, t.label, "known") for t in self.tracker.tracks
                         if t.missed == 0 and t.reported]
                self.shown = frame, Screen(boxes)
            self.frames += 1

    def source(self) -> tuple:
        self.view_cpu.append((time.monotonic(), time.thread_time()))
        with self.lock:
            return self.shown


def phase(bot: Robotish, seconds: float, url: str | None) -> dict:
    """Detection plus decode for `seconds`, with a curl viewer on `url` when given."""
    stop, rates = threading.Event(), []
    decoder = threading.Thread(target=decode_loop, args=(stop, rates))
    decoder.start()
    curl = url and subprocess.Popen(["curl", "-s", "-o", "/dev/null", "-w", "%{size_download}",
                                     "--max-time", str(seconds), url], stdout=subprocess.PIPE)
    bot.view_cpu.clear()
    frames, cpu, start = bot.frames, os.times(), time.monotonic()
    time.sleep(seconds)
    wall, used = time.monotonic() - start, os.times()
    row = {"detect_fps": round((bot.frames - frames) / wall, 2),
           "process_cpu_pct": round(100 * (used.user + used.system - cpu.user - cpu.system) / wall,
                                    1)}
    if curl:
        row["view_bytes"] = int(curl.communicate()[0] or 0)
        (w0, c0), (w1, c1) = bot.view_cpu[0], bot.view_cpu[-1]
        row |= {"view_frames": len(bot.view_cpu), "view_fps": round(len(bot.view_cpu) / wall, 2),
                "view_thread_cpu_pct": round(100 * (c1 - c0) / (w1 - w0), 1)}
    stop.set()
    decoder.join()
    return row | {"llm_tok_s": round(float(np.median(rates)), 1), "llm_requests": len(rates)}


def encode_ms(bot: Robotish, n: int = 200) -> list[float]:
    """draw() on the live frame and its boxes, the view thread's per-frame work."""
    times = []
    for _ in range(n):
        frame, screen = bot.source()
        t = time.perf_counter()
        draw(frame, screen, 960, time.time())
        times.append((time.perf_counter() - t) * 1000)
        time.sleep(1 / bot.fps)
    return times


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--fps", type=float, default=15, help="detection rate (robot.main.DETECT_FPS)")
    a = p.parse_args()
    camera = Camera()
    time.sleep(2)
    brain, bot = Brain(), Robotish(camera, a.fps)
    time.sleep(3)  # warm-up: engine, tracks
    row = {"command": "python -m bench.view_bench " + " ".join(f"--{k} {v}" for k, v in
                                                                 vars(a).items()),
           "machine": platform.node(), "release": os.environ.get("ROBOT_RELEASE"),
           "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
           "power": subprocess.run(["nvpmodel", "-q"], capture_output=True,
                                   text=True).stdout.split("\n")[0],
           "opencv": cv2.__version__, "view": {"fps_cap": 10, "width": 960, "jpeg_quality": 80},
           "light": round(float(camera.latest()[0].mean()), 1)}
    ms = encode_ms(bot)
    row |= {"encode_ms_p50": round(float(np.percentile(ms, 50)), 2),
            "encode_ms_p99": round(float(np.percentile(ms, 99)), 2)}
    row["without_view"] = phase(bot, a.seconds, None)
    view = View(bot.source, 8099, TOKEN)
    row["with_view"] = phase(bot, a.seconds, f"http://127.0.0.1:8099/?token={TOKEN}")
    view.close()
    bot.stop.set()
    brain.close()
    camera.close()
    print(json.dumps(row))
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-view-{int(time.time())}.jsonl"
    out.write_text(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
