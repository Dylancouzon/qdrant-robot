#!/usr/bin/env python3
"""Detector and tracker stability on recorded camera clips, paired on the same frames at the
robot's 15 fps cadence. `run` caches one model's raw detections (GPU box); `score` replays caches
through robot.detect.Tracker with overridden constants and measures how steady the tracks are.

    python -m bench.detect_stability run MODEL.onnx H W CLIP OUT.jsonl [SOURCE_FPS [PRE]]
                                          PRE: blur3, avg2, tdn[T], tdnh[T]
    python -m bench.detect_stability time MODEL.onnx H W CLIP     GPU ms per frame (ORT CUDA)
    python -m bench.detect_stability cluster CACHE.jsonl...        persistent-object candidates
    python -m bench.detect_stability score GT.json CACHE.jsonl [NAME=VALUE ...]
    python -m bench.detect_stability sweep SPEC.json OUT.json      every arm on every clip
    python -m bench.detect_stability selftest
"""

import json
import statistics as st
import sys
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path

import numpy as np

from robot import detect as D
from robot.config import DETECT_LOW

FPS = 15
FLOOR = 0.05  # cached detections keep scores down to here; score replays them at LOW
SHOWN_IOU = 0.5  # a track covers a persistent object when its box overlaps this much
# robot/focus.py ignores a track whose current detection scores under DETECT_LOW, so a frame
# matched below it counts as a miss here, whatever the tracker LOW is. Constant GATE changes that
# floor; MEAN also keeps a frame at MEAN_FLOOR or more when the track's mean score reaches MEAN.
MEAN_FLOOR = 0.02
BRIDGE = 3  # frames (200 ms at 15 fps) the page keeps drawing a box after its last match (D159)
CLUSTER_IOU, CLUSTER_CONF, CLUSTER_COVER = 0.5, 0.25, 0.5
SWEEP = {
    "CONTAIN",
    "GATE",
    "MEAN",
    "LOW",
    "HIGH",
    "OBJECT_CONFIDENCE",
    "MATCH_IOU",
    "CONFIRM",
    "MAX_MISSED",
    "SAME",
    "LOST",
    "MERGE",
}


def read_frames(clip: Path, source_fps: float = 0):
    """(time, upright BGR frame) at 15 fps; the camera is mounted upside down (robot/camera.py)."""
    import cv2

    cap = cv2.VideoCapture(str(clip))
    source_fps = source_fps or cap.get(cv2.CAP_PROP_FPS)
    step, k = max(1, round(source_fps / FPS)), 0
    while cap.grab():
        k += 1
        if (k - 1) % step == 0:
            yield (k - 1) / source_fps, cv2.rotate(cap.retrieve()[1], cv2.ROTATE_180)


def run(
    model: Path, size: tuple[int, int], clip: Path, out: Path, source_fps: float, pre: str = ""
) -> None:
    """Cache one model's detections; `pre` filters each frame first: blur3 (3x3 Gaussian against
    sensor grain), avg2 (mean of this and the previous frame), or tdn (avg2 only where the blurred
    gray change from the previous output is under T, default 20, so moving things stay sharp);
    tdnh[T] does tdn on the frame resized to 640 wide, which the detector would do anyway."""
    import cv2

    D.INPUT, D.LOW = size, FLOOR
    detect, rows, t0, last = D.Detector(model), [], time.time(), None
    for t, frame in read_frames(clip, source_fps):
        width, grow = frame.shape[1], 1.0
        if pre.startswith("tdnh"):
            grow = width / 640
            frame = cv2.resize(frame, (640, round(frame.shape[0] / grow)))
        if pre == "blur3":
            frame = cv2.GaussianBlur(frame, (3, 3), 0)
        elif pre == "avg2":
            prev = frame if last is None else last
            frame, last = cv2.addWeighted(frame, 0.5, prev, 0.5, 0), frame
        elif pre.startswith("tdn"):  # tdn and tdnh
            prev = frame if last is None else last
            change = cv2.cvtColor(cv2.absdiff(frame, prev), cv2.COLOR_BGR2GRAY)
            still = cv2.blur(change, (5, 5)) < int(pre.removeprefix("tdn").removeprefix("h") or 20)
            last = np.where(still[..., None], cv2.addWeighted(frame, 0.5, prev, 0.5, 0), frame)
            frame = last
        rows.append(
            {
                "t": round(t, 4),
                "dets": [
                    [d.label, round(d.conf, 4), *(round(v * grow) for v in d.box)]
                    for d in detect(frame)
                ],
            }
        )
    meta = {
        "meta": model.name,
        "clip": clip.name,
        "input": size,
        "width": width,
        "pre": pre,
        "frames": len(rows),
        "wall_s": round(time.time() - t0, 1),
    }
    out.write_text("".join(json.dumps(r) + "\n" for r in [meta, *rows]))
    print(meta)


def gpu_ms(model: Path, size: tuple[int, int], clip: Path, n: int = 300) -> dict:
    """Median and p95 ms of the model call alone (host to device, run, back), after warm-up."""
    D.INPUT = size
    detect = D.Detector(model)
    blob = D.letterbox(next(read_frames(clip))[1])[0]
    for _ in range(30):
        detect.run(blob)
    ms = []
    for _ in range(n):
        t = time.perf_counter()
        detect.run(blob)
        ms.append((time.perf_counter() - t) * 1e3)
    return {
        "model": model.name,
        "input": size,
        "p50_ms": round(st.median(ms), 2),
        "p95_ms": round(float(np.percentile(ms, 95)), 2),
        "n": n,
    }


def load(cache: Path) -> tuple[dict, list[tuple[float, list[D.Detection]]]]:
    rows = [json.loads(line) for line in cache.read_text().splitlines()]
    return rows[0], [
        (r["t"], [D.Detection(d[0], d[1], tuple(d[2:])) for d in r["dets"]]) for r in rows[1:]
    ]


def cluster(caches: list[Path]) -> list[dict]:
    """Boxes seen in at least CLUSTER_COVER of the frames of some cache: the objects that stay
    in view the whole clip, found by greedy IoU clustering of detections of every cache."""
    groups: list[list] = []  # [median box, labels, {cache: frames}]
    for ci, cache in enumerate(caches):
        for fi, (_, dets) in enumerate(load(cache)[1]):
            for d in (d for d in D.distinct(dets) if d.conf >= CLUSTER_CONF):
                score_, g = max(
                    (
                        (D.iou(np.array([g[0]]), np.array([d.box]))[0, 0], i)
                        for i, g in enumerate(groups)
                    ),
                    default=(0, None),
                )
                if score_ < CLUSTER_IOU:
                    groups.append([np.array(d.box, float), Counter(), {}])
                    g = len(groups) - 1
                g = groups[g]
                g[1][d.label] += 1
                g[2].setdefault(ci, set()).add(fi)
                g[0] = 0.9 * g[0] + 0.1 * np.array(d.box)
    counts = [len(load(c)[1]) for c in caches]
    return [
        {
            "box": [round(float(v)) for v in g[0]],
            "labels": dict(g[1].most_common(3)),
            "cover": [round(len(g[2].get(i, ())) / n, 2) for i, n in enumerate(counts)],
        }
        for g in groups
        if max(len(g[2].get(i, ())) / n for i, n in enumerate(counts)) >= CLUSTER_COVER
    ]


def contained(a: np.ndarray, b: np.ndarray, floor: float) -> np.ndarray:
    """Pairwise: just above D.MATCH_IOU where the smaller box lies `floor` inside the other."""
    lt, rb = np.maximum(a[:, None, :2], b[None, :, :2]), np.minimum(a[:, None, 2:], b[None, :, 2:])
    area = lambda x: np.prod(x[:, 2:] - x[:, :2], axis=1)  # noqa: E731
    inter = np.prod(np.clip(rb - lt, 0, None), axis=2)
    small = np.minimum(area(a)[:, None], area(b)[None, :])
    return np.where(inter / (small + 1e-9) >= floor, D.MATCH_IOU + 1e-3, 0.0)


class ContainTracker(D.Tracker):
    """Tracker that also matches a detection that lies inside a track's box, or the reverse (the
    box grows to the hand around a held object): an arm to test, not robot behavior."""

    floor = 0.8

    @staticmethod
    def _match(tracks, dets):
        real = D.iou
        D.iou = lambda a, b: np.maximum(real(a, b), contained(a, b, ContainTracker.floor))
        try:
            return D.Tracker._match(tracks, dets)
        finally:
            D.iou = real


def replay(frames, width: int, consts: dict) -> tuple[list[list], list]:
    """Per frame, the confirmed tracks the frame matched (id, majority label, detected label,
    score, box, mean score over the track's life), and every sighting the tracker emits, under
    overridden module constants."""
    consts = dict(consts)
    ContainTracker.floor = consts.pop("CONTAIN", 0)
    old = {k: getattr(D, k) for k in consts}
    for k, v in consts.items():
        setattr(D, k, v)
    try:
        tracker = (ContainTracker if ContainTracker.floor else D.Tracker)()
        shown, sightings = [], []
        for t, dets in frames:
            sightings += tracker.update([d for d in dets if d.conf >= D.LOW], width, t)
            shown.append(
                [
                    (k.id, k.label, k.det.label, k.det.conf, k.det.box, k.votes[k.label] / k.hits)
                    for k in tracker.tracks
                    if k.missed == 0 and k.reported
                ]
            )
        return shown, sightings
    finally:
        for k, v in old.items():
            setattr(D, k, v)


def object_stats(shown: list[list], box: list[int], scale: float) -> dict:
    """How steadily the tracks covered one persistent object (box in frame pixels)."""
    ref, hits = np.array([box]), []
    for frame in shown:
        best = max(
            ((D.iou(ref, np.array([m[4]]))[0, 0], m) for m in frame),
            default=(0, None),
            key=lambda x: x[0],
        )
        hits.append(best[1] if best[0] >= SHOWN_IOU else None)
    got = [h for h in hits if h]
    centers = np.array([[(h[4][0] + h[4][2]) / 2, (h[4][1] + h[4][3]) / 2] for h in got]) * scale
    seen = [any(hits[max(0, k - BRIDGE) : k + 1]) for k in range(len(hits))]
    flips = lambda i: sum(a[i] != b[i] for a, b in pairwise(got))  # noqa: E731
    return {
        "matched": round(len(got) / len(hits), 3),
        "visible": round(sum(seen) / len(seen), 3),
        "blinks": sum(1 for a, b in pairwise(seen) if a and not b),
        "dropouts": sum(1 for a, b in pairwise(hits) if a and not b),
        "tracks": len({h[0] for h in got}),
        "label_flips": flips(1),
        "raw_label_flips": flips(2),
        "jitter_px": round(
            float(np.sqrt(((centers - np.median(centers, 0)) ** 2).sum(1).mean())), 2
        )
        if len(got) > 1
        else None,
        "conf_std": round(float(np.std([h[3] for h in got])), 3) if got else None,
    }


def held_reference(caches: list[Path]) -> list[dict]:
    """The held item per frame of the live clip, for each window of bench.focus_clip.HELD: the
    best box with a held label (score 0.3 or more) over every cache, or None. It exists only
    where some model sees the item, so it ranks arms on the same frames and finds no recall."""
    from bench.focus_clip import HELD

    pooled = [load(c)[1] for c in caches]
    out = []
    for start, end, labels in HELD:
        best = []
        for frames in zip(*pooled, strict=True):
            t = frames[0][0]
            got = [d for _, dets in frames for d in dets if d.label in labels and d.conf >= 0.3]
            best.append(max(got, key=lambda d: d.conf).box if got and start <= t < end else None)
        out.append({"window": [start, end], "boxes": best})
    return out


def held_stats(shown: list[list], ref: dict) -> dict:
    """Coverage of the held item by confirmed tracks: frames covered, id switches between
    consecutive covered frames, distinct ids, cover-to-gap transitions, and the frames from the
    first sight of the item to its first covering track (a confirmation delay)."""
    ids = []
    for frame, box in zip(shown, ref["boxes"], strict=True):
        if box is None:
            continue
        best = max(
            ((D.iou(np.array([box]), np.array([m[4]]))[0, 0], m[0]) for m in frame),
            default=(0, None),
        )
        ids.append(best[1] if best[0] >= SHOWN_IOU else None)
    got = [i for i in ids if i is not None]
    return {
        "frames": len(ids),
        "covered": round(len(got) / max(1, len(ids)), 3),
        "id_switches": sum(a != b for a, b in pairwise(got)),
        "ids": len(set(got)),
        "dropouts": sum(1 for a, b in pairwise(ids) if a is not None and b is None),
        "first_cover": next((k for k, i in enumerate(ids) if i is not None), None),
    }


def mic_stats(frames, shown: list[list], box: list[int], low: float, high: float) -> dict:
    """The taught microphone, frame by frame: matched by a displayed track, its longest unmatched
    run, the detector's best score on it, and for each miss whether the detector gave no box at
    all, a box under `low`, or a box the tracker failed to carry (a detector or tracker miss)."""
    ref = np.array([box])
    on = lambda b: D.iou(ref, np.array([b]))[0, 0] >= SHOWN_IOU  # noqa: E731
    conf = [max((d.conf for d in dets if on(d.box)), default=0.0) for _, dets in frames]
    hit = [any(on(m[4]) for m in f) for f in shown]
    miss, run, longest = Counter(), 0, 0
    for c, h in zip(conf, hit, strict=True):
        run = 0 if h else run + 1
        longest = max(longest, run)
        if not h:
            miss[
                "detector: no box"
                if c == 0
                else "detector: under LOW"
                if c < low
                else "tracker: box not matched"
            ] += 1
    seen = [c for c in conf if c > 0]
    return {
        "frames": len(conf),
        "matched": round(sum(hit) / len(hit), 3),
        "longest_gap": longest,
        "misses": dict(miss),
        "box_frames": len(seen),
        "conf_p10_p50_p90": [round(float(np.percentile(seen, q)), 3) for q in (10, 50, 90)]
        if seen
        else None,
        "between_low_high": round(float(np.mean([low <= c < high for c in conf])), 3),
    }


def score(gt: list[dict], cache: Path, consts: dict, held: list[dict] | None = None) -> dict:
    meta, frames = load(cache)
    gate, mean = consts.get("GATE", DETECT_LOW), consts.get("MEAN", 9)
    shown, sightings = replay(
        frames, meta["width"], {k: v for k, v in consts.items() if k not in ("GATE", "MEAN")}
    )
    shown = [[m for m in f if m[3] >= gate or (m[3] >= MEAN_FLOOR and m[5] >= mean)] for f in shown]
    per = [object_stats(shown, o["box"], 1280 / meta["width"]) for o in gt]
    covered = [o["box"] for o in gt]
    ids = {m[0] for f in shown for m in f}
    other = {
        m[0]
        for f in shown
        for m in f
        if m[1] != "person" and D.iou(np.array([m[4]]), np.array(covered)).max() < SHOWN_IOU
    }
    mean = lambda k: round(float(np.mean([p[k] for p in per if p[k] is not None])), 3)  # noqa: E731
    return {
        "model": meta["meta"],
        "consts": consts,
        "objects": len(gt),
        "matched": mean("matched"),
        "visible": mean("visible"),
        "blinks": mean("blinks"),
        "dropouts": mean("dropouts"),
        "tracks": mean("tracks"),
        "label_flips": mean("label_flips"),
        "raw_label_flips": mean("raw_label_flips"),
        "jitter_px": mean("jitter_px"),
        "conf_std": mean("conf_std"),
        "other_tracks": len(other),
        "all_tracks": len(ids),
        "sightings": len(sightings),
        "per_object": per,
        **(
            {
                "mic": mic_stats(
                    frames,
                    shown,
                    gt[i]["box"],
                    consts.get("LOW", D.LOW),
                    consts.get("HIGH", D.HIGH),
                )
                | {"tracks": per[i]["tracks"]}
            }
            if (i := next((i for i, o in enumerate(gt) if o["name"] == "microphone"), None))
            is not None
            else {}
        ),
        **({"held": [held_stats(shown, r) for r in held]} if held else {}),
    }


def sweep(spec: dict) -> list[dict]:
    """spec: {"cache_dir", "gt": {clip: GT file}, "ref_models": [...], "arms": [{"name", "model",
    "consts"}]}. One row per arm and clip; the live clip also gets the held-item rows."""
    root, rows = Path(spec["cache_dir"]), []
    held = held_reference([root / f"live-{m}.jsonl" for m in spec["ref_models"]])
    for arm in spec["arms"]:
        for clip, gt in spec["gt"].items():
            r = score(
                json.loads(Path(gt).read_text()),
                root / f"{clip}-{arm['model']}.jsonl",
                arm.get("consts", {}),
                held if clip == "live" else None,
            )
            rows.append({"arm": arm["name"], "clip": clip} | r)
    return rows


def _selftest() -> None:
    box, dets = (100, 100, 200, 200), []
    for k in range(30):  # one object, missing for 4 frames in the middle
        dets.append((k / 15, [] if 10 <= k < 14 else [D.Detection("cup", 0.5, box)]))
    shown, _ = replay(dets, 1280, {})
    stats = object_stats(shown, list(box), 1.0)
    assert stats["tracks"] == 1 and stats["dropouts"] == 1, stats  # CONFIRM=3 hides frames 0-1
    assert stats["matched"] == round((30 - 2 - 4) / 30, 3), stats
    assert stats["blinks"] == 1 and stats["visible"] == round((30 - 2 - 1) / 30, 3), stats  # 4 > 3
    shown, _ = replay(dets, 1280, {"CONFIRM": 1})
    assert object_stats(shown, list(box), 1.0)["matched"] == round(26 / 30, 3)
    assert D.CONFIRM == 3, "replay restores the constants"
    print("selftest ok")


def main(argv: list[str]) -> None:
    cmd, args = argv[0], argv[1:]
    if cmd == "selftest":
        _selftest()
    elif cmd == "run":
        run(
            Path(args[0]),
            (int(args[1]), int(args[2])),
            Path(args[3]),
            Path(args[4]),
            float(args[5]) if len(args) > 5 else 0,
            args[6] if len(args) > 6 else "",
        )
    elif cmd == "time":
        print(json.dumps(gpu_ms(Path(args[0]), (int(args[1]), int(args[2])), Path(args[3]))))
    elif cmd == "cluster":
        print(json.dumps(cluster([Path(a) for a in args]), indent=0))
    elif cmd == "score":
        consts = {k: float(v) if "." in v else int(v) for k, v in (a.split("=") for a in args[2:])}
        assert set(consts) <= SWEEP, consts
        print(json.dumps(score(json.loads(Path(args[0]).read_text()), Path(args[1]), consts)))
    elif cmd == "sweep":
        Path(args[1]).write_text(json.dumps(sweep(json.loads(Path(args[0]).read_text())), indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
