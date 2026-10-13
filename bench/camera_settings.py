#!/usr/bin/env python3
"""Camera capture bake-off on recorded static-scene clips: grain, detector stability, and
crop-vector stability under the robot's own Detector, Tracker, and DINOv2 crops. Clips are raw
MJPEG files from `v4l2-ctl --stream-to`. Append filters with `:`, joined by `+`: `linear`
resizes 1080p with INTER_LINEAR instead of INTER_AREA; `median3` (3-frame temporal median) or
`bilateral` denoises after resizing.

    python -m bench.camera_settings CLIP[:FILTER] ... [--out FILE]
        on the Jetson, via tools/jetson.py run
    python -m bench.camera_settings --selftest
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from robot.camera import ROTATE, SIZE
from robot.detect import HIGH, Detection, Detector, Tracker, distinct, iou
from robot.settings import DEFAULTS

FPS = 30  # the clips are recorded at 30 fps; the tracker sees every second frame, like the robot
LAGS = (30, 150, 450)  # frames: 1, 5, and 15 s
EMBED_EVERY = 3  # crop vectors for every third frame, so every lag pairs two embedded frames
OBJECT_IOU = 0.5  # a detection or track with this overlap is the same physical object
PRESENT = 0.5  # a reference object is detected in this share of the frames of at least one clip


def median3(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    return np.maximum(np.minimum(a, b), np.minimum(np.maximum(a, b), c))


class Clip:
    """Frames of one recording as the robot sees them: rotated, 1280x720, optionally denoised.
    `cost` sums the CPU seconds of each stage (all threads) while the frames are read."""

    def __init__(self, spec: str):
        path, _, filters = spec.partition(":")
        self.path, self.filters = Path(path), set(filters.split("+")) - {""}
        self.name = self.path.stem + (f":{filters}" if filters else "")
        self.cost: Counter = Counter()

    def frames(self):
        """Yield (native frame, pipeline frame) pairs."""
        cap, last = cv2.VideoCapture(str(self.path)), []
        while True:
            t = time.process_time()
            ok, native = cap.read()
            self.cost["decode"] += time.process_time() - t
            if not ok:
                return
            t = time.process_time()
            frame = cv2.rotate(native, ROTATE)
            if frame.shape[1] != SIZE[0]:
                frame = cv2.resize(
                    frame,
                    SIZE,
                    interpolation=(
                        cv2.INTER_LINEAR if "linear" in self.filters else cv2.INTER_AREA
                    ),
                )
            self.cost["rotate_resize"] += time.process_time() - t
            t = time.process_time()
            if "median3" in self.filters:
                last = (last + [frame])[-3:]
                out = median3(*last) if len(last) == 3 else None
            elif "bilateral" in self.filters:
                out = cv2.bilateralFilter(frame, 5, 25, 5)
            else:
                out = frame
            self.cost["filter"] += time.process_time() - t
            if out is not None:
                yield native, out


class Noise:
    """Per-pixel temporal grey std. `raw` includes exposure drift; `noise` removes each frame's
    mean first, so slow brightness changes and flicker do not count as grain."""

    def __init__(self):
        self.n, self.means, self.acc = 0, [], None

    def add(self, bgr: np.ndarray) -> None:
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float64)
        m = g.mean()
        self.means.append(m)
        if self.acc is None:
            self.acc = np.zeros((4, *g.shape))
        d = g - m
        self.acc += [g, g * g, d, d * d]
        self.n += 1

    def _std(self, s, q) -> float:
        return float(np.sqrt(np.maximum(q / self.n - (s / self.n) ** 2, 0)).mean())

    def result(self) -> dict:
        s, q, ds, dq = self.acc
        means = np.array(self.means)
        return {
            "brightness": round(float(means.mean()), 1),
            "noise": round(self._std(ds, dq), 3),
            "noise_raw": round(self._std(s, q), 3),
            "flicker_std": round(float(means.std()), 3),  # includes slow drift
            "flicker_hf": round(float(np.diff(means).std() / np.sqrt(2)), 3),
        }  # frame to frame


@dataclass
class Observed:
    """What the Detector and Tracker said about one clip."""

    name: str
    dets: list[list[Detection]]  # per frame, one detection per physical box
    views: list[dict]  # per tracker update (every second frame): track id -> (label, box)
    noise: dict
    noise_native: dict | None
    cost_ms: dict
    frames: int


def observe(clip: Clip, detect: Detector) -> Observed:
    noise, native_noise, tracker = Noise(), Noise(), Tracker()
    dets, views = [], []
    for i, (native, frame) in enumerate(clip.frames()):
        noise.add(frame)
        if native.shape[1] != SIZE[0]:
            native_noise.add(native)
        found = detect(frame)
        dets.append(distinct(found))
        if i % 2 == 0:
            tracker.update(found, SIZE[0], i / FPS)
            views.append(tracker.view())
    n = len(dets)
    return Observed(
        clip.name,
        dets,
        views,
        noise.result(),
        native_noise.result() if native_noise.n else None,
        {k: round(1000 * v / n, 2) for k, v in clip.cost.items()},
        n,
    )


@dataclass
class Reference:
    """A physical object of the static scene, found across every clip, so all arms score one set."""

    label: str
    box: np.ndarray  # median detected box
    seen: dict = field(default_factory=dict)  # clip name -> frames with a detection


def reference_objects(observed: list[Observed]) -> list[Reference]:
    """Cluster confident detections by overlap; keep clusters present in half a clip's frames."""
    pool = sorted(
        (
            (d, o.name, f)
            for o in observed
            for f, ds in enumerate(o.dets)
            for d in ds
            if d.conf >= HIGH
        ),
        key=lambda x: -x[0].conf,
    )
    seeds, members = np.zeros((0, 4)), []
    for d, name, f in pool:
        k = int(np.argmax(iou(seeds, np.array([d.box])).ravel())) if len(seeds) else -1
        if k >= 0 and iou(seeds[k : k + 1], np.array([d.box]))[0, 0] >= OBJECT_IOU:
            members[k].append((d, name, f))
        else:
            seeds = np.vstack([seeds, d.box])
            members.append([(d, name, f)])
    frames = {o.name: o.frames for o in observed}
    refs = []
    for group in members:
        seen = {n: len({f for _, m, f in group if m == n}) for n in frames}
        if max(seen[n] / frames[n] for n in frames) >= PRESENT:
            refs.append(
                Reference(
                    Counter(d.label for d, _, _ in group).most_common(1)[0][0],
                    np.median([d.box for d, _, _ in group], axis=0),
                    seen,
                )
            )
    return refs


def matched(ref: Reference, dets: list[list[Detection]]) -> list[tuple[int, Detection]]:
    """The best confident detection of the object in each frame that has one."""
    out = []
    for f, ds in enumerate(dets):
        near = [
            d
            for d in ds
            if d.conf >= HIGH and iou(ref.box[None], np.array([d.box]))[0, 0] >= OBJECT_IOU
        ]
        if near:
            out.append((f, max(near, key=lambda d: d.conf)))
    return out


def object_stats(ref: Reference, o: Observed) -> dict:
    hits = matched(ref, o.dets)
    if len(hits) < 2:
        return {
            "label": ref.label,
            "det_frac": round(len(hits) / o.frames, 3),
            "track_frac": 0.0,
            "longest_gap": o.frames,
            "track_ids": 0,
            "conf_std": None,
            "conf_pct": None,
            "jitter_px": None,
            "label_flips": None,
        }
    conf = np.array([d.conf for _, d in hits])
    frames = [-1] + [f for f, _ in hits] + [o.frames]
    boxes = np.array([d.box for _, d in hits], float)
    centers = np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2]
    labels = [d.label for _, d in hits]
    ids, tracked = set(), 0
    for view in o.views:
        on = [
            i for i, (_, b) in view.items() if iou(ref.box[None], np.array([b]))[0, 0] >= OBJECT_IOU
        ]
        ids.update(on)
        tracked += bool(on)
    return {
        "label": ref.label,
        "det_frac": round(len(hits) / o.frames, 3),
        "track_frac": round(tracked / len(o.views), 3),
        "track_ids": len(ids),
        "longest_gap": max(b - a - 1 for a, b in zip(frames, frames[1:], strict=False)),
        "conf_std": round(float(conf.std()), 3),
        "conf_pct": [round(float(x), 3) for x in np.percentile(conf, (5, 50, 95))],
        "jitter_px": round(float(np.sqrt(centers.var(axis=0).sum())), 2),
        "label_flips": sum(a != b for a, b in zip(labels, labels[1:], strict=False)),
    }


def crop_cosines(vectors: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
    """Cosine of each frame's crop vector to the crop LAG frames earlier, by lag."""
    return {
        lag: np.array([vectors[f] @ vectors[f - lag] for f in vectors if f - lag in vectors])
        for lag in LAGS
    }


def embed(crops, clip_spec: str, refs: list[Reference], o: Observed) -> list[dict[int, np.ndarray]]:
    """Crop vectors per reference object, computed as robot/things.py does, from matched boxes."""
    from robot.things import cut

    wanted = [{f: d.box for f, d in matched(r, o.dets) if f % EMBED_EVERY == 0} for r in refs]
    vectors, batch, keys = [{} for _ in refs], [], []

    def flush():
        if batch:
            for (i, f), v in zip(keys, crops(batch), strict=True):
                vectors[i][f] = v
        batch.clear()
        keys.clear()

    for f, (_, frame) in enumerate(Clip(clip_spec).frames()):
        for i, w in enumerate(wanted):
            if f in w:
                batch.append(cut(frame, w[f]))
                keys.append((i, f))
        if len(batch) >= 32:
            flush()
    flush()
    return vectors


def pooled(per_object: list[dict[int, np.ndarray]]) -> dict:
    match = DEFAULTS["match"]
    out = {}
    for lag in LAGS:
        cos = np.concatenate([crop_cosines(v)[lag] for v in per_object] or [np.zeros(0)])
        out[f"{lag // FPS}s"] = (
            {
                "pairs": len(cos),
                "mean": round(float(cos.mean()), 4),
                "p5": round(float(np.percentile(cos, 5)), 4),
                f"below_{match}": round(float((cos < match).mean()), 4),
            }
            if len(cos)
            else {"pairs": 0}
        )
    return out


def summary(stats: list[dict]) -> dict:
    def mean(key):
        vals = [s[key] for s in stats if s[key] is not None]
        return round(float(np.mean(vals)), 3) if vals else None

    return {
        "objects": len(stats),
        "det_frac_mean": mean("det_frac"),
        "det_frac_min": min(s["det_frac"] for s in stats),
        "track_frac_mean": mean("track_frac"),
        "track_frac_min": min(s["track_frac"] for s in stats),
        "conf_std": mean("conf_std"),
        "jitter_px": mean("jitter_px"),
        "track_ids": mean("track_ids"),
        "label_flips": mean("label_flips"),
    }


def revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("ROBOT_RELEASE", "unknown")


def _selftest() -> None:
    rng = np.random.default_rng(0)
    n = Noise()
    for _ in range(
        40
    ):  # grey 100 with sigma 5 per channel (3.35 in grey) and a 10-grey brightness drift
        n.add(
            np.clip(100 + rng.normal(0, 5, (48, 64, 3)) + rng.integers(-5, 6), 0, 255).astype(
                np.uint8
            )
        )
    r = n.result()
    assert 3 < r["noise"] < 3.8 and r["noise_raw"] > r["noise"], r
    assert np.array_equal(
        median3(*[np.full((2, 2), v, np.uint8) for v in (9, 1, 5)]), np.full((2, 2), 5)
    )
    boxes = [(100 + (f % 3), 100, 200 + (f % 3), 200) for f in range(10)]
    dets = [
        [Detection("cup" if f == 4 else "mug", 0.5, b), Detection("x", 0.3, (500, 500, 600, 600))]
        for f, b in enumerate(boxes)
    ]
    dets[2] = dets[3] = [dets[2][1]]  # the mug is missed in two frames
    obs = Observed("t", dets, [{1: ("mug", boxes[0])}] * 5, {}, None, {}, 10)
    refs = reference_objects([obs])
    assert len(refs) == 2, refs
    s = object_stats(next(r for r in refs if r.box[0] < 300), obs)
    assert s["det_frac"] == 0.8 and s["longest_gap"] == 2 and s["track_ids"] == 1, s
    assert s["label_flips"] == 2 and s["conf_pct"] == [0.5, 0.5, 0.5], s
    assert 0.5 < s["jitter_px"] < 1.5, s
    v = {f: np.array([1.0, 0.0]) for f in range(0, 600, EMBED_EVERY)}
    assert all(
        len(c) == len(v) - lag // EMBED_EVERY and (c == 1).all()
        for lag, c in crop_cosines(v).items()
    )
    print("selftest ok")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("clips", nargs="*")
    p.add_argument("--out", type=Path)
    p.add_argument(
        "--headline",
        default="microphone",
        help="label of the object whose stats get their own row (the one that blinks live)",
    )
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return _selftest()
    from robot.things import Crops

    detect, crops = Detector(), Crops()
    observed = [observe(Clip(spec), detect) for spec in a.clips]
    refs = reference_objects(observed)
    results = []
    for spec, o in zip(a.clips, observed, strict=True):
        stats = [object_stats(r, o) for r in refs]
        vectors = embed(crops, spec, refs, o)
        for st, v in zip(stats, vectors, strict=True):
            st["crop_cosine"] = pooled([v])
        results.append(
            {
                "clip": o.name,
                "frames": o.frames,
                **o.noise,
                "noise_native": o.noise_native,
                "cost_ms_per_frame": o.cost_ms,
                "headline": next(
                    st for st, r in zip(stats, refs, strict=True) if r.label == a.headline
                ),
                "detector": summary(stats),
                "crop_cosine": pooled(vectors),
                "objects": stats,
            }
        )
        print(json.dumps({k: v for k, v in results[-1].items() if k != "objects"}), flush=True)
    detect.close()
    record = {
        "revision": revision(),
        "machine": platform.node(),
        "command": " ".join(sys.argv),
        "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
        "match": DEFAULTS["match"],
        "reference_objects": [
            {"label": r.label, "box": r.box.tolist(), "frames_seen": r.seen} for r in refs
        ],
        "limits": {
            "fps": FPS,
            "lags_frames": LAGS,
            "embed_every": EMBED_EVERY,
            "object_iou": OBJECT_IOU,
            "present": PRESENT,
        },
        "versions": {"python": platform.python_version(), "opencv": cv2.__version__},
        "results": results,
    }
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()
