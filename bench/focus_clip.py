#!/usr/bin/env python3
"""Replay a clip's recorded detections through the tracker and the focus object (robot/focus.py)
on the Mac, with no recognition (nothing taught), and score the focus against the items held up
in the clip: switches per minute, dwell, background focus, time to take a held item, scenery.
Both halves are development evidence: the rules were chosen with the whole clip in view
(reviews/20261008-202618-92452-review.md); an unseen clip is the test.

    python -m bench.focus_clip [RESULT.jsonl]    default: the live-items-1 clip detections
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from bench.clip_sightings import HALF, WIDTH, recorded
from robot import focus as F
from robot.detect import Tracker

CLIP = Path("bench/results/2026-10-08-clip-1791487472.jsonl")  # live-items-1.avi, 1331 frames
HEIGHT = 720
# Held up in live-items-1.avi (read off frames every 3 s): (start, end, detector labels the
# held item's track may carry). Any other focus is a background or worn object.
HELD = [(0.0, 46.5, {"phone"}), (58.5, 76.0, {"wallet", "camera"}), (77.0, 89.0, {"cup"})]


def frames(src: Path):
    """(time, focus Tracks, person boxes) per frame, from the current tracker."""
    tracker = Tracker()
    for t, dets in recorded(src):
        tracker.update(dets, WIDTH, t)
        live = [k for k in tracker.tracks if k.missed == 0 and k.reported]
        yield t, ([F.Track(k.id, k.det.box, k.label, k.votes[k.label] / k.hits)
                   for k in live if k.label != "person"],
                  [k.det.box for k in live if k.label == "person"])


def held(t: float) -> set[str]:
    return next((labels for a, b, labels in HELD if a <= t < b), set())


def replay(src: Path) -> tuple[list[dict], dict]:
    """One row per focus change (time, track, label, whether it is the held item) and per
    scenery mark; and when each held item's track was first in view in its window."""
    focus, rows, label, appear = F.Focus(WIDTH, HEIGHT), [], {}, {}
    for t, (tracks, people) in frames(src):
        label |= {k.id: k.label for k in tracks}
        for a, b, labels in HELD:
            if a <= t < b and any(k.label in labels for k in tracks):
                appear.setdefault(a, t)
        for e in focus.update(t, tracks, people):
            if e[0] == "focus":
                i = e[1]
                rows.append({"t": t, "focus": i, "label": label.get(i),
                             "held": i is not None and label[i] in held(t)})
            elif e[0] == "scenery":
                rows.append({"t": t, "scenery": e[1], "label": label[e[1]]})
    return rows + [{"t": t, "end": True}], appear


def score(rows: list[dict], appear: dict, start: float, end: float) -> dict:
    """Metrics for focus changes in [start, end); dwell counts intervals that start there."""
    changes = [r for r in rows if "focus" in r]
    stop = rows[-1]["t"]
    spans = [(a["t"], b["t"] if b else stop, a) for a, b in zip(changes, [*changes[1:], None],
                                                                  strict=True)]
    spans = [(a, b, r) for a, b, r in spans if r["focus"] is not None and start <= a < end]
    takes = [r for r in changes if r["focus"] is not None and start <= r["t"] < end]
    took = {}
    for a, b, _ in HELD:
        if start <= a < end:
            first = [r["t"] for r in takes if r["held"] and a <= r["t"] < b]
            took[f"{a:g}-{b:g}"] = round(first[0] - appear[a], 2) if first else None
    minutes = (min(end, stop) - start) / 60
    return {"seconds": round(min(end, stop) - start, 1), "takes": len(takes),
            "switches_per_min": round(len(takes) / minutes, 2),
            "dwell_p50_s": round(float(np.median([b - a for a, b, _ in spans])), 2) if spans
            else None,
            "background_takes": [(r["t"], r["label"]) for r in takes if not r["held"]],
            "background_seconds": round(sum(b - a for a, b, r in spans if not r["held"]), 2),
            "held_seconds_in_focus": round(sum(b - a for a, b, r in spans if r["held"]), 2),
            "time_to_focus_s": took,
            "scenery": [(r["t"], r["label"]) for r in rows if "scenery" in r
                        and start <= r["t"] < end]}


def main(src: Path) -> int:
    rows, appear = replay(src)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    diff = hashlib.sha256(subprocess.run(["git", "diff", "HEAD"], capture_output=True).stdout)
    summary = {"summary": "focus", "source": src.name, "machine": "mac (replay)",
               "revision": rev, "diff_sha256": diff.hexdigest()[:12],
               "command": "python -m bench.focus_clip " + str(src),
               "constants": {k: getattr(F, k) for k in (
                   "MIN_SIDE", "STEADY", "STEADY_S", "MOVED", "RECENT_S", "SCENERY_S", "GONE_S",
                   "HOLD_S", "MARGIN", "CUE", "HELD", "ZONE")} | {"BODY": sorted(F.BODY)},
               "recognition": "none (nothing taught)",
               "first_half": score(rows, appear, 0, HALF),
               "second_half": score(rows, appear, HALF, 1e9)}
    print(json.dumps(summary, indent=1))
    out = Path("bench/results") / f"{time.strftime('%Y-%m-%d')}-focus-{int(time.time())}.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in [*rows, summary]))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else CLIP))
