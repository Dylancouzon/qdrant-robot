#!/usr/bin/env python3
"""People memory checks. Default (Mac): enroll the dev team photos into an Edge People shard,
identify every dev probe and LFW stranger through it, and compare with the bake-off's two-shot
decisions (bench/faces_bakeoff.py). --speed (Jetson): ms per face for the face step (detect,
align, embed) on LFW photos, and the memory the face models take, on ORT CUDA or TensorRT FP16.

    python -m bench.people_bench [--face-px 40]
    python -m bench.people_bench --speed DIR [--tensorrt]   DIR: LFW identity folders only

Results hold person ids and scores only, never faces or vectors.
"""
import argparse
import contextlib
import json
import os
import platform
import resource
import shlex
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import onnxruntime as ort

from robot.config import SHARED
from robot.faces import Faces, align
from robot.people import THRESHOLD, People, face


def percentiles(ms: list[float]) -> dict:
    return {"p50_ms": round(float(np.percentile(ms, 50)), 2),
            "p99_ms": round(float(np.percentile(ms, 99)), 2), "n": len(ms)}


def dev(face_px: int) -> dict:
    """Edge enroll then identify on the dev split, against the bake-off's numpy decisions."""
    from bench.faces_bakeoff import claim_scores, data
    faces = Faces()
    enroll, probes, _ = data(faces, False, face_px)
    probes = [(p, c) for p, c in probes if c is not None]
    vec = lambda crops: np.concatenate([faces.embed([c]) for c in crops])  # noqa: E731 as bake-off
    ids = sorted(enroll)
    gallery = [vec(enroll[p]) for p in ids]
    pv = vec([c for _, c in probes])
    with tempfile.TemporaryDirectory() as tmp:
        people = People(Path(tmp))
        for p, shots in zip(ids, gallery, strict=True):
            assert people.enroll(p, {f"{p}-{k}": v for k, v in enumerate(shots)}, time.time())
        got, ms = [], []
        for v in pv:
            t = time.perf_counter()
            got.append(people.identify(v))
            ms.append((time.perf_counter() - t) * 1000)
        people.shard.close()
    scores = claim_scores(gallery, pv)["two-shot"]
    ref = [ids[j] if s >= THRESHOLD else None for s, j in zip(scores.max(1), scores.argmax(1),
                                                               strict=True)]
    names = [g[0] if g else None for g in got]
    truth = [p for p, _ in probes]
    known = [k for k, p in enumerate(truth) if p]
    others = [np.delete(scores[k], ids.index(truth[k])).max() for k in known]
    return {"kind": "dev", "face_px": face_px, "people": len(ids), "threshold": THRESHOLD,
            "known_probes": len(known), "stranger_probes": len(truth) - len(known),
            "recognized": sum(names[k] == truth[k] for k in known),
            "false_identities": sum(n is not None and n != t for n, t in zip(names, truth,
                                                                            strict=True)),
            "same_as_bakeoff": sum(n == r for n, r in zip(names, ref, strict=True)),
            "stranger_max": round(float(scores[[t is None for t in truth]].max()), 4),
            "genuine_min": round(float(min(scores[k, ids.index(truth[k])] for k in known)), 4),
            "known_other_max": round(float(max(others)), 4),  # closest other person, two-shot
            "identify": percentiles(ms)}


def timed(fn, ms: list):
    """`fn`, appending each call's duration in ms to `ms`."""
    def call(*args):
        t = time.perf_counter()
        out = fn(*args)
        ms.append((time.perf_counter() - t) * 1000)
        return out
    return call


def available_mb() -> int:
    info = dict(line.split(":") for line in Path("/proc/meminfo").read_text().splitlines())
    return int(info["MemAvailable"].split()[0]) // 1024


def speed(folder: Path, tensorrt: bool) -> dict:
    """The face step on LFW photos (250 px, face centered) with a person box twice as tall,
    so the photo is the box's upper part, as a person crop from the camera."""
    before = available_mb()
    session = ort.InferenceSession
    trt = [("TensorrtExecutionProvider", {
        "trt_fp16_enable": True, "trt_engine_cache_enable": True,
        "trt_engine_cache_path": str(SHARED / "trt-cache")}), "CUDAExecutionProvider"]
    # Faces builds its embedder session on CUDA; for TensorRT only that one session changes.
    with mock.patch.object(ort, "InferenceSession",
                           lambda path, **_: session(path, providers=trt)
                           ) if tensorrt else contextlib.nullcontext():
        faces = Faces()
    images = [cv2.imread(str(p)) for p in sorted(folder.glob("*/*.jpg"))]
    box = (0, 0, 250, 500)
    for im in images[:10]:  # warm-up, and the TensorRT engine build
        face(faces, im, box)
    loaded = available_mb()
    det, emb, total, found = [], [], [], []
    faces.detect, faces.embed = timed(faces.detect, det), timed(faces.embed, emb)  # one pass
    for im in images:
        t = time.perf_counter()
        found.append(face(faces, im, box) is not None)
        total.append((time.perf_counter() - t) * 1000)
    row = {"kind": "speed", "provider": faces.session.get_providers()[0], "images": len(images),
           "faces_found": int(sum(found)), "face_step": percentiles(total),
           "detect": percentiles(det), "embed": percentiles(emb),  # align: the rest
           "models_mb": before - loaded, "available_mb": available_mb(),
           "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024}
    if tensorrt:  # FP16 against the CUDA FP32 vectors on the same crops
        crops = [align(im, d[0, 4:14].reshape(5, 2)) for im in images[:50]
                 if len(d := faces.detect(im))]
        cuda = Faces()  # batch 1 each: a new batch size would rebuild the TensorRT engine
        row["fp16_cosine_min"] = round(min(float(faces.embed([c])[0] @ cuda.embed([c])[0])
                                           for c in crops), 6)
    return row


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--face-px", type=int, default=0, help="shrink faces to this width; 0: as shot")
    p.add_argument("--speed", type=Path, help="LFW identity folders (Jetson)")
    p.add_argument("--tensorrt", action="store_true")
    a = p.parse_args()
    ort.set_default_logger_severity(3)
    row = speed(a.speed, a.tensorrt) if a.speed else dev(a.face_px)
    row.update(machine=platform.node().split(".")[0], release=os.environ.get("ROBOT_RELEASE"),
               command=shlex.join(sys.argv), onnxruntime=ort.__version__)
    print(json.dumps(row), flush=True)
    out = SHARED / "results" if a.speed else Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{time.strftime('%Y-%m-%d')}-people-{row['kind']}-{int(time.time())}.jsonl"
     ).write_text(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
