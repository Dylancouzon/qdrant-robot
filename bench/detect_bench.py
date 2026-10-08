#!/usr/bin/env python3
"""Detector bench: labels on fixture frames, then detection plus tracking speed (fps, latency
percentiles, MemAvailable drop), optionally while llama-server decodes, with its tok/s.

    python -m bench.detect_bench --model yolo26n --backend tensorrt [--seconds 30] [--fps 15]
                                 [--camera] [--llm]
"""
import argparse
import hashlib
import json
import platform
import sys
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from bench.memory_budget import available_mb
from robot.config import MODELS, ROOT, SHARED
from robot.detect import HIGH, Detector, Tracker

ONNX = {"yolo26n": "yolo26n-384x640.onnx", "yoloe-pf": "yoloe-26n-seg-pf-384x640.onnx",
        "yoloe-booth": "yoloe-26n-booth-384x640.onnx"}  # export recipes: research/detector.md
LIVE = sorted((ROOT / "eval/dev/live").glob("closet-*.jpg"))  # 1280x720 camera frames
LABELLED = [p for p in LIVE if p.stem.endswith("-center") or p.stem == "closet-night"] + sorted(
    (ROOT / "eval/dev/images").glob("coco-*.jpg"))


def pct(xs: list[float], q: float) -> float:
    return round(float(np.percentile(xs, q)), 2)


def decode_loop(stop: threading.Event, rates: list[float]) -> None:
    """Keep llama-server decoding 128 tokens per request; record its decode tok/s."""
    from robot.brain import URL
    body = json.dumps({"prompt": "Tell me a long story about a robot at a conference.",
                       "n_predict": 128, "ignore_eos": True, "cache_prompt": False}).encode()
    while not stop.is_set():
        req = urllib.request.Request(f"{URL}/completion", body,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rates.append(json.load(r)["timings"]["predicted_per_second"])


def speed(detect: Detector, frames, seconds: float, fps: float) -> dict:
    """Detect and track for `seconds`; `frames()` returns the next frame (None: no new one)."""
    tracker, det_ms, track_ms, sightings, n = Tracker(), [], [], 0, 0
    start = time.perf_counter()
    while (now := time.perf_counter()) - start < seconds:
        frame = frames()
        if frame is None:
            time.sleep(0.002)
            continue
        dets = detect(frame)
        t = time.perf_counter()
        sightings += len(tracker.update(dets, frame))
        done = time.perf_counter()
        det_ms.append((t - now) * 1000)
        track_ms.append((done - t) * 1000)
        n += 1
        if fps:
            time.sleep(max(0.0, start + n / fps - time.perf_counter()))
    return {"frames": n, "fps": round(n / (time.perf_counter() - start), 1),
            "detect_ms_p50": pct(det_ms, 50), "detect_ms_p99": pct(det_ms, 99),
            "track_ms_p50": pct(track_ms, 50), "track_ms_p99": pct(track_ms, 99),
            "sightings": sightings}


def fixture_frames():
    images, i = [cv2.imread(str(p)) for p in LIVE], 0

    def next_frame():
        nonlocal i
        i += 1
        return images[i % len(images)]
    return next_frame


def camera_frames(cam):
    last = 0.0

    def next_frame():
        nonlocal last
        frame, stamp = cam.latest()
        if stamp == last:
            return None
        last = stamp
        return frame
    return next_frame


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=ONNX, default="yolo26n")
    p.add_argument("--backend", choices=["tensorrt", "ort-trt", "ort-cuda"], default="tensorrt")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--fps", type=float, default=0, help="loop rate cap (0: none)")
    p.add_argument("--camera", action="store_true", help="time live camera frames, not fixtures")
    p.add_argument("--llm", action="store_true", help="also run a llama-server decode loop")
    a = p.parse_args()
    import onnxruntime
    import tensorrt
    row = {"command": " ".join(sys.argv), "machine": platform.node(),
           "l4t": Path("/etc/nv_tegra_release").read_text().split(",")[0],
           "code": hashlib.sha256(b"".join(
               (ROOT / f).read_bytes() for f in ("robot/detect.py", "bench/detect_bench.py")
           )).hexdigest()[:12],
           "versions": {"tensorrt": tensorrt.__version__, "onnxruntime": onnxruntime.__version__,
                        "opencv": cv2.__version__, "numpy": np.__version__},
           "model": ONNX[a.model], "backend": a.backend,
           "precision": "fp32" if a.backend == "ort-cuda" else "fp16", "input": [384, 640],
           "source": "camera 1280x720" if a.camera else f"{len(LIVE)} fixture frames 1280x720"}
    before = available_mb()
    t = time.perf_counter()
    detect = Detector(MODELS / "detector" / ONNX[a.model], a.backend)
    for path in LIVE * 3:  # warm-up (and the ORT TensorRT engine build on its first run)
        detect(cv2.imread(str(path)))
    row |= {"load_s": round(time.perf_counter() - t, 1), "mem_drop_mb": before - available_mb()}
    row["labels"] = {}
    for path in LABELLED:
        dets = sorted(detect(cv2.imread(str(path))), key=lambda d: -d.conf)
        row["labels"][path.stem] = [f"{d.label} {d.conf:.2f}" for d in dets if d.conf >= HIGH][:6]
        print(f"{path.stem:28} {row['labels'][path.stem]}", flush=True)
    cam = None
    if a.camera:
        from robot.camera import Camera
        cam = Camera()
        time.sleep(2)
    frames = camera_frames(cam) if cam else fixture_frames()
    if a.llm:
        from robot.brain import Brain
        brain, stop, alone, shared = Brain(), threading.Event(), [], []
        worker = threading.Thread(target=decode_loop, args=(stop, alone))
        worker.start()
        time.sleep(a.seconds / 2)
        stop.set()
        worker.join()
        stop.clear()
        worker = threading.Thread(target=decode_loop, args=(stop, shared))
        worker.start()
        row |= speed(detect, frames, a.seconds, a.fps)
        stop.set()
        worker.join()
        brain.close()
        row |= {"llm_tok_s_alone": round(float(np.median(alone)), 1),
                "llm_tok_s_with_detector": round(float(np.median(shared)), 1)}
    else:
        row |= speed(detect, frames, a.seconds, a.fps)
    row["mem_available_end_mb"] = available_mb()
    if cam:
        cam.close()
    print(json.dumps({k: v for k, v in row.items() if k != "labels"}))
    out = SHARED / "results" / (f"{time.strftime('%Y-%m-%d')}-detect-{a.model}-{a.backend}"
                                f"{'-llm' if a.llm else ''}-{int(time.time())}.jsonl")
    out.write_text(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
