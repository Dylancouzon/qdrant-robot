"""Score "Is this the same thing I showed you before?" on dev image pairs, as the robot answers it:
different label groups say No; one group gets MaxSim from the configured crop vectors against
`same` and `guess_band`. Boxes come from the robot's detector run on each still (CPU, Mac);
each side is one crop, where the robot holds up to three. Never reads eval/heldout.

    ROBOT_SHARED=<repo with models/> .venv/bin/python bench/same_pairs.py
"""
import hashlib
import json
import platform
import shlex
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from robot.detect import MODEL as DETECTOR, Detector, region  # noqa: E402
from robot.memory import maxsim, same_thing  # noqa: E402
from robot.settings import DEFAULTS  # noqa: E402
from robot.things import MODEL as ENCODER, Crops, cut  # noqa: E402

DEV = ROOT / "eval/dev"
MATCH, BAND = DEFAULTS["same"], DEFAULTS["guess_band"]
# (category, truth, image A, label A, image B, label B); "label@region" picks one of two objects.
# "views": one object at two positions or in two frames; "class": two objects of one class (a
# swap in hand at one spot is a pair at the same region); "kinds": two classes. The closet-*
# images are our camera; m2-* paste COCO cut-outs onto it, so a same-object pair there shares
# its pixels (an easy case); coco-* are plain photos, and three closet-* images show a coco-*
# photo (cat right, apples, stop sign) resized and re-lit: the same object in another frame.
PAIRS = [
    ("views", "same", "live/closet-cat-center", "cat", "live/closet-cat-left", "cat"),
    ("views", "same", "live/closet-moto-center", "motorcycle", "live/closet-moto-left",
     "motorcycle"),
    ("views", "same", "live/closet-stopsign-center", "stop sign", "live/closet-stopsign-left",
     "stop sign"),
    ("views", "same", "images/m2-clock", "clock", "images/m2-clock-right", "clock"),
    ("views", "same", "images/m2-umbrella", "umbrella", "images/m2-umbrella-bag", "umbrella"),
    ("views", "same", "images/m2-umbrella", "umbrella", "images/m2-bag-umbrella", "umbrella"),
    ("views", "same", "images/m2-teddy-white", "teddy bear", "images/m2-teddies",
     "teddy bear@left"),
    ("views", "same", "images/m2-teddy-brown", "teddy bear", "images/m2-teddies",
     "teddy bear@right"),
    ("views", "same", "images/m2-banana", "banana", "images/m2-snack", "banana"),
    ("views", "same", "live/closet-cat-center", "cat", "images/coco-000000039769", "cat@right"),
    ("views", "same", "live/closet-apples-center", "apple", "images/coco-000000002149", "apple"),
    ("views", "same", "live/closet-stopsign-center", "stop sign", "images/coco-000000000724",
     "stop sign"),
    ("class", "different", "images/m2-teddy-white", "teddy bear", "images/m2-teddy-brown",
     "teddy bear"),
    ("class", "different", "images/m2-teddies", "teddy bear@left", "images/m2-teddies",
     "teddy bear@right"),
    ("class", "different", "images/m2-laptop", "laptop", "images/m2-laptop-silver", "laptop"),
    ("class", "different", "live/closet-teddy-center", "teddy bear", "images/m2-teddy-white",
     "teddy bear"),
    ("class", "different", "live/closet-teddy-center", "teddy bear", "images/m2-teddy-brown",
     "teddy bear"),
    ("class", "different", "live/closet-cat-center", "cat", "images/coco-000000039769",
     "cat@left"),
    ("class", "different", "images/m2-pepsi", "cup", "images/coco-000000001425", "cup"),
    ("class", "different", "live/closet-moto-center", "motorcycle", "images/coco-000000008211",
     "motorcycle"),
    ("kinds", "different", "images/m2-clock", "clock", "images/m2-laptop", "laptop"),
    ("kinds", "different", "images/m2-pepsi", "cup", "images/m2-banana", "banana"),
    ("kinds", "different", "live/closet-cat-center", "cat", "live/closet-moto-center",
     "motorcycle"),
    ("kinds", "different", "live/closet-apples-center", "apple", "live/closet-teddy-center",
     "teddy bear"),
    ("kinds", "different", "live/closet-stopsign-center", "stop sign", "images/m2-umbrella",
     "umbrella"),
    ("kinds", "different", "images/m2-umbrella-bag", "umbrella", "images/m2-banana", "banana"),
    ("kinds", "different", "images/m2-clock", "clock", "live/closet-cat-center", "cat"),
]


def crop(detector, frames, image, wanted):
    """The crop of the highest-confidence detection with the label (and region) wanted."""
    label, _, side = wanted.partition("@")
    if image not in frames:
        pixels = cv2.imread(str(DEV / f"{image}.jpg"))
        frames[image] = pixels, detector(pixels)
    frame, found = frames[image]
    boxes = [d.box for d in sorted(found, key=lambda d: -d.conf)
             if d.label == label and (not side or region(d.box, frame.shape[1]) == side)]
    assert boxes, f"no {wanted} in {image}"
    return cut(frame, boxes[0]).copy()


def verdict(score):
    """The robot's answer, by MaxSim alone, as `_same_answer` gives it."""
    said = same_thing(score, MATCH, BAND)
    return "same" if said.startswith("Yes") else "unsure" if said.startswith("It looks") \
        else "different"


def main():
    run = str(int(time.time()))
    detector, encoder, frames, rows = Detector(), Crops(), {}, []
    for category, truth, a, a_label, b, b_label in PAIRS:
        va, vb = encoder([crop(detector, frames, a, a_label), crop(detector, frames, b, b_label)])
        score = maxsim(va[None], vb[None])
        rows.append({"category": category, "truth": truth, "a": a, "b": b, "labels": [
            a_label.split("@")[0], b_label.split("@")[0]], "score": round(score, 4),
            "verdict": verdict(score)})
        print(f"{category:6} {truth:9} {rows[-1]['verdict']:9} {score:.3f}  {a} | {b}")
    counts = {}
    for category in ("views", "class", "kinds"):
        mine = [r for r in rows if r["category"] == category]
        counts[category] = {v: sum(r["verdict"] == v for r in mine)
                            for v in ("same", "unsure", "different")} | {"pairs": len(mine)}
        counts[category]["scores"] = [min(r["score"] for r in mine), max(r["score"] for r in mine)]
    result = {
        "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
                          for n in ("bench/same_pairs.py", "robot/memory.py", "robot/things.py")},
        "model_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (DETECTOR, ENCODER)},
        "machine": {"label": "E", "hostname": platform.node(), "platform": platform.platform()},
        "versions": {"python": platform.python_version(), "onnxruntime": ort.__version__,
                     "numpy": np.__version__, "opencv": cv2.__version__},
        "command": shlex.join([sys.executable, *sys.argv]),
        "limits": {"same": MATCH, "guess_band": BAND, "crops_per_side": 1},
        "pairs": len(rows), "counts": counts,
        "false_same": sum(r["truth"] == "different" and r["verdict"] == "same" for r in rows),
        "false_different": sum(r["truth"] == "same" and r["verdict"] == "different"
                               for r in rows),
        "unsure_same": sum(r["truth"] == "same" and r["verdict"] == "unsure" for r in rows),
        "unsure_different": sum(r["truth"] == "different" and r["verdict"] == "unsure"
                                for r in rows),
        "rows": rows}
    target = ROOT / f"bench/results/2026-10-12-same-pairs-{run}.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(target)
    print(json.dumps({k: v for k, v in result.items() if k in (
        "counts", "false_same", "false_different", "unsure_same", "unsure_different")}, indent=2))


if __name__ == "__main__":
    main()
