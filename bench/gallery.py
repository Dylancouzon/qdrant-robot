"""Measure independent named-object gallery policies on viewpoint videos.

.venv/bin/python bench/gallery.py
"""

import ast
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

from crop_arms import (
    ARMS,
    DATA,
    MATCH,
    MODEL,
    ROOT,
    Crops,
    crops,
    detect,
    taught_gallery,
    frames,
    iou,
    percentiles,
    teach,
)

POLICIES = (
    "fixed",
    "fixed-masked",
    "confirm-1",
    "confirm-3",
    "track",
    "track-masked",
    "track-nofloor",
)
from robot.detect import Detection, Tracker  # noqa: E402
from robot.settings import DEFAULTS  # noqa: E402
from robot.things import MODEL as CROPS_MODEL  # noqa: E402

BAND, FLOOR, DUPLICATE = DEFAULTS["guess_band"], DEFAULTS["window_floor"], DEFAULTS["duplicate"]

OUTPUT = ROOT / "build/gallery"


def landscape(frame):
    """Place upright portrait content in the robot frame without stretching."""
    h, w = frame.shape[:2]
    if w > h:
        raise RuntimeError("Inspect landscape Objectron content before choosing rotation")
    width = round(w * 720 / h)
    left = (1280 - width) // 2
    image = np.full((720, 1280, 3), 114, np.uint8)
    image[:, left : left + width] = cv2.resize(frame, (width, 720))
    return image, (left, width)


def embed(pair, encoder):
    values = encoder([pair[arm] for arm in ARMS])
    return dict(zip(ARMS, values, strict=True))


def selected(rows, boxes, names, kind, content, reference=None, minimum=0):
    if reference is not None:
        overlaps = iou(boxes, np.array([reference]))[:, 0]
        return int(overlaps.argmax()) if len(overlaps) and overlaps.max() >= minimum else None
    left, width = content
    candidates = [
        i
        for i, row in enumerate(rows)
        if names[int(row[5])] in ({"cup", "mug"} if kind == "cup" else {"camera"})
        and left + 0.2 * width <= (boxes[i, 0] + boxes[i, 2]) / 2 <= left + 0.8 * width
        and 144 <= (boxes[i, 1] + boxes[i, 3]) / 2 <= 576
    ]
    return max(candidates, key=lambda i: rows[i, 4]) if candidates else None


def fill_record(record, frame, rows, boxes, protos, geometry, best, encoder, name):
    """Keep one detection, its descriptor, and reviewable crop together."""
    box = boxes[best]
    if min(box[2:] - box[:2]) <= 0:
        raise RuntimeError(f"Empty crop: {name}:{record['frame']}")
    pair, fill = crops(frame, rows[best], box, protos, geometry)
    record.update(box=box.tolist(), vectors=embed(pair, encoder), mask_fill=fill)
    same = [j for j, row in enumerate(rows) if j != best and int(row[5]) == int(rows[best, 5])]
    record["ambiguous"] = bool(same and (iou(boxes[same], box[None]) > 0.3).any())
    for arm in ARMS:
        target = OUTPUT / f"{name}-{record['frame']:04}-{arm}.jpg"
        assert cv2.imwrite(str(target), pair[arm])
        record["images"][arm] = str(target)


def video_metadata(path):
    """Read the source clock and frame count used by the teaching split."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if not np.isfinite(fps) or fps <= 0 or total < 2:
        raise RuntimeError(f"Invalid video metadata: {path}")
    return fps, total


def teaching_track(tracker, box):
    """Find the runtime track holding a teaching detection after synonym suppression."""
    candidates = [
        t
        for t in tracker.tracks
        if t.missed == 0 and iou(np.array([t.det.box]), np.array([box]))[0, 0] >= 0.7
    ]
    return max(candidates, key=lambda t: t.det.conf).id if candidates else None


def collect_record(
    index,
    frame,
    rows,
    boxes,
    protos,
    geometry,
    best,
    encoder,
    name,
    teaching_shot,
    boundary,
    shots,
    ended,
    tracker,
    taught_id,
    detections,
):
    """Keep scoring truth separate from the crop currently matched to the taught track."""
    record = {"frame": index, "box": None, "vectors": None, "ambiguous": False, "images": {}}
    if best is not None:
        fill_record(record, frame, rows, boxes, protos, geometry, best, encoder, name)
        if teaching_shot and index <= boundary:
            for arm in ARMS:
                shots[arm].append(record["vectors"][arm])
    record["track_crop"] = None
    if index <= boundary and (ended is None or index < ended):
        track = next(t for t in tracker.tracks if t.id == taught_id)
        tracked = next(j for j, detection in enumerate(detections) if detection is track.det)
        if tracked == best:
            record["track_crop"] = record.copy()
        else:
            crop = {"frame": index, "images": {}}
            fill_record(
                crop, frame, rows, boxes, protos, geometry, tracked, encoder, name + "-track"
            )
            record["track_crop"] = crop
    return record


def finish_collection(name, start, ended, reason, boundary, protocol, session, encoder, shots):
    """Validate teaching and preserve the original fixed-gallery construction."""
    if start is None:
        raise RuntimeError(f"No teaching detection: {name}")
    if ended is None:
        ended, reason = boundary + 1, "half ended"
    if protocol:
        galleries, teaching = teach(session, encoder, protocol)
    else:
        galleries = {arm: taught_gallery(shots[arm]) for arm in ARMS}
        teaching = [start, start + 10, start + 20]
    return ended, reason, galleries, teaching


def collect(path, session, encoder, names, protocol=None, stride=3):
    """Track every original frame; embed sampled truth and taught-track crops separately."""
    name = "d145-cup" if protocol else path.parent.name
    kind = name.split("-")[0] if protocol is None else "cup"
    fps, total = video_metadata(path)
    records, shots = [], {arm: [] for arm in ARMS}
    tracker = Tracker()
    start = taught_id = boundary = ended = None
    reason = None
    for index, frame in frames(path):
        content = (0, 1280)
        if protocol is None:
            frame, content = landscape(frame)
        rows, boxes, protos, geometry = detect(session, frame)
        detections = [
            Detection(names[int(row[5])], float(row[4]), tuple(box.tolist()))
            for row, box in zip(rows, boxes, strict=True)
        ]
        tracker.update(detections, frame.shape[1], index / fps)
        best = selected(
            rows,
            boxes,
            names,
            kind,
            content,
            protocol["boxes"][str(index)] if protocol else None,
            protocol["physical_overlap_min"] if protocol else 0,
        )
        if start is None and best is not None:
            taught_id = teaching_track(tracker, boxes[best])
            if taught_id is None:
                continue
            start = index
            boundary = start + (total - start - 1) // 2
        if start is None:
            continue
        if ended is None and taught_id not in tracker.in_view():
            ended, reason = index, "lost"
        if ended is None and index > boundary:
            ended, reason = boundary + 1, "half ended"
        teaching_shot = index in (start, start + 10, start + 20)
        if index % stride and not teaching_shot:
            continue
        record = collect_record(
            index,
            frame,
            rows,
            boxes,
            protos,
            geometry,
            best,
            encoder,
            name,
            teaching_shot,
            boundary,
            shots,
            ended,
            tracker,
            taught_id,
            detections,
        )
        if index % stride == 0 or index == start:
            records.append(record)
    ended, reason, galleries, teaching = finish_collection(
        name, start, ended, reason, boundary, protocol, session, encoder, shots
    )
    scoring = [r for r in records if r["frame"] > boundary]
    print(
        f"{name}: {len(scoring)} scoring frames; track ended "
        f"{(ended - start) / fps:.3f}s ({reason})",
        flush=True,
    )
    return {
        "name": name,
        "kind": kind,
        "records": records,
        "ground_truth": [r for r in records if r["vectors"] is not None],
        "teaching_views": {arm: len(galleries[arm]) for arm in ARMS},
        "galleries": galleries,
        "teaching": teaching,
        "path": str(path),
        "stride": stride,
        "fps": fps,
        "teaching_frame": start,
        "teaching_half_end_frame": boundary,
        "taught_track_id": taught_id,
        "track_end_seconds": (ended - start) / fps,
        "track_end_reason": reason,
    }


def negatives(session, encoder):
    vectors = {arm: [] for arm in ARMS}
    tags = []
    counts = {}
    groups = {
        "negatives": sorted((DATA / "d140/negatives").glob("*.jpg")),
        "coco": sorted((Path.home() / ".cache/coco-val2017").glob("*.jpg"))[:150],
    }
    if not all(groups.values()):
        raise RuntimeError("Negative image set is missing")
    for source, paths in groups.items():
        count = 0
        for path in paths:
            frame = cv2.imread(str(path))
            if frame is None:
                raise RuntimeError(f"Cannot decode {path}")
            rows, boxes, protos, geometry = detect(session, frame)
            pairs = [
                crops(frame, row, box, protos, geometry)[0]
                for row, box in zip(rows, boxes, strict=True)
                if min(box[2:] - box[:2]) > 0
            ]
            for offset in range(0, len(pairs), 16):
                batch = pairs[offset : offset + 16]
                values = encoder([p[arm] for p in batch for arm in ARMS])
                for j, arm in enumerate(ARMS):
                    vectors[arm].extend(values[j::2])
            tags.extend(
                {"source": source, "kind": None, "image": str(path), "crop": j}
                for j in range(len(pairs))
            )
            count += len(pairs)
        counts[source] = {"images": len(paths), "detections": count}
        print(f"Negatives {source}: {count}", flush=True)
    return {arm: np.array(v) for arm, v in vectors.items()}, counts, tags


def distractors(instance, instances, external, arm, external_tags):
    vectors, same = [external[arm]], [np.zeros(len(external[arm]), bool)]
    tags = list(external_tags)
    for other in instances:
        if other is instance:
            continue
        available = other["ground_truth"]
        indices = np.linspace(0, len(available) - 1, min(60, len(available)), dtype=int)
        values = [available[i]["vectors"][arm] for i in indices]
        if values:
            tags.extend(
                {
                    "source": other["name"],
                    "kind": other["kind"],
                    "frame": available[i]["frame"],
                    "image": available[i]["images"][arm],
                }
                for i in indices
            )
            vectors.append(np.array(values))
            same.append(np.full(len(values), other["kind"] == instance["kind"]))
    return np.concatenate(vectors), np.concatenate(same), tags


def replay(policy, instance, pool, same, tags, sink):
    """Freeze each gallery before scoring unseen later frames."""
    arm = "masked" if policy.endswith("masked") else "box"
    gallery = instance["galleries"][arm].copy()
    confirmations = 0
    last = (
        -float("inf")
        if policy.startswith("confirm")
        else instance["teaching_frame"] / instance["fps"]
    )
    near_previous = False
    admissions, positive = [], []
    for record in instance["records"]:
        index = record["frame"]
        teaching = index <= instance["teaching_half_end_frame"]
        candidate = record.get("track_crop") if policy.startswith("track") else record
        score = None
        admitted = False
        if teaching and candidate is not None and candidate["vectors"] is not None:
            vector = candidate["vectors"][arm]
            score = float(np.max(vector @ gallery.T))
            near = MATCH - BAND <= score < MATCH
            now = index / instance["fps"]
            if policy.startswith("confirm"):  # simulated: every eligible question gets a "yes"
                eligible = (
                    near and near_previous and now - last >= 3 and confirmations < int(policy[-1])
                )
            elif policy.startswith("track"):
                eligible = (
                    (policy == "track-nofloor" or score >= FLOOR)
                    and score < DUPLICATE
                    and not candidate["ambiguous"]
                    and now - last >= 1
                )
            else:
                eligible = False
            near_previous = near
            if eligible and score < DUPLICATE:
                if len(gallery) == 24:
                    gallery = np.delete(gallery, 1, axis=0)
                gallery = np.vstack([gallery, vector])
                last = now
                confirmations += policy.startswith("confirm")
                admitted = True
                admissions.append(candidate)
        elif teaching:
            near_previous = False
        if not teaching:
            score = (
                float(np.max(record["vectors"][arm] @ gallery.T))
                if record["vectors"] is not None
                else None
            )
            positive.append(score)
        sink.write(
            json.dumps(
                {
                    "type": "frame",
                    "instance": instance["name"],
                    "policy": policy,
                    "frame": index,
                    "teaching": teaching,
                    "score": score,
                    "admitted": admitted,
                    "views": len(gallery),
                    "box": record["box"],
                }
            )
            + "\n"
        )
    final = np.max(pool @ gallery.T, axis=1)
    for tag, score in zip(tags, final, strict=True):
        sink.write(
            json.dumps(
                {
                    "type": "final_negative",
                    "instance": instance["name"],
                    "policy": policy,
                    **tag,
                    "score": float(score),
                }
            )
            + "\n"
        )
    hits = sum(s is not None and s >= MATCH for s in positive)
    return (
        {
            "hits": hits,
            "scored_frames": len(positive),
            "hit_fraction": hits / len(positive),
            "no_detection": sum(s is None for s in positive),
            "views_end": len(gallery),
            "admissions": len(admissions),
            "false_matches": int((final >= MATCH).sum()),
            "negatives_scored": len(final),
            "negative_max": float(final.max()),
            "same_kind_max": float(final[same].max()),
        },
        final,
        admissions,
        {"positive": positive, "final": final, "tags": tags},
    )


def contact(policy, instance, admissions, run):
    arm = "masked" if policy.endswith("masked") else "box"
    tiles = []
    for record in admissions:
        image = cv2.imread(record["images"][arm])
        h, w = image.shape[:2]
        ratio = min(180 / w, 160 / h)
        tile = np.full((190, 200, 3), 114, np.uint8)
        resized = cv2.resize(image, (round(w * ratio), round(h * ratio)))
        tile[: resized.shape[0], : resized.shape[1]] = resized
        cv2.putText(
            tile, f"frame {record['frame']}", (5, 182), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1
        )
        tiles.append(tile)
    if not tiles:
        tile = np.full((190, 800, 3), 220, np.uint8)
        cv2.putText(
            tile, "No track admissions", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1
        )
        tiles.append(tile)
    while len(tiles) % 4:
        tiles.append(np.full_like(tiles[0], 114))
    sheet = np.vstack([np.hstack(tiles[i : i + 4]) for i in range(0, len(tiles), 4)])
    path = OUTPUT / f"{run}-{policy}-{instance['name']}-admissions.jpg"
    assert cv2.imwrite(str(path), sheet)
    return str(path.relative_to(ROOT))


def pair_table(data, threshold):
    """Count each final-gallery crop once and group it by its source."""
    rows = []
    for name, values in data.items():
        grouped = {}
        for tag, score in zip(values["tags"], values["final"], strict=True):
            key = (tag["source"], tag["kind"])
            grouped.setdefault(key, []).append(float(score))
        for (source, kind), scores in grouped.items():
            count = sum(score >= threshold for score in scores)
            if count:
                rows.append(
                    {
                        "gallery_instance": name,
                        "source_instance": source,
                        "source_kind": kind,
                        "count": count,
                        "max_score": max(scores),
                    }
                )
    return sorted(
        rows,
        key=lambda r: (-r["count"], -r["max_score"], r["gallery_instance"], r["source_instance"]),
    )


def threshold_sweep(data):
    """Rescore recorded positives; gallery admission remains at the replay settings."""
    positive = [score for values in data.values() for score in values["positive"]]
    d145 = data.get("d145-cup", {}).get("positive", [])
    final = np.concatenate([values["final"] for values in data.values()])
    rows = []
    for step in range(31):
        threshold = round(0.80 + step * 0.005, 3)
        hits = sum(score is not None and score >= threshold for score in positive)
        d145_hits = sum(score is not None and score >= threshold for score in d145)
        rows.append(
            {
                "threshold": threshold,
                "hits": hits,
                "scored_frames": len(positive),
                "hit_fraction": hits / len(positive),
                "d145_hits": d145_hits,
                "d145_frames": len(d145),
                "false_matches": int((final >= threshold).sum()),
                "false_pairs": len(pair_table(data, threshold)),
            }
        )
    return rows


def pair_contact(pairs, instances, run):
    """Show representative instance crops side by side for the worst fixed pairs."""
    by_name = {i["name"]: i for i in instances}
    tiles = []
    for pair in pairs:
        sides = []
        for key in ("gallery_instance", "source_instance"):
            name = pair[key]
            record = by_name[name]["ground_truth"][0]
            image = cv2.imread(record["images"]["box"])
            if image is None:
                raise RuntimeError(f"Cannot decode {record['images']['box']}")
            h, w = image.shape[:2]
            ratio = min(380 / w, 230 / h)
            tile = np.full((280, 400, 3), 220, np.uint8)
            resized = cv2.resize(image, (round(w * ratio), round(h * ratio)))
            tile[: resized.shape[0], : resized.shape[1]] = resized
            cv2.putText(tile, name, (5, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            sides.append(tile)
        row = np.hstack(sides)
        label = f"{pair['count']} crops; max {pair['max_score']:.4f}"
        cv2.putText(row, label, (5, 272), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        tiles.append(row)
    if not tiles:
        return None
    path = OUTPUT / f"{run}-pairs.jpg"
    assert cv2.imwrite(str(path), np.vstack(tiles))
    return str(path.relative_to(ROOT))


def main():
    started = time.time()
    run = str(int(started))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(MODEL), options, providers=["CPUExecutionProvider"])
    names = ast.literal_eval(session.get_modelmeta().custom_metadata_map["names"])
    encoder = Crops()
    assert encoder.sess.get_providers() == ["CPUExecutionProvider"]
    protocol = json.loads((DATA / "d145/cup/protocol.json").read_text())
    instances = [
        collect(
            DATA / "d140/external/cup-batch-5-3.avi", session, encoder, names, protocol, stride=1
        )
    ]
    paths = sorted((Path.home() / ".cache/objectron").glob("*/video.MOV"))
    assert len(paths) == 16, len(paths)
    for path in paths:
        instances.append(collect(path, session, encoder, names))
    external, counts, external_tags = negatives(session, encoder)
    table, admitted, replayed = {}, {}, {}
    with (OUTPUT / f"{run}.jsonl").open("w") as sink:
        for policy in POLICIES:
            arm = "masked" if policy.endswith("masked") else "box"
            results, scores = {}, []
            replayed[policy] = {}
            for instance in instances:
                pool, same, tags = distractors(instance, instances, external, arm, external_tags)
                row, negative_scores, admissions, values = replay(
                    policy, instance, pool, same, tags, sink
                )
                replayed[policy][instance["name"]] = values
                results[instance["name"]] = row
                scores.append(negative_scores)
                admitted[policy, instance["name"]] = admissions
            merged = np.concatenate(scores)
            hits = sum(r["hits"] for r in results.values())
            total = sum(r["scored_frames"] for r in results.values())
            false = int((merged >= MATCH).sum())
            table[policy] = {
                "hits": hits,
                "scored_frames": total,
                "hit_fraction": hits / total,
                "d145": results["d145-cup"],
                "instances": results,
                "false_matches": false,
                "negatives_scored": len(merged),
                "negative_max": float(merged.max()),
                "negative_scores": percentiles(merged.tolist(), (99,)),
                "same_kind_max": max(r["same_kind_max"] for r in results.values()),
                "status": "FAIL" if false else "PASS",
            }
            print(policy, hits, total, false, flush=True)
    sweep = {policy: threshold_sweep(data) for policy, data in replayed.items()}
    fixed_zero = next((r for r in sweep["fixed"] if r["false_matches"] == 0), None)
    zero_false = {}
    for policy, rows in sweep.items():
        own = next((r for r in rows if r["false_matches"] == 0), None)
        at_fixed = next(
            (r for r in rows if fixed_zero and r["threshold"] == fixed_zero["threshold"]), None
        )
        zero_false[policy] = {"lowest": own, "at_fixed_zero": at_fixed}
    pairs = {policy: pair_table(replayed[policy], MATCH) for policy in ("fixed", "track")}
    instance_pairs = [
        r for r in pairs["fixed"] if r["source_instance"] not in ("negatives", "coco")
    ][:6]
    pair_sheet = pair_contact(instance_pairs, instances, run)
    examples = sorted(instances[1:], key=lambda i: len(admitted["track", i["name"]]), reverse=True)[
        :2
    ]
    sheets = [
        contact("track", i, admitted["track", i["name"]], run) for i in [instances[0], *examples]
    ]
    for policy in POLICIES:
        table[policy]["median_views"] = float(
            np.median([r["views_end"] for r in table[policy]["instances"].values()])
        )
        table[policy]["median_teaching_window_seconds"] = float(
            np.median(
                [
                    i["track_end_seconds"]
                    if policy.startswith("track")
                    else (i["teaching_half_end_frame"] + 1 - i["teaching_frame"]) / i["fps"]
                    for i in instances
                ]
            )
        )
    result = {
        "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (
                "bench/gallery.py",
                "bench/crop_arms.py",
                "robot/things.py",
                "robot/detect.py",
            )
        },
        "model_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (MODEL, CROPS_MODEL)
        },
        "machine": {"label": "E", "hostname": platform.node(), "platform": platform.platform()},
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "onnxruntime": ort.__version__,
        },
        "command": shlex.join([sys.executable, *sys.argv]),
        "elapsed_seconds": time.time() - started,
        "limits": {
            "match": MATCH,
            "cap": 24,
            "guess_band": BAND,
            "window_floor": FLOOR,
            "duplicate": DUPLICATE,
            "objectron_stride": 3,
            "d145_stride": 1,
            "tracker_stride": 1,
            "interval_clock": "frame index / source fps",
        },
        "notes": [
            "Every original frame feeds runtime Detection objects to Tracker.",
            "Embedding stride is independent of tracker cadence.",
            "Track windows close permanently at the first unmatched frame.",
            "Teaching includes the first frame plus half of the remaining source frames.",
            "Scoring ground truth is independent of taught-track selection.",
            "D145 retains the original held-clip initial gallery.",
            "Zero-false thresholds use a 0.005 sweep from 0.80 to 0.95.",
        ],
        "negative_sources": counts,
        "negative_count_semantics": (
            "Final galleries score every negative crop once per target instance."
        ),
        "rows": str((OUTPUT / f"{run}.jsonl").relative_to(ROOT)),
        "instances": [
            {
                k: i[k]
                for k in (
                    "name",
                    "kind",
                    "path",
                    "stride",
                    "fps",
                    "teaching_frame",
                    "teaching",
                    "teaching_views",
                    "teaching_half_end_frame",
                    "taught_track_id",
                    "track_end_seconds",
                    "track_end_reason",
                )
            }
            for i in instances
        ],
        "policies": table,
        "sweep": sweep,
        "zero_false": zero_false,
        "pairs": pairs,
        "contact_sheets": [*sheets, pair_sheet],
    }
    path = ROOT / f"bench/results/2026-10-11-gallery-{run}.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(path, flush=True)


if __name__ == "__main__":
    main()
