#!/usr/bin/env python3
"""Run the detector and tracker over a recorded camera clip and log every sighting (confirmed,
moved, gone) with its time: what the robot would remember from that clip.

    python -m bench.clip_sightings CLIP.mkv        on the Jetson; writes SHARED/results
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import cv2

from robot.camera import ROTATE
from robot.config import SHARED
from robot.detect import Detector, Tracker

FPS = 15  # the robot's detection rate


def main(clip: Path) -> int:
    cap, detect, tracker = cv2.VideoCapture(str(clip)), Detector(), Tracker()
    step = max(1, round(cap.get(cv2.CAP_PROP_FPS) / FPS))
    rows, labels, k = [], Counter(), 0
    while (ok := cap.grab()):
        k += 1
        if k % step:
            continue
        ok, frame = cap.retrieve()
        t = k / cap.get(cv2.CAP_PROP_FPS)
        frame = cv2.rotate(frame, ROTATE)  # mounted upside down, as robot/camera.py does
        dets = detect(frame)
        labels.update(d.label for d in dets)
        for s in tracker.update(dets, frame.shape[1], t):
            rows.append({"t": round(t, 2), "track": s.track, "label": s.label,
                         "region": s.region, "gone": s.gone})
            print(json.dumps(rows[-1]), flush=True)
    detect.close()
    summary = {"summary": "clip", "clip": clip.name, "frames": k, "detected": dict(labels),
               "release": os.environ.get("ROBOT_RELEASE")}
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-clip-{int(time.time())}.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in [*rows, summary]))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
