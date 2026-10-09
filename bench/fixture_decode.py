"""Freeze a deployed decoder's sequential pixel oracle and check every indexed fixture frame.

Run on Jetson through tools/jetson.py, under an external native-process watchdog.
"""

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import cv2

from robot.config import SHARED


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pixels(frame):
    return hashlib.sha256(frame.tobytes()).hexdigest()


def main(folder):
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        raise RuntimeError("deployed decoder qualification runs on Jetson")
    paths = sorted(folder.glob("*.avi"))
    if not paths:
        raise ValueError("no fixture AVIs")
    result = (
        SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-fixture-decode-{time.time_ns()}.jsonl"
    )
    result.parent.mkdir(parents=True, exist_ok=True)
    with result.open("x") as stream:

        def emit(row):
            stream.write(json.dumps(row) + "\n")
            stream.flush()

        emit(
            {
                "type": "metadata",
                "machine": platform.node(),
                "release": os.environ.get("ROBOT_RELEASE"),
                "command": sys.argv,
                "code_sha256": digest(Path(__file__)),
                "n_expected": len(paths),
                "python": platform.python_version(),
                "opencv": cv2.__version__,
                "precision": "uint8 BGR pixels",
                "video_build": [
                    line.strip()
                    for line in cv2.getBuildInformation().splitlines()
                    if any(key in line for key in ("avcodec:", "avformat:", "avutil:", "JPEG:"))
                ],
                "models_loaded": False,
                "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
            }
        )
        total = 0
        for path in paths:
            started = time.monotonic()
            cap = cv2.VideoCapture(str(path))
            try:
                cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
                assert cap.isOpened()
                backend, fps, count = (
                    cap.getBackendName(),
                    cap.get(cv2.CAP_PROP_FPS),
                    cap.get(cv2.CAP_PROP_FRAME_COUNT),
                )
                assert fps == 15 and count >= 1 and count.is_integer()
                hashes, shape = [], None
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if shape is None:
                        shape = list(frame.shape)
                    assert list(frame.shape) == shape
                    hashes.append(pixels(frame))
                assert len(hashes) == int(count)
            finally:
                cap.release()
            indexed = cv2.VideoCapture(str(path))
            try:
                indexed.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
                for index in reversed(range(len(hashes))):
                    assert indexed.set(cv2.CAP_PROP_POS_FRAMES, index)
                    ok, frame = indexed.read()
                    assert ok and pixels(frame) == hashes[index], (path.name, index)
            finally:
                indexed.release()
            total += len(hashes)
            elapsed = time.monotonic() - started
            emit(
                {
                    "type": "source",
                    "file": path.name,
                    "sha256": digest(path),
                    "bytes": path.stat().st_size,
                    "backend": backend,
                    "fps": fps,
                    "shape": shape,
                    "frames": len(hashes),
                    "indexed_matches": len(hashes),
                    "decoded_bgr_sha256": hashes,
                    "elapsed_s": elapsed,
                }
            )
            print(
                f"verified {path.name}: {len(hashes)} indexed frames in {elapsed:.2f}s", flush=True
            )
        emit(
            {
                "summary": "fixture_decode",
                "n": len(paths),
                "n_expected": len(paths),
                "frames": total,
                "indexed_matches": total,
                "completed": True,
                "note": "Pixel oracle only; confirm outer unit exit separately.",
            }
        )
    print(f"saved {result}", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
