#!/usr/bin/env python3
"""Named-object crop embedding cost on the Jetson (M2.2b): RAM the DINOv2-small session adds
to a process that already uses CUDA, ms per crop alone, and llama-server decode tok/s with and
without crops embedded back to back (a bound: the robot embeds on its worker thread, which
runs turns too, so no crop overlaps a turn's decode; it embeds only new tracks of a named kind
and naming or "my X" turns).

    python -m bench.crop_cost [--seconds 30]     on the Jetson, via tools/jetson.py run
"""
import argparse
import json
import os
import platform
import threading
import time
import urllib.request

import cv2
import numpy as np
import onnxruntime as ort

from robot.brain import URL, Brain
from robot.config import ROOT, SHARED
from robot.text_embed import TextEmbedder
from robot.things import Crops


def rss_mb() -> float:
    return int(open("/proc/self/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20


def decode(stop: threading.Event, rates: list[float]) -> None:
    body = json.dumps({"prompt": "Tell me a long story about a robot at a conference.",
                       "n_predict": 128, "ignore_eos": True, "cache_prompt": False}).encode()
    while not stop.is_set():
        req = urllib.request.Request(f"{URL}/completion", body,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rates.append(json.load(r)["timings"]["predicted_per_second"])


def embed_ms(crops: Crops, crop: np.ndarray, seconds: float) -> list[float]:
    times, end = [], time.time() + seconds
    while time.time() < end:
        t = time.perf_counter()
        crops([crop])
        times.append(1000 * (time.perf_counter() - t))
    return times


def phase(seconds: float, work=None) -> dict:
    stop, rates = threading.Event(), []
    decoder = threading.Thread(target=decode, args=(stop, rates))
    decoder.start()
    ms = work(seconds) if work else time.sleep(seconds)
    stop.set()
    decoder.join()
    row = {"llm_tok_s": round(float(np.median(rates)), 1), "llm_requests": len(rates)}
    return row | ({"crop_ms_p50": round(float(np.percentile(ms, 50)), 2),
                   "crop_ms_p99": round(float(np.percentile(ms, 99)), 2), "crops": len(ms)}
                  if ms else {})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=30)
    a = p.parse_args()
    crop = cv2.imread(str(ROOT / "eval/dev/images/m2-phones.jpg"))[150:450, 700:900]
    TextEmbedder()(["warm"])  # the robot's process already holds a CUDA context
    before = rss_mb()
    crops = Crops()
    crops([crop])  # warm-up: CUDA kernels and the arena
    loaded = rss_mb()
    alone = embed_ms(crops, crop, 10)
    brain = Brain()
    row = {"command": f"python -m bench.crop_cost --seconds {a.seconds}",
           "machine": platform.node(), "release": os.environ.get("ROBOT_RELEASE"),
           "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "onnxruntime": ort.__version__,
           "providers": crops.sess.get_providers(), "model": "dinov2-small fp32, 224x224",
           "rss_added_mb": round(loaded - before, 1),
           "alone_ms_p50": round(float(np.percentile(alone, 50)), 2),
           "alone_ms_p99": round(float(np.percentile(alone, 99)), 2), "alone_n": len(alone),
           "decode_only": phase(a.seconds),
           "decode_with_crops": phase(a.seconds, lambda s: embed_ms(crops, crop, s))}
    brain.close()
    print(json.dumps(row))
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-crop-cost-{int(time.time())}.jsonl"
    out.write_text(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
