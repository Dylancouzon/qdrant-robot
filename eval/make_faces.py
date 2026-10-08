#!/usr/bin/env python3
"""Compose the M3 face scenes: one visitor cut from a team photo or an LFW stranger, pasted at
visitor size (face 40 to 120 px) into a camera background, for eval/{dev,heldout}/m3.jsonl.
Writes eval/faces/scenes/ and its SOURCES.md, both gitignored: they show team faces.

    python -m eval.make_faces   (needs eval/faces and models/faces; the look-alike search over
                                 LFW takes a few minutes on the Mac CPU)
"""
import json
from pathlib import Path

import cv2
import numpy as np

from bench.faces_bakeoff import FACES, LFW, crop, heldout_lfw, subject
from eval.make_scenes import DEV_BG, EVAL, HO_BG, H, W, X, background
from robot.faces import Faces

OUT = FACES / "scenes"
FACE_Y = 0.38  # face center height in the frame: a standing visitor in front of the desk robot
SEARCH_PX = 60  # face width at which LFW strangers are ranked against the enrolled shots

# name: (person id, manifest split and file index | "lookalike" | "lookalike2", face px, region).
# A look-alike is the LFW identity of the set's split whose face scores highest against the
# person's enrollment shots by the claim score (the second-best shot), so the hardest stranger.
SCENES = {
    "dev": {
        "p05-enroll-a": ("p05", "enroll", 0, 100, "center"),
        "p05-enroll-b": ("p05", "enroll", 1, 96, "center"),
        "p05-dev-a": ("p05", "dev", 0, 64, "left"),
        "p06-enroll-a": ("p06", "enroll", 0, 104, "center"),
        "p06-enroll-b": ("p06", "enroll", 1, 100, "center"),
        "p06-dev-a": ("p06", "dev", 0, 72, "right"),
        "p06-dev-b": ("p06", "dev", 1, 56, "center"),
        "p07-enroll-a": ("p07", "enroll", 0, 92, "center"),
        "p07-enroll-b": ("p07", "enroll", 1, 96, "center"),
        "p07-told": ("p07", "dev", 0, 80, "center"),
        "p07-dev-a": ("p07", "dev", 1, 60, "left"),
        "p07-dev-b": ("p07", "dev", 2, 76, "right"),
        "p08-enroll-a": ("p08", "enroll", 0, 100, "center"),
        "p08-enroll-b": ("p08", "enroll", 1, 104, "center"),
        "p08-replace": ("p08", "dev", 0, 84, "center"),
        "p08-dev-a": ("p08", "dev", 1, 68, "right"),
        "p08-dev-b": ("p08", "dev", 2, 52, "left"),
        "p08-dev-c": ("p08", "dev", 3, 80, "center"),
        "p09-enroll-a": ("p09", "enroll", 0, 96, "center"),
        "p09-enroll-b": ("p09", "enroll", 1, 100, "center"),
        "p09-dev-a": ("p09", "dev", 0, 70, "center"),
        "stranger-p05": ("p05", "lookalike", 0, 72, "center"),
        "stranger-p06": ("p06", "lookalike", 0, 76, "center"),
        "stranger-p06-2": ("p06", "lookalike2", 0, 60, "left"),
        "stranger-p07": ("p07", "lookalike", 0, 64, "right"),
    },
    "heldout": {
        "p02-enroll-a": ("p02", "enroll", 0, 98, "center"),
        "p02-enroll-b": ("p02", "enroll", 1, 102, "center"),
        "p02-ho-a": ("p02", "heldout", 0, 66, "right"),
        "p04-enroll-a": ("p04", "enroll", 0, 100, "center"),
        "p04-enroll-b": ("p04", "enroll", 1, 94, "center"),
        "p04-ho-a": ("p04", "heldout", 0, 74, "left"),
        "p11-enroll-a": ("p11", "enroll", 0, 96, "center"),
        "p11-enroll-b": ("p11", "enroll", 1, 100, "center"),
        "p11-ho-a": ("p11", "heldout", 0, 58, "center"),
        "p10-enroll-a": ("p10", "enroll", 0, 100, "center"),
        "p10-enroll-b": ("p10", "enroll", 2, 96, "center"),
        "p10-ho-a": ("p10", "heldout", 0, 70, "right"),
        "p01-told": ("p01", "heldout", 0, 82, "center"),
        "stranger-p02": ("p02", "lookalike", 0, 70, "left"),
        "stranger-p04": ("p04", "lookalike", 0, 62, "center"),
        "stranger-p11": ("p11", "lookalike", 0, 78, "right"),
    },
}


def cutout(path: Path) -> np.ndarray:
    """BGRA: a transparent cutout keeps its alpha; a plain photo gets a soft head-and-shoulders
    ellipse around its subject later (alpha 0 here marks "no alpha")."""
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"cannot read {path}")
    if im.ndim == 3 and im.shape[2] == 4 and im[..., 3].min() < 255:
        return im
    im = cv2.imread(str(path))  # EXIF orientation applied
    return np.dstack([im, np.zeros(im.shape[:2], np.uint8)])


def compose(faces: Faces, bg: np.ndarray, path: Path, face_px: int, region: str,
            lfw: bool) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """`bg` with the subject of `path` pasted so its face is `face_px` wide, centered at
    X[region] and FACE_Y; returns the frame and the subject's visible box (x1, y1, x2, y2)."""
    im = cutout(path)
    s = 1600 / max(im.shape[:2])  # detect on a manageable size first
    im = cv2.resize(im, None, fx=min(s, 1), fy=min(s, 1), interpolation=cv2.INTER_AREA)
    f = subject(faces, im[..., :3], lfw)
    if lfw:  # ponytail: LFW is cropped at the shoulders; its last rows stretched stand in for a
        # torso, so the person box is a visitor's (face in its upper half), not a bare head
        im = cv2.copyMakeBorder(im, 0, round(3 * f[3]), 0, 0, cv2.BORDER_REPLICATE)
    s = face_px / f[2]
    im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cx, cy = (f[0] + f[2] / 2) * s, (f[1] + f[3] / 2) * s
    if im[..., 3].max() == 0:  # plain photo: a soft ellipse over head, shoulders, and chest
        mask = np.zeros(im.shape[:2], np.uint8)
        cv2.ellipse(mask, (round(cx), round(cy + 1.9 * face_px)),
                    (round(1.7 * face_px), round(3.0 * face_px)), 0, 0, 360, 255, -1)
        im[..., 3] = cv2.GaussianBlur(mask, (0, 0), face_px / 8)
    dx, dy = round(X[region] * W - cx), round(FACE_Y * H - cy)
    frame = bg.copy()
    x1, y1 = max(0, dx), max(0, dy)
    x2, y2 = min(W, dx + im.shape[1]), min(H, dy + im.shape[0])
    src = im[y1 - dy:y2 - dy, x1 - dx:x2 - dx]
    a = src[..., 3:] / 255
    frame[y1:y2, x1:x2] = (a * src[..., :3] + (1 - a) * frame[y1:y2, x1:x2]).astype(np.uint8)
    ys, xs = np.nonzero(src[..., 3] > 127)
    return frame, (x1 + xs.min(), y1 + ys.min(), x1 + xs.max(), y1 + ys.max())


def lookalikes(faces: Faces, enroll: list[Path], heldout: bool, ranked: list) -> list[Path]:
    """LFW photos of the set's split, best first by the claim score against `enroll`;
    `ranked` caches (path, vector) for the split across people."""
    if not ranked:
        for d in sorted(p for p in LFW.iterdir() if heldout_lfw(p.name) == heldout):
            c = crop(faces, min(d.iterdir()), True, SEARCH_PX)
            if c is not None:
                ranked.append((min(d.iterdir()), faces.embed([c])[0]))
    shots = faces.embed([crop(faces, p, False, SEARCH_PX) for p in enroll])
    score = [np.sort(shots @ v)[-2] for _, v in ranked]
    return [ranked[i][0] for i in np.argsort(score)[::-1]]


def check(faces: Faces, frame: np.ndarray, box: tuple, face_px: int) -> float:
    """The face width YuNet finds in the upper half of the subject's box (as robot/people.py
    searches a person box); fails when it finds none or a size outside 40 to 120 px."""
    x1, y1, x2, y2 = box
    found = faces.detect(frame[y1:y1 + (y2 - y1) // 2, x1:x2])
    assert len(found), f"no face in the upper half of the person box at {face_px} px"
    w = float(found[0, 2])
    assert 40 <= w <= 120, f"face {w:.0f} px wide, outside 40 to 120"
    return w


def main() -> None:
    people = json.loads((FACES / "manifest.json").read_text())["people"]
    faces = Faces()
    OUT.mkdir(exist_ok=True)
    lines = ["# M3 face scenes (gitignored)", "", "Written by `eval/make_faces.py`.", ""]
    for name, scenes in SCENES.items():
        heldout = name == "heldout"
        bg = background(HO_BG if heldout else DEV_BG, EVAL / name)
        ranked: list = []
        for out, (pid, split, i, face_px, region) in scenes.items():
            if split.startswith("lookalike"):
                enroll = [FACES / f for f in people[pid]["enroll"]]
                path = lookalikes(faces, enroll, heldout, ranked)[split == "lookalike2"]
            else:
                path = FACES / people[pid][split][i]
            lfw = path.is_relative_to(LFW)
            frame, box = compose(faces, bg, path, face_px, region, lfw)
            w = check(faces, frame, box, face_px)
            dst = OUT / f"{name}-{out}.jpg"
            cv2.imwrite(str(dst), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            source = f"LFW {path.parent.name}" if lfw else f"{pid} {split} {path.name}"
            lines.append(f"- `{dst.name}`: {source}, face {w:.0f} px (asked {face_px}), "
                         f"{region}, person box {box}")
            print(lines[-1], flush=True)
    (OUT / "SOURCES.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
