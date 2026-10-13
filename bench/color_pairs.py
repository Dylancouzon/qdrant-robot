"""Measure a CIELAB color cue for the same-object veto on the viewpoint set and the dev pairs.

Descriptor: mean (or median) Lab color of the middle half of a crop; two crop sets differ by the
Euclidean distance (Delta E 76) between their mean descriptors. Same-instance pairs set the
threshold; lookalike pairs and the dev pairs only check it.

    ROBOT_SHARED=. .venv/bin/python bench/color_pairs.py
"""

import hashlib
import json
import platform
import shlex
import subprocess
import sys
import time

import cv2
import numpy as np

import embed_arms  # also puts the repo root on sys.path through same_pairs below
import same_pairs
from robot.things import SHOTS, Crops

ROOT = same_pairs.ROOT
LEVELS = (50, 90, 95, 99, 100)
STATS = ("mean", "median")


def lab(crop, stat="mean"):
    """Mean or median Lab color (L 0-100, a and b about -127..127) of the middle half of a crop."""
    h, w = crop.shape[:2]
    middle = crop[h // 4 : h - h // 4, w // 4 : w - w // 4]
    pixels = cv2.cvtColor(middle.astype(np.float32) / 255, cv2.COLOR_BGR2Lab).reshape(-1, 3)
    return pixels.mean(0) if stat == "mean" else np.median(pixels, axis=0)


def distance(a, b, lightness_only=False):
    """Delta E 76 between two mean descriptors, or the lightness gap alone."""
    return float(abs(a[0] - b[0])) if lightness_only else float(np.linalg.norm(a - b))


def _selftest():
    white = np.full((40, 40, 3), 255, np.uint8)
    black = np.zeros((40, 40, 3), np.uint8)
    assert np.allclose(lab(white), [100, 0, 0], atol=0.5) and np.allclose(lab(black), 0, atol=0.5)
    assert distance(lab(white), lab(black)) > 99 and distance(lab(white), lab(white)) == 0
    # a hand-sized border of another color around the middle half must not move the descriptor
    framed = white.copy()
    framed[:10], framed[-10:], framed[:, :10], framed[:, -10:] = 0, 0, 0, 0
    assert np.allclose(lab(framed), lab(white))


def windows(ids, most=None):
    """Non-overlapping runs of SHOTS crop ids, at most `most`, spread evenly over the clip."""
    runs = [ids[i : i + SHOTS] for i in range(0, len(ids) - SHOTS + 1, SHOTS)]
    if most is None or len(runs) <= most:
        return runs
    return [runs[i] for i in np.linspace(0, len(runs) - 1, most, dtype=int)]


def stats(values):
    values = np.asarray(values, float)
    return {f"p{p}": round(float(np.percentile(values, p)), 3) for p in LEVELS} | {"n": len(values)}


class Viewpoint:
    """The recorded viewpoint crops with their colors and DINOv3 vectors."""

    def __init__(self):
        data = embed_arms.pickle.loads((embed_arms.EMBED / "viewpoint.pkl").read_bytes())
        self.instances, contexts = data["instances"], data["contexts"]
        path = embed_arms.EMBED / "emb/dinov3-s_224_pad_0.0_none_clean.npz"
        self.dinov3 = np.load(path)["viewpoint_cat"]
        a = self.instances
        used = sorted(
            {i for x in a for i in x["galleries"]["box"]}
            | {r["vectors"]["box"] for x in a for r in x["records"] if r["vectors"]}
            | {g["vectors"]["box"] for x in a for g in x["ground_truth"] if g["vectors"]}
        )
        self.crops = {}
        for i in used:
            image, (x1, y1, x2, y2) = embed_arms.decode([contexts[i]])[0]
            self.crops[int(i)] = image[y1:y2, x1:x2]
        self.colors = {s: {i: lab(c, s) for i, c in self.crops.items()} for s in STATS}

    def mean_color(self, ids, s):
        return np.mean([self.colors[s][int(i)] for i in ids], axis=0)

    def maxsim(self, a, b):  # the robot's score: each crop's best match, averaged
        return float((self.dinov3[a] @ self.dinov3[b].T).max(axis=1).mean())


def timing(crops):
    """Per-crop descriptor cost for each statistic."""
    out = {}
    for s in STATS:
        ms = []
        for c in crops.values():
            t = time.perf_counter()
            lab(c, s)
            ms.append((time.perf_counter() - t) * 1000)
        out[s] = {
            "p50_ms": round(float(np.median(ms)), 3),
            "p99_ms": round(float(np.percentile(ms, 99)), 3),
            "max_ms": round(max(ms), 3),
            "crops": len(ms),
        }
    sizes = np.array([c.shape[:2] for c in crops.values()])
    out["median_crop_hw"] = np.median(sizes, axis=0).tolist()
    return out


def same_instance(v):
    """Taught shots against later crops (second half of the clip), per window and per crop.

    Returns distances by (statistic, mode), each triple window's MaxSim, and per-instance rows."""
    same = {(s, mode): [] for s in STATS for mode in ("triple", "single", "triple_L", "single_L")}
    same_ms, rows = [], []
    for a in v.instances:
        taught = [int(i) for i in a["galleries"]["box"]]
        later = [
            r["vectors"]["box"]
            for r in a["records"]
            if r["frame"] > a["teaching_half_end_frame"] and r["vectors"] is not None
        ]
        runs = windows(later)
        same_ms += [v.maxsim(taught, w) for w in runs]
        row = {
            "instance": a["name"],
            "taught_shots": len(taught),
            "later_crops": len(later),
            "triples": len(runs),
        }
        for s in STATS:
            t = v.mean_color(taught, s)
            triples = [distance(t, v.mean_color(w, s)) for w in runs]
            singles = [distance(t, v.colors[s][i]) for i in later]
            same[s, "triple"] += triples
            same[s, "single"] += singles
            same[s, "triple_L"] += [distance(t, v.mean_color(w, s), True) for w in runs]
            same[s, "single_L"] += [distance(t, v.colors[s][i], True) for i in later]
            row[s] = {
                "triple_max": round(max(triples), 2),
                "triple_p50": round(float(np.median(triples)), 2),
                "single_max": round(max(singles), 2),
            }
        rows.append(row)
    return same, same_ms, rows


def lookalikes(v):
    """Taught shots against crops of every other instance of the kind.

    Returns distances by (statistic, "E" or "L"), each window's MaxSim, and per-pair rows."""
    look = {(s, m): [] for s in STATS for m in ("L", "E")}
    look_ms, rows = [], []
    for a in v.instances:
        taught = [int(i) for i in a["galleries"]["box"]]
        for b in v.instances:
            if b is a or b["kind"] != a["kind"]:
                continue
            runs = windows([g["vectors"]["box"] for g in b["ground_truth"] if g["vectors"]], 6)
            if not runs:
                continue
            scores = [v.maxsim(taught, w) for w in runs]
            look_ms += scores
            row = {
                "gallery": a["name"],
                "other": b["name"],
                "kind": a["kind"],
                "windows": len(runs),
                "maxsim_max": round(max(scores), 4),
            }
            for s in STATS:
                es = [distance(v.mean_color(taught, s), v.mean_color(w, s)) for w in runs]
                ls = [distance(v.mean_color(taught, s), v.mean_color(w, s), True) for w in runs]
                look[s, "E"] += es
                look[s, "L"] += ls
                row[s] = {
                    "dE_min": round(min(es), 2),
                    "dE_p50": round(float(np.median(es)), 2),
                    "dL_min": round(min(ls), 2),
                    "dL_p50": round(float(np.median(ls)), 2),
                }
            rows.append(row)
    return look, np.array(look_ms), rows


def thresholds(same, look, pair_rows):
    """For each descriptor, the Delta E that keeps 95, 99, and 100 percent of same windows."""
    out = {}
    for s in STATS:
        for mode, lightness in (("triple", False), ("triple_L", True), ("single", False)):
            values = np.array(same[s, mode])
            dist = np.array(look[s, "L" if lightness else "E"])
            pick = "dL" if lightness else "dE"
            out[f"{s}_{mode}"] = {}
            for keep in (95, 99, 100):
                t = float(np.percentile(values, keep))
                out[f"{s}_{mode}"][f"keep{keep}"] = {
                    "threshold": round(t, 2),
                    "same_kept": int((values <= t).sum()),
                    "same_total": len(values),
                    "lookalike_windows_vetoed": int((dist > t).sum()),
                    "lookalike_windows": len(dist),
                    "ordered_pairs_all_windows_vetoed": sum(
                        r[s][f"{pick}_min"] > t for r in pair_rows
                    ),
                    "ordered_pairs_median_vetoed": sum(r[s][f"{pick}_p50"] > t for r in pair_rows),
                    "ordered_pairs": len(pair_rows),
                }
    return out


def conditional(same, same_ms, look, look_ms):
    """The veto only runs when MaxSim passes `same`, so set its threshold on those windows."""
    passing = np.array(same_ms) >= same_pairs.MATCH
    out = {
        "same_windows_passing_maxsim": int(passing.sum()),
        "same_windows": len(passing),
        "maxsim_threshold": same_pairs.MATCH,
    }
    for s in STATS:
        for mode, key in (("triple", "E"), ("triple_L", "L")):
            values = np.array(same[s, mode])[passing]
            dist = np.array(look[s, key])
            entry = {"dE_or_dL": stats(values)}
            for keep in (95, 99, 100):
                t = float(np.percentile(values, keep))
                entry[f"keep{keep}"] = {"threshold": round(t, 2)} | {
                    f"lookalike_windows_maxsim>={m}_vetoed": [
                        int((dist[look_ms >= m] > t).sum()),
                        int((look_ms >= m).sum()),
                    ]
                    for m in (0.6, 0.7, 0.8)
                }
            out[f"{s}_{mode}"] = entry
    return out


def dev_pairs():
    """One crop per side, as bench/same_pairs.py; a check only."""
    detector, encoder, frames = same_pairs.Detector(), Crops(), {}
    rows = []
    for category, truth, a, a_label, b, b_label in same_pairs.PAIRS:
        ca = same_pairs.crop(detector, frames, a, a_label)
        cb = same_pairs.crop(detector, frames, b, b_label)
        va, vb = encoder([ca, cb])
        row = {
            "category": category,
            "truth": truth,
            "a": a,
            "b": b,
            "maxsim": round(float(va @ vb), 4),
        }
        for s in STATS:
            row[s] = {
                "dE": round(distance(lab(ca, s), lab(cb, s)), 2),
                "dL": round(distance(lab(ca, s), lab(cb, s), True), 2),
            }
        rows.append(row)
    return rows


def record(v, **parts):
    """The result file: provenance, then every measured part."""
    return {
        "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
            for n in ("bench/color_pairs.py", "bench/same_pairs.py", "bench/embed_arms.py")
        },
        "machine": {"label": "E", "hostname": platform.node(), "platform": platform.platform()},
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
        },
        "command": shlex.join([sys.executable, *sys.argv]),
        "descriptor": (
            "Lab of the middle half (25% trimmed per side) of the box crop; "
            "float32 BGR/255 through cv2.COLOR_BGR2Lab; set color is the mean of its crops' colors"
        ),
        "data": {
            "source": "build/detect-quality/embed/viewpoint.pkl "
            "(bench/gallery.py collect output, box crops)",
            "instances": len(v.instances),
            "crops_used": len(v.crops),
            "shots_per_set": SHOTS,
            "same_split": "taught shots (instance galleries) vs later crops, frame > "
            "teaching_half_end_frame; triples are non-overlapping runs of 3",
            "lookalike_split": "taught shots vs up to 6 triples of every other instance of the "
            "kind (bench/embed_arms.py same_pairs windows)",
        },
        **parts,
    }


def main():
    _selftest()
    v = Viewpoint()
    same, same_ms, same_rows = same_instance(v)
    look, look_ms, pair_rows = lookalikes(v)
    limits = thresholds(same, look, pair_rows)
    after_maxsim = conditional(same, same_ms, look, look_ms)
    dev = dev_pairs()
    result = record(
        v,
        timing_ms_per_crop=timing(v.crops),
        same_instance={
            f"{s}_{m}": stats(same[s, m])
            for s in STATS
            for m in ("triple", "single", "triple_L", "single_L")
        },
        same_instance_per_instance=same_rows,
        lookalike={f"{s}_{m}": stats(look[s, m]) for s in STATS for m in ("E", "L")},
        thresholds=limits,
        conditional_on_maxsim_pass=after_maxsim,
        lookalike_pairs=pair_rows,
        # veto value where DINOv3 is dangerous: lookalike pairs scoring near the `same` setting
        **{
            "lookalike_pairs_maxsim_at_least_0.80": [
                r for r in pair_rows if r["maxsim_max"] >= 0.80
            ]
        },
        dev_pairs=dev,
    )
    for category in ("views", "class", "kinds"):
        mine = [r["mean"]["dE"] for r in dev if r["category"] == category]
        print(f"dev {category:6} dE {min(mine):.1f}..{max(mine):.1f}")
    print("same triple (mean):", stats(same["mean", "triple"]))
    print("recommended mean-triple 99% threshold:", limits["mean_triple"]["keep99"]["threshold"])
    for key in ("mean_triple", "median_triple", "mean_triple_L", "mean_single"):
        print(key, json.dumps(limits[key]))
    target = ROOT / "bench/results/2026-10-12-color-pairs.json"
    target.write_text(json.dumps(result, indent=1) + "\n")
    print(target)


if __name__ == "__main__":
    main()
