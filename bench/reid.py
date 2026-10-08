#!/usr/bin/env python3
"""Named-object re-identification bake-off (M2.2b): can a crop descriptor tell "my phone" from
another phone? Views: COCO phones and teddy bears pasted into scenes at other sizes, sides, and
light (the fixtures' kind of change), and Objectron cups and cameras filmed from other angles
(real viewpoint change). Every crop is our detector's box, as at runtime. Arms: an HSV
histogram (no model), DINOv2-small, SigLIP 2 base. Each instance enrolls three crops; a query
scores MaxSim against every enrolled instance of any class (the robot matches across detector
labels). The threshold is the highest other-instance score on half the instances (zero false
matches there), tested on the other half.

    .venv/bin/python bench/reid.py COCO_ANNOTATIONS_DIR MODELS_DIR
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "eval")]
from make_scenes import CACHE, SCENES, background, paste  # noqa: E402

from robot.detect import Detector, iou  # noqa: E402

PER_CLASS = 24  # COCO instances per class
VIDEOS = 8      # Objectron videos per class
CLASSES = {"cell phone": (77, 260), "teddy bear": (88, 300)}  # COCO id, enrolled height px
REAL = {"cup": {"cup", "mug"}, "camera": {"camera"}}
ENROLL_BG = "live/closet-night.jpg"  # the dev scene
# (background, region, share of the enrolled height, light gain): other rooms, sides, sizes.
QUERIES = [(552883, "left", 0.7, 1.25), (58029, "right", 0.8, 0.75),
           (ENROLL_BG, "right", 0.65, 1.0)]
OBJECTRON = "https://storage.googleapis.com/objectron"


def fetch(url: str, path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, path)
    return path


def coco_instances(ann_dir: Path) -> dict[str, list[dict]]:
    """Per class, PER_CLASS whole, unoccluded-looking instances from train and val, never one
    that held-out or the M2.2b probes show (their images too)."""
    banned = {a for name in ("heldout", "probes") for _, objs, _ in SCENES[name].values()
              for a, _, _ in objs}
    found: dict[str, list[dict]] = {c: [] for c in CLASSES}
    for split in ("val2017", "train2017"):
        d = json.loads((ann_dir / f"instances_{split}.json").read_text())
        imgs = {i["id"]: i for i in d["images"]}
        banned_imgs = {a["image_id"] for a in d["annotations"] if a["id"] in banned}
        for name, (cat, _) in CLASSES.items():
            for a in sorted(d["annotations"], key=lambda a: a["id"]):
                w, h = a["bbox"][2:]
                if (a["category_id"] == cat and not a["iscrowd"] and h >= 80 and w >= 40
                        and a["area"] > 0.5 * w * h and a["id"] not in banned
                        and a["image_id"] not in banned_imgs
                        and imgs[a["image_id"]]["license"] in (4, 5, 7, 8)
                        and len(found[name]) < PER_CLASS and isinstance(a["segmentation"], list)):
                    fetch(f"http://images.cocodataset.org/{split}/{a['image_id']:012d}.jpg",
                          CACHE / f"{a['image_id']:012d}.jpg")
                    found[name].append(a)
    return found


def crop(detect: Detector, frame: np.ndarray, box: tuple[int, int, int, int] | None,
         labels: set[str] | None = None) -> np.ndarray | None:
    """The detector box that overlaps `box` most (IoU 0.3 or more), or the most confident one
    with one of `labels`; None when the detector misses."""
    dets = detect(frame)
    if box is not None:
        dets = [d for d in dets if iou(np.array([d.box]), np.array([box]))[0, 0] >= 0.3]
        dets.sort(key=lambda d: -iou(np.array([d.box]), np.array([box]))[0, 0])
    else:
        dets = sorted((d for d in dets if d.label in labels), key=lambda d: -d.conf)
    if not dets:
        return None
    x1, y1, x2, y2 = dets[0].box
    return frame[y1:y2, x1:x2]


def composed(ann: dict, bg: str | int, region: str, height: int, gain: float, detect: Detector
             ) -> np.ndarray | None:
    frame = background(bg, ROOT / "eval/dev")
    empty = frame.copy()
    paste(frame, ann, region, height)
    ys, xs = np.nonzero(np.abs(frame.astype(int) - empty).sum(2) > 30)
    frame = np.clip(frame * gain, 0, 255).astype(np.uint8)
    return crop(detect, frame, (xs.min(), ys.min(), xs.max(), ys.max())) if len(xs) else None


def coco_views(ann_dir: Path, detect: Detector) -> dict[str, list[tuple[list, list]]]:
    """class -> per instance (enroll crops, query crops)."""
    out = {}
    for name, anns in coco_instances(ann_dir).items():
        h = CLASSES[name][1]
        out[name] = [([composed(a, ENROLL_BG, "center", round(h * s), 1.0, detect)
                       for s in (1.0, 0.92, 1.08)],
                      [composed(a, bg, region, round(h * s), g, detect)
                       for bg, region, s, g in QUERIES]) for a in anns]
    return out


def objectron_views(detect: Detector) -> dict[str, list[tuple[list, list]]]:
    """class -> per video: three frames a third of a second apart at the start (a held object),
    and three from its second half (other viewpoints)."""
    out = {}
    for name, labels in REAL.items():
        cache = Path.home() / ".cache/objectron"
        index = fetch(f"{OBJECTRON}/v1/index/{name}_annotations_test", cache / f"{name}.index")
        out[name] = []
        for entry in index.read_text().split()[:VIDEOS]:
            video = fetch(f"{OBJECTRON}/videos/{entry}/video.MOV",
                          cache / entry.replace("/", "-") / "video.MOV")
            cap = cv2.VideoCapture(str(video))
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frames = []
            for k in (0, 10, 20, n // 2, 3 * n // 4, n - 5):
                cap.set(cv2.CAP_PROP_POS_FRAMES, k)
                frames.append(crop(detect, cap.read()[1], None, labels))
            out[name].append((frames[:3], frames[3:]))
    return out


def hsv(c: np.ndarray) -> np.ndarray:
    h = cv2.calcHist([cv2.cvtColor(c, cv2.COLOR_BGR2HSV)], [0, 1, 2], None, [8, 4, 4],
                     [0, 180, 0, 256, 0, 256]).ravel()
    return np.sqrt(h / h.sum())  # unit length: cosine is the Bhattacharyya coefficient


def onnx_arm(path: Path, mean: list, std: list, pool: str):
    """pool: "pooler" (SigLIP 2), "cls" (DINOv2's CLS token), or "cat" (DINOv2's CLS and mean
    patch token, each unit length, concatenated)."""
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    def embed(c: np.ndarray) -> np.ndarray:
        h, w = c.shape[:2]
        s = max(h, w)  # pad to a square so the object keeps its shape
        sq = cv2.copyMakeBorder(c, (s - h) // 2, s - h - (s - h) // 2, (s - w) // 2,
                                s - w - (s - w) // 2, cv2.BORDER_CONSTANT, value=(114,) * 3)
        x = cv2.resize(sq, (224, 224), interpolation=cv2.INTER_LINEAR)[..., ::-1] / 255.0
        x = ((x - mean) / std).astype(np.float32).transpose(2, 0, 1)[None]
        out = sess.run(None, {"pixel_values": x})
        if pool == "pooler":
            return out[1][0] / np.linalg.norm(out[1][0])
        t = out[0][0]
        cls = t[0] / np.linalg.norm(t[0])
        if pool == "cls":
            return cls
        patches = t[1:].mean(0)
        return np.concatenate([cls, patches / np.linalg.norm(patches)]) / np.sqrt(2)
    return embed


def score(views: dict[str, list[tuple[list, list]]], embed) -> dict[str, tuple]:
    """Per class: positive scores (own enrollment), same-class and other-class negative scores
    (every other instance's enrollment: the robot matches across detector labels), and rank-1
    hits over same-class pairs, by MaxSim over the enrolled crops."""
    vecs = [(c, np.array([embed(x) for x in e if x is not None]),
             [embed(x) for x in q if x is not None]) for c, v in views.items() for e, q in v]
    vecs = [(c, e, q) for c, e, q in vecs if len(e) and q]
    out = {c: ([], [], [], []) for c in views}
    for i, (c, _, q) in enumerate(vecs):
        pos, same, other, rank = out[c]
        for v in q:
            s = [float((e @ v).max()) for _, e, _ in vecs]
            pos.append(s[i])
            same += [s[j] for j, x in enumerate(vecs) if j != i and x[0] == c]
            other += [s[j] for j, x in enumerate(vecs) if x[0] != c]
            rank += [s[i] > s[j] for j, x in enumerate(vecs) if j != i and x[0] == c]
    return out


def main(ann_dir: Path, models: Path) -> None:
    detect = Detector(models / "yoloe-26n-booth-384x640.onnx")
    data = {**coco_views(ann_dir, detect), **objectron_views(detect)}
    arms = {"hsv": hsv,
            **{f"dinov2-small-{pool}": onnx_arm(models / "dinov2-small.onnx",
                                                [0.485, 0.456, 0.406], [0.229, 0.224, 0.225],
                                                pool) for pool in ("cls", "cat")},
            "siglip2-base": onnx_arm(models / "siglip2-base-patch16-224-ONNX.onnx",
                                     [0.5] * 3, [0.5] * 3, "pooler")}
    rows = []
    for arm, embed in arms.items():
        tune, held = (score({c: v[k::2] for c, v in data.items()}, embed) for k in (0, 1))
        t = max(x for _, same, other, _ in tune.values() for x in same + other) + 1e-6
        for c, (pos, same, other, rank) in held.items():
            rows.append({"arm": arm, "class": c, "threshold": round(t, 4),
                         "true_match": f"{sum(x >= t for x in pos)}/{len(pos)}",
                         "false_same_class": f"{sum(x >= t for x in same)}/{len(same)}",
                         "false_other_class": f"{sum(x >= t for x in other)}/{len(other)}",
                         "rank1_pairs": f"{sum(rank)}/{len(rank)}",
                         "pos_p10": round(float(np.percentile(pos, 10)), 3),
                         "neg_max": round(max(same + other), 3)})
            print(rows[-1], flush=True)
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=ROOT, capture_output=True).stdout
    misses = {c: sum(x is None for e, q in v for x in e + q) for c, v in data.items()}
    rows.append({"summary": "reid", "machine": platform.node(), "onnxruntime": ort.__version__,
                 "revision": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                            capture_output=True, text=True).stdout.strip(),
                 "diff_sha": hashlib.sha256(diff).hexdigest()[:12], "precision": "fp32 cpu",
                 "instances": {c: len(v) for c, v in data.items()}, "detector_misses": misses,
                 "models": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:16]
                            for f in sorted(models.glob("*.onnx"))},
                 "command": " ".join(sys.argv), "split": "threshold on even instances, "
                 "tested on odd; zero false matches on the even half, against every other "
                 "instance of any class"})
    out = ROOT / "bench/results" / f"{time.strftime('%Y-%m-%d')}-reid-{int(time.time())}.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("annotations", type=Path, help="folder with instances_{val,train}2017.json")
    p.add_argument("models", type=Path, help="folder with the detector and embedder ONNX files")
    a = p.parse_args()
    main(a.annotations, a.models)
