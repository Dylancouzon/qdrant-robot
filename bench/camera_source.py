"""Jetson-only 30-second concurrent fixture source qualification, with a pixel oracle.

Run through tools/jetson.py run camera-source -- -m bench.camera_source SOURCE.
Constant-rate captured files only. Stored orientation is preserved; no models run.
"""
import hashlib
import json
import math
import os
import platform
import queue
import resource
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from robot.camera import FileCamera
from robot.config import ROOT, SHARED

SECONDS = 30
PERIODS = {"detector": 1 / 15, "watcher": 0.3, "speech_start": 1.0}


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pixels(frame):
    return hashlib.sha256(frame).hexdigest()


def oracle(path, emit):
    """Decode every frame sequentially before timing; retain hashes only."""
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
        fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if (not cap.isOpened() or not math.isfinite(fps) or fps <= 0
                or not math.isfinite(count) or count < 1 or not count.is_integer()):
            raise ValueError("invalid source metadata")
        hashes, progress = [], time.monotonic()
        for i in range(int(count)):
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError(f"oracle decode failed at {i}")
            hashes.append(pixels(frame))
            if time.monotonic() - progress >= 1:
                emit({"phase": "oracle", "frames": len(hashes)})
                progress = time.monotonic()
        if cap.read()[0]:
            raise ValueError("source frame count disagrees with sequential decoding")
        if count / fps < SECONDS + 2 / fps:
            raise ValueError("source must cover 30 seconds without final-frame hold")
        return fps, hashes
    finally:
        cap.release()


def reader(name, source, start, anchor, fps, hashes, messages, stop):
    period = PERIODS[name]
    try:
        for slot in range(math.ceil(SECONDS / period)):
            due = slot * period
            if name == "detector" and 15 <= due < 15.5:
                if stop.wait(max(0, start + 15.5 - time.monotonic())):
                    return
                continue
            if stop.wait(max(0, start + due - time.monotonic())):
                return
            before = time.monotonic()
            frame, stamp = source.latest()
            after, wall = time.monotonic(), time.time()
            index = round((stamp - anchor) * fps)
            digest = pixels(frame)
            matches = [i for i, value in enumerate(hashes) if value == digest]
            messages.put({"caller": name, "slot": slot, "elapsed_s": after - start,
                          "index": index, "actual_index": matches[0] if len(matches) == 1 else None,
                          "matching_indices_count": len(matches),
                          "identity_ok": 0 <= index < len(hashes) and hashes[index] == digest,
                          "latest_ms": (after - before) * 1000,
                          "frame_age_ms": (wall - stamp) * 1000})
    except Exception as error:
        messages.put({"error": repr(error), "caller": name})
        stop.set()


def summarize(rows, fps):
    callers, passed = {}, True
    for name, period in PERIODS.items():
        samples = [r for r in rows if r["caller"] == name]
        indices = sorted({r["index"] for r in samples})
        expected = sum(not (name == "detector" and 15 <= i * period < 15.5)
                       for i in range(math.ceil(SECONDS / period)))
        latency = np.percentile([r["latest_ms"] for r in samples], [50, 95]).tolist()
        age = np.percentile([r["frame_age_ms"] for r in samples], [50, 95]).tolist()
        ok = (len(samples) == expected and latency[1] <= 1000 / fps
              and age[1] <= 2000 / fps and all(r["identity_ok"] for r in samples))
        callers[name] = {"samples": len(samples), "expected_samples": expected,
                         "unique_indices": len(indices), "source_fps": len(indices) / SECONDS,
                         "latest_p50_p95_ms": latency,
                         "frame_age_p50_p95_ms": age,
                         "skipped_frames": sum(max(0, b - a - 1)
                                               for a, b in zip(indices, indices[1:], strict=False)),
                         "pass": ok}
        passed &= ok
    union = sorted({r["index"] for r in rows})
    return {"callers": callers, "pass": passed, "samples": len(rows),
            "expected_samples": sum(c["expected_samples"] for c in callers.values()),
            "unique_indices": len(union), "union_source_fps": len(union) / SECONDS,
            "skipped_frames": sum(max(0, b - a - 1)
                                  for a, b in zip(union, union[1:], strict=False)),
            "rss_peak_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}


def measure(source, fps, hashes, emit):
    _, anchor = source.latest()
    start = time.monotonic()
    messages, stop, rows = queue.Queue(), threading.Event(), []
    threads = [threading.Thread(target=reader, name=name, daemon=True,
                               args=(name, source, start, anchor, fps, hashes, messages, stop))
               for name in PERIODS]
    for thread in threads:
        thread.start()
    progress = start
    try:
        while any(t.is_alive() for t in threads) or not messages.empty():
            try:
                row = messages.get(timeout=0.1)
            except queue.Empty:
                row = None
            if row is not None:
                emit(row)
                if "error" in row:
                    raise RuntimeError(row["error"])
                rows.append(row)
            now = time.monotonic()
            if now - progress >= 1:
                emit({"phase": "measure", "elapsed_s": now - start, "samples": len(rows),
                      "rss_peak_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024})
                progress = now
            if now - start > SECONDS + 5:
                raise RuntimeError("reader stalled; stop the outer named service")
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=1)
    if any(t.is_alive() for t in threads):
        raise RuntimeError("native reader remains blocked; stop the outer named service")
    return summarize(rows, fps)


def main(path):
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        raise RuntimeError("qualification runs on the Jetson only")
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-camera-source-{time.time_ns()}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as log:
        def emit(row):
            log.write(json.dumps(row) + "\n")
            log.flush()
            if "phase" in row or "summary" in row:
                print(json.dumps(row), flush=True)

        emit({"phase": "start", "source": str(path), "source_sha256": file_hash(path),
              "orientation": "stored", "machine": platform.platform(),
              "python": sys.version, "opencv": cv2.__version__, "models": "none",
              "release": os.environ.get("ROBOT_RELEASE"),
              "code_sha256": {p: file_hash(ROOT / p) for p in
                              ("robot/camera.py", "bench/camera_source.py")},
              "environment": (ROOT / "ENV.txt").read_text(),
              "command": " ".join(sys.argv), "tegrastats": os.environ["ROBOT_TEGRASTATS"],
              "seconds": SECONDS, "periods_s": PERIODS, "detector_pause_s": [15, 15.5],
              "limits": "latest p95 <= 1/fps; age p95 <= 2/fps; all pixels match oracle"})
        fps, hashes = oracle(path, emit)
        emit({"phase": "oracle_complete", "fps": fps, "frame_count": len(hashes)})
        source = FileCamera(path)
        try:
            result = measure(source, fps, hashes, emit)
        finally:
            # A blocked native thread needs the outer service to terminate the process.
            if not any(t.name in PERIODS and t.is_alive() for t in threading.enumerate()):
                source.close()
        emit({"summary": "camera-source", "complete": True, "fps": fps,
              "frame_count": len(hashes), **result})
        return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
