#!/usr/bin/env python3
"""Compose the M2 fixture scenes: COCO val2017 objects cut out along their masks and pasted at a
fixed region of a background, plus plain COCO copies; writes eval/<set>/images and SOURCES.md.

    eval/make_scenes.py instances_val2017.json   (from COCO annotations_trainval2017.zip)
"""
import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np

EVAL = Path(__file__).parent
CACHE = Path.home() / ".cache" / "coco-val2017"
W, H = 960, 540  # the robot's frame shape (16:9), as in eval/dev/live
X = {"left": 0.17, "center": 0.5, "right": 0.83}  # object centers; left means image left
MAX_W = {"left": 290, "center": 600, "right": 290}  # a side object stays inside its third
DEV_BG = "live/closet-night.jpg"
HO_BG = 68286  # a hotel bedroom, cropped to 16:9; held-out never uses a dev background

# name: (background, [(annotation id, region, height px)], why it fits). An int background is a
# COCO image; a scene with no objects is that image as is (a real photo).
SCENES = {
    "dev": {
        "m2-clock": (DEV_BG, [(335955, "center", 260)], "a station clock, center"),
        "m2-clock-right": (DEV_BG, [(335955, "right", 220)], "the station clock, right third"),
        "m2-laptop": (DEV_BG, [(1097715, "center", 300)], "a black laptop, center"),
        "m2-laptop-silver": (DEV_BG, [(1102546, "center", 300)], "a silver laptop, center"),
        "m2-snack": (DEV_BG, [(1041806, "left", 200), (1078906, "right", 190)],
                     "a banana left, a pink-frosted donut right"),
        "m2-banana": (DEV_BG, [(1041806, "left", 200)], "the banana left; the donut is gone"),
        "m2-pepsi": (DEV_BG, [(670367, "center", 260)], "a blue Pepsi paper cup, center"),
        "m2-umbrella-bag": (DEV_BG, [(282291, "left", 290), (1178519, "right", 260)],
                            "a rainbow-striped umbrella left, a red handbag right"),
        "m2-bag-umbrella": (DEV_BG, [(1178519, "left", 260), (282291, "right", 290)],
                            "the same two, swapped: red handbag left, umbrella right"),
        "m2-umbrella": (DEV_BG, [(282291, "center", 340)], "the striped umbrella, held up"),
        "m2-teddy-white": (DEV_BG, [(1163282, "center", 330)],
                           "a white teddy bear with a red scarf and red hat, center"),
        "m2-teddy-brown": (DEV_BG, [(1161771, "center", 330)],
                           "a brown teddy bear with a green hat, center"),
        "m2-teddies": (DEV_BG, [(1163282, "left", 280), (1161771, "right", 280)],
                       "white bear left, brown bear right"),
        "m2-phone-gold": (DEV_BG, [(1638183, "center", 340)],
                          "a gold keypad phone (Nokia), held up"),
        "m2-phone-black": (DEV_BG, [(323016, "center", 240)],
                           "a black slider phone, held up; same class as the gold one"),
        "m2-phones": (DEV_BG, [(323016, "left", 170), (1638183, "right", 240)],
                      "black phone left, gold phone right"),
        "m2-phone-gold-left": (DEV_BG, [(1638183, "left", 240)], "the gold phone, left third"),
        "coco-000000081061": (81061, [], "a wooden chair, a couch, a suitcase by a curb"),
        "coco-000000513688": (513688, [], "a desk chair at a desk with a laptop and phone"),
        "coco-000000366141": (366141, [], "a living room: armchairs, sofa, cat, TV"),
    },
    "heldout": {
        "m2-bg": (HO_BG, [], "the empty held-out scene: a hotel bed with two lamps"),
        "m2-scissors": (HO_BG, [(1157541, "center", 300)], "scissors, held up"),
        "m2-vase-remote": (HO_BG, [(1154625, "left", 260), (1111918, "right", 160)],
                           "a glass vase with stems left, a TV remote right"),
        "m2-remote-right": (HO_BG, [(1111918, "right", 160)], "the remote right; vase gone"),
        "m2-remote": (HO_BG, [(1111918, "center", 260)], "the TV remote, held up"),
        "m2-apples": (HO_BG, [(1049781, "center", 240)], "two red apples, center"),
        "m2-bag-umbrella": (HO_BG, [(1177695, "left", 280), (279676, "right", 260)],
                            "a black leather handbag left, a black lace umbrella right"),
        "m2-clock-left": (HO_BG, [(333904, "left", 230)], "an orange wall clock, left third"),
        "m2-teddy-white": (HO_BG, [(1163344, "center", 280)], "a white fluffy teddy bear"),
        "m2-teddy-gold": (HO_BG, [(1162789, "center", 320)],
                          "a golden-brown teddy bear with a yellow button tag"),
        "m2-bottle-dragon": (HO_BG, [(83672, "center", 360)],
                             "a brown beer bottle with a red Dragon Stout label"),
        "m2-bottle-pink": (HO_BG, [(86514, "center", 360)],
                           "a dark bottle with a pink label; same class as the stout"),
        "m2-phone-flip": (HO_BG, [(328787, "center", 330)], "a silver Samsung flip phone"),
        "m2-phone-slider": (HO_BG, [(321838, "center", 170)],
                            "a silver slider phone with a green screen; same class"),
        "m2-phones": (HO_BG, [(321838, "left", 120), (328787, "right", 250)],
                      "slider phone left, flip phone right"),
        "coco-000000578500": (578500, [], "a living room: blue wing chair, sofas, lamps"),
        "coco-000000319935": (319935, [], "a bedroom: armchair, sofa, bed, coffee table"),
        "coco-000000277197": (277197, [], "a living room: carved chairs, sofa, flowers"),
    },
}


def coco(image_id: int) -> Path:
    f = CACHE / f"{image_id:012d}.jpg"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"http://images.cocodataset.org/val2017/{f.name}", f)
    return f


def background(bg: str | int, root: Path) -> np.ndarray:
    if isinstance(bg, str):
        return cv2.imread(str(root / bg))
    im = cv2.imread(str(coco(bg)))
    h = round(im.shape[1] * H / W)  # center crop to 16:9
    top = (im.shape[0] - h) // 2
    return cv2.resize(im[top:top + h], (W, H), interpolation=cv2.INTER_AREA)


def paste(frame: np.ndarray, ann: dict, region: str, height: int) -> None:
    im = cv2.imread(str(coco(ann["image_id"])))
    mask = np.zeros(im.shape[:2], np.uint8)
    for poly in ann["segmentation"]:
        cv2.fillPoly(mask, [np.array(poly).reshape(-1, 2).astype(np.int32)], 255)
    x, y, w, h = (int(v) for v in ann["bbox"])
    s = min(height / h, MAX_W[region] / w)
    size = (round(w * s), round(h * s))
    obj = cv2.resize(im[y:y + h, x:x + w], size, interpolation=cv2.INTER_AREA)
    alpha = cv2.GaussianBlur(cv2.resize(mask[y:y + h, x:x + w], size), (5, 5), 0)[..., None] / 255
    x0, y0 = round(X[region] * W - size[0] / 2), round(0.55 * H - size[1] / 2)
    roi = frame[y0:y0 + size[1], x0:x0 + size[0]]
    roi[:] = (alpha * obj + (1 - alpha) * roi).astype(np.uint8)


def main(annotations: Path) -> None:
    d = json.loads(annotations.read_text())
    anns = {a["id"]: a for a in d["annotations"]}
    images = {i["id"]: i for i in d["images"]}
    licenses = {lic["id"]: lic for lic in d["licenses"]}
    cats = {c["id"]: c["name"] for c in d["categories"]}
    for name, scenes in SCENES.items():
        root = EVAL / name
        lines = ["# M2 fixture images", "", "Written by `eval/make_scenes.py`. Composites paste "
                 "COCO val2017 objects cut out along their masks; plain `coco-*` files are the "
                 "original photos. Each image keeps its sources' licenses; one with a CC BY-SA "
                 "source is CC BY-SA.", ""]
        for out, (bg, objects, why) in scenes.items():
            dst = root / "images" / f"{out}.jpg"
            if not objects and isinstance(bg, int) and out.startswith("coco-"):
                dst.write_bytes(coco(bg).read_bytes())
            else:
                frame = background(bg, root)
                for ann_id, region, height in objects:
                    paste(frame, anns[ann_id], region, height)
                cv2.imwrite(str(dst), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            src = [bg] * isinstance(bg, int) + [anns[a]["image_id"] for a, _, _ in objects]
            used = ", ".join(f"{cats[anns[a]['category_id']]} {a} ({r})" for a, r, _ in objects)
            ours = f" Background: `{bg}` (our camera)." if isinstance(bg, str) else ""
            lines.append(f"- `{out}.jpg`: {why}." + (f" Objects: {used}." if used else "") + ours)
            for i in dict.fromkeys(src):
                lic = licenses[images[i]["license"]]
                assert lic["id"] in (4, 5, 7, 8), f"{i}: {lic['name']} does not allow this use"
                lines.append(f"  - COCO {i}: {images[i]['flickr_url']}, {lic['name']} "
                             f"({lic['url']})")
            print(dst)
        (root / "images" / "SOURCES.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("annotations", type=Path)
    main(p.parse_args().annotations)
