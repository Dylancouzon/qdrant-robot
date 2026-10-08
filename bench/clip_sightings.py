#!/usr/bin/env python3
"""Run the detector and tracker over a recorded camera clip and report what the robot would
remember: sightings (confirmed, moved, gone), tracks, relabeled tracks, and label stability, for
each half of the clip (thresholds are chosen on the first half; the second is held out).

    python -m bench.clip_sightings CLIP.avi       on the Jetson; writes SHARED/results with the
                                                  detections of every frame
    python -m bench.clip_sightings RESULT.jsonl   replay those detections through the current
                                                  tracker, no model (Mac); prints the summary
"""
import json
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from robot.camera import ROTATE
from robot.config import SHARED
from robot.detect import Detection, Tracker
from robot.main import Robot
from robot.memory import CountRequest, Memory

FPS = 15  # the robot's detection rate
WIDTH = 1280
HALF = 45.0  # seconds: the first half tunes, the second is held out (gates/review.md rule 6)


def frames(clip: Path):
    """(time, detections) per detected frame of a clip, at the robot's detection rate."""
    from robot.detect import Detector
    cap, detect, k = cv2.VideoCapture(str(clip)), Detector(), 0
    step = max(1, round(cap.get(cv2.CAP_PROP_FPS) / FPS))
    while cap.grab():
        k += 1
        if k % step:
            continue
        frame = cv2.rotate(cap.retrieve()[1], ROTATE)  # mounted upside down, as camera.py does
        assert frame.shape[1] == WIDTH, frame.shape
        yield k / cap.get(cv2.CAP_PROP_FPS), detect(frame)
    detect.close()


def recorded(result: Path):
    for line in result.read_text().splitlines():
        if "dets" in (row := json.loads(line)):
            yield row["t"], [Detection(d[0], d[1], tuple(d[2:])) for d in row["dets"]]


def track(source) -> tuple[list[dict], list[dict], dict]:
    """Feed every frame to a Tracker and its sightings to the robot's sighting writes on an
    empty shard; returns the frame rows, the sighting rows, and the points stored (now, peak)."""
    tracker, frame_rows, rows, peak = Tracker(), [], [], 0
    robot = Robot.__new__(Robot)  # no models: the sighting writes only
    tmp = tempfile.TemporaryDirectory()
    robot.memory, robot.points, robot.away = Memory(Path(tmp.name)), {}, set()
    robot.visitors = {}
    for t, dets in source:
        frame_rows.append({"t": round(t, 3), "dets": [[d.label, round(d.conf, 3), *d.box]
                                                      for d in dets]})
        if found := tracker.update(dets, WIDTH, t):
            robot._sight(found)
            peak = max(peak, robot.memory.shard.count(CountRequest()))
        for s in found:
            if s.ended:  # frees the tracker's id; memory is not written
                continue
            rows.append({"t": round(t, 2), "track": s.track, "label": s.label,
                         "region": s.region, "gone": s.gone})
        for tr in tracker.tracks:  # what each confirmed track matched, for label stability
            if tr.missed == 0:
                rows.append({"t": round(t, 2), "track": tr.id, "matched": tr.det.label})
    stored = {"points": robot.memory.shard.count(CountRequest()), "peak": peak}
    robot.memory.shard.close()
    tmp.cleanup()
    return frame_rows, rows, stored


def summarize(rows: list[dict], start: float, end: float) -> dict:
    """Counts for the tracks first reported in [start, end). A track's label is off when it
    differs from the most common label of the detections the track matched: `first_label_off`
    for the label of its first sighting (what memory kept before majority labels), `last_label_off`
    for its last (what memory holds now)."""
    said, matched = defaultdict(list), defaultdict(Counter)
    for r in rows:
        if "matched" in r:
            matched[r["track"]][r["matched"]] += 1
        elif not r["gone"]:
            said[r["track"]].append((r["t"], r["label"]))
    ids = [i for i, s in said.items() if start <= s[0][0] < end]
    top = {i: matched[i].most_common(1)[0] for i in ids}
    return {"tracks": len(ids),
            "first_label_off": sum(said[i][0][1] != top[i][0] for i in ids),
            "last_label_off": sum(said[i][-1][1] != top[i][0] for i in ids),
            "mixed_detections": sum(len(matched[i]) > 1 for i in ids),
            "label_stability": round(sum(top[i][1] / sum(matched[i].values()) for i in ids)
                                     / max(1, len(ids)), 3),
            "sightings": sum(1 for r in rows if "matched" not in r and r["track"] in ids)}


def main(src: Path) -> int:
    replay = src.suffix == ".jsonl"
    frame_rows, rows, stored = track(recorded(src) if replay else frames(src))
    summary = {"summary": "clip", "source": src.name, "frames": len(frame_rows), "stored": stored,
               "first_half": summarize(rows, 0, HALF), "second_half": summarize(rows, HALF, 1e9),
               "release": os.environ.get("ROBOT_RELEASE")}
    print(json.dumps(summary))
    if not replay:
        out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-clip-{int(time.time())}.jsonl"
        sightings = [r for r in rows if "matched" not in r]
        out.write_text("".join(json.dumps(r) + "\n" for r in [*frame_rows, *sightings, summary]))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
