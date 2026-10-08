#!/usr/bin/env python3
"""Face embedder and claim-score bake-off on the Mac (CPU): YuNet, ArcFace alignment, then three
embedders and three claim scores. Dev calibrates the threshold (dev impostor maximum + MARGIN);
--heldout runs the frozen CHOICE once on held-out people and strangers.

    python -m bench.faces_bakeoff [--heldout] [--face-px 80]

Inputs (gitignored): eval/faces/manifest.json (team photos, split per person) and LFW in
eval/faces/lfw/lfw (strangers, split per identity). Results hold person ids and scores only.
"""
import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from robot.config import MODELS, ROOT
from robot.faces import DETECTOR, Faces, align
from tools.models import sha256

FACES = ROOT / "eval/faces"
LFW = FACES / "lfw/lfw"
EMBEDDERS = {  # name: (model, pixel mean, scale), RGB input as each was trained
    # ONNX export of the .pt in models.json: backbones from github.com/otroshi/edgeface@ce86851,
    # torch 2.8.0, timm 1.0.19, opset 17, input 1x3x112x112 (max abs diff to PyTorch 5e-6).
    "edgeface-s": (MODELS / "faces/edgeface_s_gamma_05.onnx", 127.5, 1 / 127.5),
    "w600k-r50": (MODELS / "faces/w600k_r50.onnx", 127.5, 1 / 127.5),
    "sface": (MODELS / "faces/sface_2021dec.onnx", 0.0, 1.0),
}
CLAIMS = ("maxsim", "mean", "two-shot")
MARGIN = 0.05  # cosine added to the dev impostor maximum
GALLERIES = (5, 10, 20, 50)  # people enrolled; LFW dev identities fill beyond the team
# Frozen from the dev runs (full, 80 px, 40 px) before --heldout: the only pair with zero false
# matches at every gallery size and face size; the threshold is the highest dev one (40 px).
CHOICE = ("w600k-r50", "two-shot", 0.328, 40)  # embedder, claim, threshold, face_px


def load(path: Path) -> np.ndarray:
    """BGR, transparent cutouts on mid gray, longest side at most 1,280 px (EXIF applied)."""
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im.ndim == 3 and im.shape[2] == 4:
        a = im[..., 3:] / 255
        im = (im[..., :3] * a + 128 * (1 - a)).astype(np.uint8)
    else:
        im = cv2.imread(str(path))
    s = 1280 / max(im.shape[:2])
    return cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else im


def subject(faces: Faces, im: np.ndarray, centered: bool) -> np.ndarray | None:
    """The subject's detection: the largest face, or for LFW the face nearest the center."""
    found = faces.detect(im)
    if not len(found):
        return None
    if centered:
        c = found[:, :2] + found[:, 2:4] / 2 - np.array(im.shape[1::-1]) / 2
        found = found[np.argsort((c ** 2).sum(1))]
    return found[0]


def crop(faces: Faces, path: Path, centered: bool, face_px: int) -> np.ndarray | None:
    """Aligned crop of the subject; with `face_px`, the photo first shrinks until the subject's
    face box is that wide, as a face 1 to 2 m from the robot's wide camera (80 to 40 px)."""
    im = load(path)
    f = subject(faces, im, centered)
    if f is not None and face_px and f[2] > face_px:
        s = face_px / f[2]
        im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        f = subject(faces, im, centered)
    return None if f is None else align(im, f[4:14].reshape(5, 2))


def heldout_lfw(name: str) -> bool:
    return int(hashlib.sha256(name.encode()).hexdigest(), 16) % 10 < 3


def data(faces: Faces, heldout: bool, face_px: int) -> tuple[dict, list, dict]:
    """Enrollment crops per person id, probe crops with their person id (None for strangers,
    else the id; a None crop is a detector miss), and LFW identities with six or more found
    faces on dev (gallery growth)."""
    people = json.loads((FACES / "manifest.json").read_text())["people"]
    enroll = {pid: [crop(faces, FACES / f, False, face_px) for f in p["enroll"]]
              for pid, p in people.items()}
    assert all(c is not None for shots in enroll.values() for c in shots), "enrollment miss"
    split = "heldout" if heldout else "dev"
    probes = [(pid, crop(faces, FACES / f, False, face_px)) for pid, p in people.items()
              for f in p[split]]
    extra = {}
    for d in sorted(LFW.iterdir()):
        if heldout_lfw(d.name) != heldout:
            continue
        crops = [crop(faces, f, True, face_px) for f in sorted(d.iterdir())]
        found = [c for c in crops if c is not None]
        if not heldout and len(found) >= 6:
            extra[d.name] = found
        else:
            probes += [(None, c) for c in crops]
    return enroll, probes, extra


def claim_scores(gallery: list[np.ndarray], probes: np.ndarray) -> dict[str, np.ndarray]:
    """(probes, people) score per claim rule: best shot, mean person vector, second-best shot
    (a claim needs two distinct shots at the threshold)."""
    out = {c: np.zeros((len(probes), len(gallery))) for c in CLAIMS}
    for j, shots in enumerate(gallery):
        assert len(shots) >= 2, "two-shot support needs two enrolled shots"
        sims = np.sort(probes @ shots.T, axis=1)
        mean = shots.mean(0)
        out["maxsim"][:, j] = sims[:, -1]
        out["mean"][:, j] = probes @ (mean / np.linalg.norm(mean))
        out["two-shot"][:, j] = sims[:, -2]
    return out


def judge(scores: np.ndarray, truth: np.ndarray, t: float) -> dict:
    """Identify as the best-scoring person, claim only at `t` or above. `truth` is the gallery
    index of each probe, -1 for strangers."""
    best, pick = scores.max(1), scores.argmax(1)
    claimed = best >= t
    known = truth >= 0
    rows = np.arange(len(truth))
    genuine = scores[rows[known], truth[known]]
    own = np.eye(scores.shape[1], dtype=bool)[truth] & known[:, None]
    impostor = np.ma.masked_array(scores, mask=own)
    return {"threshold": round(t, 4), "known_probes": int(known.sum()),
            "stranger_probes": int((~known).sum()),
            "recognized": int((claimed & known & (pick == truth)).sum()),
            "false_identities": int((claimed & (pick != truth)).sum()),
            "false_on_strangers": int((claimed & ~known).sum()),
            "genuine_min": round(float(genuine.min()), 4),
            "genuine_p50": round(float(np.median(genuine)), 4),
            "impostor_p50": round(float(np.ma.median(impostor)), 4),
            "impostor_p999": round(float(np.percentile(impostor.compressed(), 99.9)), 4),
            "impostor_max": round(float(impostor.max()), 4)}


def cost(faces: Faces, model: Path) -> dict:
    x = [np.zeros((112, 112, 3), np.uint8)]
    for _ in range(5):
        faces.embed(x)
    ms = []
    for _ in range(50):
        t = time.perf_counter()
        faces.embed(x)
        ms.append((time.perf_counter() - t) * 1000)
    return {"mac_cpu_ms_p50": round(statistics.median(ms), 2),
            "size_mb": round(model.stat().st_size / 1e6, 1)}


def run(name: str, heldout: bool, enroll: dict, probes: list, extra: dict) -> list[dict]:
    model, mean, scale = EMBEDDERS[name]
    faces = Faces(model, mean, scale)
    vec = lambda crops: np.concatenate([faces.embed([c]) for c in crops])  # noqa: E731 SFace: batch 1
    ids = sorted(enroll)
    gallery = [vec(enroll[p]) for p in ids]
    # A detector miss makes no claim: it counts in the inputs, never as recognized or false.
    inputs = {"known_inputs": sum(p is not None for p, _ in probes),
              "known_missed": sum(p is not None and c is None for p, c in probes),
              "stranger_inputs": sum(p is None for p, _ in probes),
              "stranger_missed": sum(p is None and c is None for p, c in probes)}
    probes = [(p, c) for p, c in probes if c is not None]
    truth = np.array([ids.index(p) if p else -1 for p, _ in probes])
    pv = vec([c for _, c in probes])
    rows = []
    for c, scores in claim_scores(gallery, pv).items():
        if heldout:
            if (name, c) == CHOICE[:2]:
                rows.append({"kind": "heldout", "embedder": name, "claim": c, **inputs,
                             **judge(scores, truth, CHOICE[2])})
            continue
        dev = judge(scores, truth, 0.0)
        t = dev["impostor_max"] + MARGIN
        hit = (scores.max(1) >= t) & (scores.argmax(1) == truth)
        rows.append({"kind": "dev", "embedder": name, "claim": c, "people": len(ids), **inputs,
                     "shots": [len(enroll[p]) for p in ids], **judge(scores, truth, t),
                     # the nearest dev stranger per person: its look-alike, by this embedder
                     "lookalike_max": dict(zip(ids, scores[truth < 0].max(0).round(4).tolist(),
                                               strict=True)),
                     "per_person_recognized": {p: int((hit & (truth == k)).sum())
                                               for k, p in enumerate(ids)}})
    if not heldout:
        rows += growth(name, gallery, pv[truth < 0], vec, extra, rows)
        rows.append({"kind": "cost", "embedder": name, **cost(faces, model)})
    return rows


def growth(name, gallery, strangers, vec, extra, dev_rows) -> list[dict]:
    """False matches on dev strangers at each claim's dev threshold as the gallery grows: team
    people first, then LFW dev identities (five shots each) that are never probes."""
    more = [vec(crops[:5]) for crops in extra.values()]
    rows = []
    for n in GALLERIES:
        g = (gallery + more)[:n]
        for c, scores in claim_scores(g, strangers).items():
            t = next(r["threshold"] for r in dev_rows if r["claim"] == c)
            best = scores.max(1)
            rows.append({"kind": "growth", "embedder": name, "claim": c, "people": n,
                         "stranger_probes": len(strangers), "threshold": t,
                         "false_matches": int((best >= t).sum()),
                         "impostor_max": round(float(best.max()), 4),
                         "impostor_p999": round(float(np.percentile(best, 99.9)), 4)})
    return rows


def revision() -> dict:
    """Git HEAD and a hash of the bake-off's own source as run (covers uncommitted changes)."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()
    src = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in
                                  ("bench/faces_bakeoff.py", "robot/faces.py"))).hexdigest()
    return {"head": head, "source_sha256": src[:16]}


def main(heldout: bool, face_px: int) -> None:
    ort.set_default_logger_severity(3)
    if heldout:
        face_px = CHOICE[3]
    names = [CHOICE[0]] if heldout else list(EMBEDDERS)
    meta = {"kind": "meta", "machine": platform.node().split(".")[0],
            "platform": platform.platform(), "revision": revision(),
            "split": "heldout" if heldout else "dev", "margin": MARGIN, "face_px": face_px,
            "versions": {p: version(p) for p in ("onnxruntime", "opencv-python-headless", "numpy")},
            "models": {p.name: sha256(p) for p in [DETECTOR] + [EMBEDDERS[n][0] for n in names]},
            "preprocessing": "longest side <= 1280 px, alpha on gray 128, YuNet score >= 0.6, "
                             "largest face (LFW: nearest the center), similarity warp of five "
                             "landmarks to the ArcFace 112x112 template, RGB (x - mean) * scale",
            "embedders": {n: EMBEDDERS[n][1:] for n in names}, "claims": CLAIMS,
            "command": "python -m bench.faces_bakeoff" + " --heldout" * heldout
                       + f" --face-px {face_px}" * bool(face_px)}
    crops = data(Faces(*EMBEDDERS[names[0]]), heldout, face_px)  # detection and alignment, once
    rows = [meta] + [r for n in names for r in run(n, heldout, *crops)]
    out = ROOT / (f"bench/results/{time.strftime('%Y-%m-%d')}-faces-{meta['split']}-"
                  f"{face_px or 'full'}px-{int(time.time())}.jsonl")
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    for r in rows[1:]:
        print(json.dumps({k: v for k, v in r.items()
                          if k not in ("per_person_recognized", "lookalike_max")}))
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--face-px", type=int, default=0, help="shrink faces to this width; 0: as shot")
    a = ap.parse_args()
    main(a.heldout, a.face_px)
