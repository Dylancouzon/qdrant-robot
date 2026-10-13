"""Compare crop-embedding arms on the viewpoint benchmark and the robot's own camera clip.

Stage 1 (Mac, detector on CPU): run bench/gallery.py's collect() once and keep every crop it
would embed, with a margin of surrounding frame, so arms re-embed identical crops.
    .venv/bin/python bench/embed_arms.py record
    .venv/bin/python bench/embed_arms.py record-robot
    .venv/bin/python bench/embed_arms.py record-mic
    .venv/bin/python bench/embed_arms.py check    (this replay agrees with gallery.replay)
Stage 2 (WSL, GPU, under flock): embed every crop for every arm and condition.
Stage 3 (WSL, CPU): replay the teaching window per arm and write the result JSON.
"""

import pickle
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
EMBED = HERE.parent / "build/detect-quality/embed"
CONTEXT = 0.3  # kept margin around each box, as a fraction of the box's long side


class Tagged(np.ndarray):
    """A box crop that remembers its surrounding frame region."""


def tag_context(original):
    def wrapped(frame, row, box, protos, geometry):
        pair, fill = original(frame, row, box, protos, geometry)
        x1, y1, x2, y2 = (int(v) for v in box)
        h, w = frame.shape[:2]
        m = round(CONTEXT * max(x2 - x1, y2 - y1))
        cx1, cy1, cx2, cy2 = max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m)
        tagged = pair["box"].view(Tagged)
        tagged.context = (frame[cy1:cy2, cx1:cx2].copy(), (x1 - cx1, y1 - cy1, x2 - cx1, y2 - cy1))
        pair["box"] = tagged
        return pair, fill

    return wrapped


class Recorder:
    """Stands in for the encoder: returns each box crop's id and keeps its context region."""

    def __init__(self):
        self.items = []

    def __call__(self, crops):
        ids = []
        for crop in crops:
            context = getattr(crop, "context", None)
            if context is None:  # masked arm, never embedded here
                ids.append(-1)
                continue
            ok, png = cv2.imencode(".png", context[0])
            assert ok
            self.items.append((png.tobytes(), context[1]))
            ids.append(len(self.items) - 1)
        return np.array(ids)


def record():
    import ast
    import json

    import crop_arms
    import gallery
    import onnxruntime as ort

    gallery.OUTPUT = EMBED / "jpg"
    gallery.OUTPUT.mkdir(parents=True, exist_ok=True)
    crop_arms.crops = gallery.crops = tag_context(crop_arms.crops)
    crop_arms.taught_gallery = gallery.taught_gallery = lambda ids: np.asarray(ids)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(gallery.MODEL), options, providers=["CPUExecutionProvider"])
    names = ast.literal_eval(session.get_modelmeta().custom_metadata_map["names"])
    recorder = Recorder()
    protocol = json.loads((gallery.DATA / "d145/cup/protocol.json").read_text())
    instances = [
        gallery.collect(
            gallery.DATA / "d140/external/cup-batch-5-3.avi",
            session,
            recorder,
            names,
            protocol,
            stride=1,
        )
    ]
    paths = sorted((Path.home() / ".cache/objectron").glob("*/video.MOV"))
    assert len(paths) == 16, len(paths)
    instances += [gallery.collect(path, session, recorder, names) for path in paths]
    external, counts, tags = gallery.negatives(session, recorder)
    EMBED.mkdir(parents=True, exist_ok=True)
    with (EMBED / "viewpoint.pkl").open("wb") as f:
        pickle.dump(
            {
                "instances": instances,
                "external": external,
                "tags": tags,
                "counts": counts,
                "contexts": recorder.items,
            },
            f,
        )
    print(len(recorder.items), "crops", counts)


ROBOT_CLIP = HERE.parent / "build/detect-quality/baseline-720p.mjpeg"
STATIC_END = 540  # frame where a person walks in
LATER_S = (0, 1, 5, 15)  # seconds after the taught frame
AVERAGE = (0, 2, 4)  # frames before the later frame that join its average (query averaging)


def record_robot(clip=ROBOT_CLIP, fps=25):
    """Crops of the clip's static objects at taught times and, after each lag, at the lagged frame
    and the frames just before it. The clip is rotated 180 degrees, as the camera hangs."""
    import ast

    import crop_arms
    import onnxruntime as ort
    from robot.config import DETECT_HIGH, OBJECT_MIN_SIDE
    from robot.detect import iou

    crop_arms.crops = tag_context(crop_arms.crops)
    session = ort.InferenceSession(str(crop_arms.MODEL), providers=["CPUExecutionProvider"])
    names = ast.literal_eval(session.get_modelmeta().custom_metadata_map["names"])
    frames = {
        i: cv2.rotate(f, cv2.ROTATE_180) for i, f in crop_arms.frames(clip) if i <= STATIC_END
    }
    recorder, found = Recorder(), {}

    def detections(index):
        if index not in found:
            rows, boxes, protos, geometry = crop_arms.detect(session, frames[index])
            found[index] = (rows, boxes, protos, geometry)
        return found[index]

    def crop_at(index, reference):
        rows, boxes, protos, geometry = detections(index)
        overlap = iou(boxes, np.array([reference]))[:, 0] if len(boxes) else []
        if not len(overlap) or overlap.max() < 0.5:
            return None
        best = int(overlap.argmax())
        pair, _ = crop_arms.crops(frames[index], rows[best], boxes[best], protos, geometry)
        return int(recorder([pair["box"]])[0])

    objects = []
    for start in range(50, STATIC_END - fps * max(LATER_S) + 1, fps // 2):  # every 0.5 s
        rows, boxes, protos, geometry = detections(start)
        for row, box in zip(rows, boxes, strict=True):
            if row[4] < DETECT_HIGH or min(box[2:] - box[:2]) < OBJECT_MIN_SIDE:
                continue
            pair, _ = crop_arms.crops(frames[start], row, box, protos, geometry)
            entry = {
                "label": names[int(row[5])],
                "start": start,
                "box": box.tolist(),
                "taught": int(recorder([pair["box"]])[0]),
                "later": {},
            }
            for lag in LATER_S:
                later = start + lag * fps
                entry["later"][lag] = [crop_at(later - back, box) for back in AVERAGE]
            objects.append(entry)
    EMBED.mkdir(parents=True, exist_ok=True)
    with (EMBED / "robot.pkl").open("wb") as f:
        pickle.dump({"objects": objects, "contexts": recorder.items, "clip": str(clip)}, f)
    print(
        len(objects), "objects", len(recorder.items), "crops", sorted({o["label"] for o in objects})
    )


def record_mic(clip=ROBOT_CLIP, first=50):
    """The taught microphone's box and masked crops in every static frame, found by overlap with
    its first detection. Frames where the detector misses it stay None."""
    import ast

    import crop_arms
    import onnxruntime as ort
    from robot.detect import iou

    crop_arms.crops = tag_context(crop_arms.crops)
    session = ort.InferenceSession(str(crop_arms.MODEL), providers=["CPUExecutionProvider"])
    names = ast.literal_eval(session.get_modelmeta().custom_metadata_map["names"])
    recorder, masked, reference, rows_out = Recorder(), [], None, []
    for index, frame in crop_arms.frames(clip):
        if index > STATIC_END:
            break
        if index < first:
            continue
        frame = cv2.rotate(frame, cv2.ROTATE_180)
        rows, boxes, protos, geometry = crop_arms.detect(session, frame)
        if reference is None:
            mics = [i for i, r in enumerate(rows) if names[int(r[5])] == "microphone"]
            assert mics, "no microphone at the first frame"
            reference = boxes[max(mics, key=lambda i: rows[i, 4])]
            print("microphone box", reference.tolist(), flush=True)
        overlap = iou(boxes, reference[None])[:, 0] if len(boxes) else []
        if not len(overlap) or overlap.max() < 0.3:
            rows_out.append({"frame": index, "box": None, "masked": None})
            continue
        best = int(overlap.argmax())
        pair, fill = crop_arms.crops(frame, rows[best], boxes[best], protos, geometry)
        ok, png = cv2.imencode(".png", pair["masked"])
        masked.append((png.tobytes(), (0, 0, pair["masked"].shape[1], pair["masked"].shape[0])))
        rows_out.append(
            {
                "frame": index,
                "box": int(recorder([pair["box"]])[0]),
                "masked": len(masked) - 1,
                "label": names[int(rows[best, 5])],
                "conf": float(rows[best, 4]),
                "mask_fill": fill,
                "iou": float(overlap[best]),
            }
        )
        if index == first:
            cv2.imwrite(str(EMBED / "mic-first.jpg"), np.hstack([pair["box"], pair["masked"]]))
    with (EMBED / "mic.pkl").open("wb") as f:
        pickle.dump({"frames": rows_out, "box": recorder.items, "masked": masked}, f)
    print(sum(r["box"] is not None for r in rows_out), "of", len(rows_out), "frames detected")


# ---------------------------------------------------------------- stage 2: embedding arms
MODELS = {  # name: (loader, pinned revision, license)
    "dinov2-s": (
        "hf:facebook/dinov2-small",
        "ed25f3a31f01632728cabb09d1542f84ab7b0056",
        "Apache-2.0",
    ),
    "dinov2-reg-s": (
        "hf:facebook/dinov2-with-registers-small",
        "0d9846e56b43a21fa46d7f3f5070f0506a5795a9",
        "Apache-2.0",
    ),
    "dinov2-b": (
        "hf:facebook/dinov2-base",
        "f9e44c814b77203eaa57a6bdbbd535f21ede1415",
        "Apache-2.0",
    ),
    "dinov2-reg-b": (
        "hf:facebook/dinov2-with-registers-base",
        "a1d738ccfa7ae170945f210395d99dde8adb1805",
        "Apache-2.0",
    ),
    "dinov3-s": (
        "timm:timm/vit_small_patch16_dinov3.lvd1689m",
        "3bf4720a82ec2066db88137180ff1f83a675cef0",
        "DINOv3 License (non-OSI)",
    ),
    "dinov3-b": (
        "timm:timm/vit_base_patch16_dinov3.lvd1689m",
        "c6a5fb7d12bbd3cf3b0079253141c3332aaed7da",
        "DINOv3 License (non-OSI)",
    ),
}
POOLS = ("cls", "mean", "cat", "sum")  # cat is the shipped descriptor
MEAN, STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
GRAIN = 7.0  # per-channel sigma of the robot clip's temporal noise (median, static scene)
CONDITIONS = {"clean": 0.0, "grain": GRAIN}


def region(context, margin, shift=(0, 0)):
    """The box crop plus a margin of surrounding frame, with the box moved by `shift`; margin and
    shift are fractions of the box's long side."""
    image, (x1, y1, x2, y2) = context
    long = max(x2 - x1, y2 - y1)
    pad, dx, dy = round(margin * long), round(shift[0] * long), round(shift[1] * long)
    h, w = image.shape[:2]
    return image[
        max(0, y1 + dy - pad) : min(h, y2 + dy + pad), max(0, x1 + dx - pad) : min(w, x2 + dx + pad)
    ]


def degrade(image, sigma, seed):
    if not sigma:
        return image
    noise = np.random.default_rng(seed).normal(0, sigma, image.shape)
    return np.clip(image + noise, 0, 255).round().astype(np.uint8)


def denoise(image, how):
    return {
        "none": lambda i: i,
        "gauss": lambda i: cv2.GaussianBlur(i, (0, 0), 1.0),
        "median": lambda i: cv2.medianBlur(i, 3),
        "nlm": lambda i: cv2.fastNlMeansDenoisingColored(i, None, 7, 7, 5, 15),
    }[how](image)


def resize(image, size, how, patch):
    """pad: square, grey fill (shipped). stretch: square, aspect lost. native: aspect kept,
    sides rounded to the patch size, about size*size pixels."""
    h, w = image.shape[:2]
    if how == "pad":
        s = max(h, w)
        image = cv2.copyMakeBorder(
            image,
            (s - h) // 2,
            s - h - (s - h) // 2,
            (s - w) // 2,
            s - w - (s - w) // 2,
            cv2.BORDER_CONSTANT,
            value=(114,) * 3,
        )
        return cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
    if how == "stretch":
        return cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
    scale = size / max(h, w)
    nh, nw = (max(patch, round(v * scale / patch) * patch) for v in (h, w))
    return cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)


def pools(tokens, patches):
    def norm(v):
        return v / v.norm(dim=1, keepdim=True)

    cls, mean = norm(tokens[:, 0]), norm(tokens[:, -patches:].mean(1))
    return {
        "cls": cls,
        "mean": mean,
        "cat": torch.cat([cls, mean], 1) / 2**0.5,
        "sum": norm(cls + mean),
    }


def load(name):
    kind, repo = MODELS[name][0].split(":")
    revision = MODELS[name][1]
    if kind == "hf":
        from transformers import AutoModel

        model = AutoModel.from_pretrained(repo, revision=revision)
        run = lambda x: model(pixel_values=x).last_hidden_state  # noqa: E731
        patch = model.config.patch_size
    else:
        import timm
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file

        model = timm.create_model(repo.split("/")[1].split(".")[0], pretrained=False)
        model.load_state_dict(
            load_file(hf_hub_download(repo, "model.safetensors", revision=revision))
        )
        run = model.forward_features
        patch = model.patch_embed.patch_size[0]
    return model.eval().cuda(), run, patch


def embed_variant(encoder, items, size, how, margin, clean, seed_offset, sigma, shift=(0, 0)):
    """Return {pool: (N, D) array} for all crops under one preprocessing. The noise is drawn once
    per crop over its whole frame region, so every shift of one crop sees the same grain."""
    model, run, patch = encoder
    shapes = {}
    for i, (image, box) in enumerate(items):
        image = region((degrade(image, sigma, seed_offset + i), box), margin, shift)
        image = denoise(image, clean)
        image = resize(image, size, how, patch)[..., ::-1] / 255.0
        shapes.setdefault(image.shape[:2], []).append(
            (i, ((image - MEAN) / STD).astype(np.float32).transpose(2, 0, 1))
        )
    out = {pool: None for pool in POOLS}
    with torch.no_grad():
        for shape, group in shapes.items():
            for start in range(0, len(group), 64):
                batch = group[start : start + 64]
                x = torch.from_numpy(np.stack([g[1] for g in batch])).cuda()
                result = pools(run(x), (shape[0] // patch) * (shape[1] // patch))
                for pool, value in result.items():
                    if out[pool] is None:
                        out[pool] = np.zeros((len(items), value.shape[1]), np.float32)
                    out[pool][[g[0] for g in batch]] = value.float().cpu().numpy()
    return out


def decode(contexts):
    return [
        (cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR), box) for png, box in contexts
    ]


# variant: (model, size, resize, margin, denoise); the shipped descriptor is the first
SHIPPED = ("dinov2-s", 224, "pad", 0.0, "none")
VARIANTS = [
    SHIPPED,
    ("dinov2-reg-s", 224, "pad", 0.0, "none"),
    ("dinov2-b", 224, "pad", 0.0, "none"),
    ("dinov2-reg-b", 224, "pad", 0.0, "none"),
    ("dinov3-s", 224, "pad", 0.0, "none"),
    ("dinov3-b", 224, "pad", 0.0, "none"),
    ("dinov2-s", 224, "pad", 0.1, "none"),
    ("dinov2-s", 224, "pad", 0.2, "none"),
    ("dinov3-s", 224, "pad", 0.1, "none"),
    ("dinov3-s", 224, "pad", 0.2, "none"),
    ("dinov3-b", 224, "pad", 0.1, "none"),
    ("dinov2-b", 224, "pad", 0.1, "none"),
    ("dinov2-b", 224, "pad", 0.2, "none"),
    ("dinov2-s", 336, "pad", 0.0, "none"),
    ("dinov2-s", 448, "pad", 0.0, "none"),
    ("dinov2-s", 224, "stretch", 0.0, "none"),
    ("dinov2-s", 224, "native", 0.0, "none"),
    ("dinov2-s", 224, "pad", 0.0, "gauss"),
    ("dinov2-s", 224, "pad", 0.0, "median"),
    ("dinov2-s", 224, "pad", 0.0, "nlm"),
]
JITTER = ((0.06, 0), (-0.06, 0), (0, 0.06), (0, -0.06))  # box shifts, fraction of long side
AUGMENT = [SHIPPED, ("dinov3-s", 224, "pad", 0.0, "none"), ("dinov2-b", 224, "pad", 0.0, "none")]


def embed(variants=None):
    """Embed viewpoint and robot crops for each variant, pool, and condition into emb/*.npz."""
    global torch
    import torch

    viewpoint = pickle.loads(Path("viewpoint.pkl").read_bytes())["contexts"]
    robot = pickle.loads(Path("robot.pkl").read_bytes())["contexts"]
    sets = {"viewpoint": decode(viewpoint), "robot": decode(robot)}
    encoders = {}
    for variant in variants or VARIANTS:
        name, size, how, margin, clean = variant
        if name not in encoders:
            encoders = {name: load(name)}  # one model resident at a time
        for condition, sigma in CONDITIONS.items():
            target = f"emb/{'_'.join(map(str, variant))}_{condition}.npz"
            if Path(target).exists():
                continue
            started, tables = time.time(), {}
            for source, items in sets.items():
                seed = 0 if source == "viewpoint" else 10**6
                got = embed_variant(encoders[name], items, size, how, margin, clean, seed, sigma)
                for pool, table in got.items():
                    tables[f"{source}_{pool}"] = table
            np.savez(target, **tables)
            print(variant, condition, f"{time.time() - started:.1f}s", flush=True)
            if variant in AUGMENT:  # teaching-time jitter: the same crops with the box moved
                shifted = [
                    embed_variant(
                        encoders[name], sets["viewpoint"], size, how, margin, clean, 0, sigma, shift
                    )
                    for shift in JITTER
                ]
                np.savez(
                    target.replace("emb/", "emb/aug_"),
                    **{
                        f"viewpoint_{pool}": np.stack([s_[pool] for s_ in shifted])
                        for pool in POOLS
                    },
                )


def embed_mic():
    """Embed the microphone's box and masked crops for every variant into emb/mic_*.npz."""
    global torch
    import torch

    mic = pickle.loads(Path("mic.pkl").read_bytes())
    sets = {"box": decode(mic["box"]), "masked": decode(mic["masked"])}
    encoders = {}
    for variant in VARIANTS:
        name, size, how, margin, clean = variant
        if name not in encoders:
            encoders = {name: load(name)}
        tables = {}
        for source, items in sets.items():
            for pool, table in embed_variant(
                encoders[name], items, size, how, margin, clean, 0, 0.0
            ).items():
                tables[f"{source}_{pool}"] = table
        np.savez(f"emb/mic_{'_'.join(map(str, variant))}.npz", **tables)
        print(variant, flush=True)


# ---------------------------------------------------------------- stage 3: teaching-window replay
BASE = 0.822  # shipped match; the other admission settings scale with each arm's threshold
CAP = 24
FALSE_BUDGETS = (0, 41, 116, 300)  # 41: fixed galleries, 116: shipped teaching window (D154)
GRID = np.round(np.arange(0.60, 0.9851, 0.005), 3)


def affine(threshold):
    """Map a shipped setting on the 0.822 scale to an arm whose match is `threshold`.

    1.0 stays 1.0."""
    k = (1 - threshold) / (1 - BASE)
    return lambda x: 1 - (1 - x) * k


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def taught(ids, table, duplicate, aug=None):
    """The runtime's add_vectors: skip a view too close to a kept one, cap at 24 views keeping the
    first. A view with jittered copies keeps them in a block that goes with it."""
    views = []
    for i in ids:
        if views and max(v[0] @ table[i] for v in views) >= duplicate:
            continue
        views.append(block(i, table, aug))
    while len(views) > CAP:
        views.pop(1)
    return views


def block(i, table, aug):
    return table[i][None] if aug is None else np.vstack([table[i], aug[:, i]])


def replay(
    instance, table, query, pool, threshold, aug=None, floor=None, duplicate=None, stats=None
):
    """gallery.replay's 'track' policy on one arm's vectors. `table` feeds the taught gallery and
    admissions; `query` feeds the scored frames and the distractors; `aug` holds each crop's
    jittered copies. `floor` and `duplicate` default to the shipped 0.70 and 0.95 mapped onto the
    arm's `threshold`; `stats` counts the teaching candidates. Returns the later frames' scores
    (None: nothing detected) and each distractor's best score."""
    f = affine(threshold)
    floor, duplicate = (
        f(0.70) if floor is None else floor,
        f(0.95) if duplicate is None else duplicate,
    )
    views = taught(instance["galleries"]["box"], table, duplicate, aug)
    gallery = np.vstack(views)
    last = instance["teaching_frame"] / instance["fps"]
    positive = []
    for record in instance["records"]:
        candidate = record.get("track_crop")
        if record["frame"] > instance["teaching_half_end_frame"]:
            vectors = record["vectors"]
            positive.append(
                None if vectors is None else float(np.max(gallery @ query[vectors["box"]]))
            )
        elif candidate is not None and candidate["vectors"] is not None:
            i = candidate["vectors"]["box"]
            score, now = float(np.max(gallery @ table[i])), record["frame"] / instance["fps"]
            if not candidate["ambiguous"] and now - last >= 1:
                if stats is not None:
                    stats["eligible"] += 1
                    stats["skipped"] += score >= duplicate
                    stats["admitted"] += floor <= score < duplicate
                if floor <= score < duplicate:
                    if len(views) == CAP:
                        views.pop(1)
                    views.append(block(i, table, aug))
                    gallery, last = np.vstack(views), now
    return positive, np.max(query[pool] @ gallery.T, axis=1), len(gallery)


INSTANCES, POOLS_ = [], []  # set by score() before the workers fork


def benchmark():
    """The 17 recorded instances with their distractor pools and each pool entry's category."""
    import gallery

    data = pickle.loads((EMBED / "viewpoint.pkl").read_bytes())
    instances = data["instances"]
    pools = []
    for instance in instances:
        ids, same, tags = gallery.distractors(
            instance, instances, data["external"], "box", data["tags"]
        )
        external = np.array([t["source"] in ("negatives", "coco") for t in tags])
        pools.append((ids, external, same))
    return instances, pools


def averaged(table, instances, k):
    """Each frame's vector becomes the mean of itself and the k-1 earlier detections (the last
    three frames at the robot's cadence); stills (external negatives) stay as they are."""
    out = table.copy()
    for instance in instances:
        ids = [r["vectors"]["box"] for r in instance["records"] if r["vectors"] is not None]
        step = max(1, 3 // instance["stride"])
        for j, i in enumerate(ids):
            out[i] = unit(table[ids[max(0, j - step * (k - 1)) : j + 1 : step]].mean(0))
    return out


def sweep(instances, pools, table, query, aug=None):
    """Rows of (threshold, recognized, scored, false on external, other kind, same kind)."""
    rows = []
    for threshold in GRID:
        hits = total = 0
        false = np.zeros(3, int)
        for instance, (pool, external, same) in zip(instances, pools, strict=True):
            positive, final, _ = replay(instance, table, query, pool, threshold, aug)
            hits += sum(s is not None and s >= threshold for s in positive)
            total += len(positive)
            over = final >= threshold
            false += [
                (over & external).sum(),
                (over & ~external & ~same).sum(),
                (over & same).sum(),
            ]
        rows.append([threshold, hits, total, *false])
    return np.array(rows)


def per_instance(table, query, threshold, aug=None):
    """(name, recognized, scored, false matches) for each instance at one threshold."""
    out = []
    for instance, (pool, _, _) in zip(INSTANCES, POOLS_, strict=True):
        positive, final, _ = replay(instance, table, query, pool, threshold, aug)
        out.append(
            [
                instance["name"],
                sum(s is not None and s >= threshold for s in positive),
                len(positive),
                int((final >= threshold).sum()),
            ]
        )
    return out


def matched(rows, budget):
    """The lowest threshold whose false matches stay within the budget: (threshold, hits, false)."""
    ok = [r for r in rows if r[3:].sum() <= budget]
    return [float(ok[0][0]), int(ok[0][1]), int(ok[0][3:].sum())] if ok else None


def self_check(instances, pools):
    """gallery.replay, fed the shipped DINOv3 vectors and defaults, agrees with this replay."""
    import gallery
    from robot.settings import DEFAULTS

    match = DEFAULTS["match"]

    table = np.load(EMBED / "emb/dinov3-s_224_pad_0.0_none_clean.npz")["viewpoint_cat"]

    def vectors(record):
        if record is None or record["vectors"] is None:
            return record
        return {**record, "vectors": {"box": table[record["vectors"]["box"]]}}

    class Sink:
        write = staticmethod(lambda _: None)

    for instance, (pool, _external, same) in zip(instances, pools, strict=True):
        copy = {
            **instance,
            "records": [
                {**vectors(r), "track_crop": vectors(r.get("track_crop"))}
                for r in instance["records"]
            ],
            "galleries": {
                "box": np.vstack(taught(instance["galleries"]["box"], table, DEFAULTS["duplicate"]))
            },
        }
        row, _, _, _ = gallery.replay("track", copy, table[pool], same, [{}] * len(pool), Sink)
        positive, final, _ = replay(
            instance,
            table,
            table,
            pool,
            match,
            floor=DEFAULTS["window_floor"],
            duplicate=DEFAULTS["duplicate"],
        )
        mine = (sum(s is not None and s >= match for s in positive), int((final >= match).sum()))
        assert mine == (row["hits"], row["false_matches"]), (instance["name"], mine, row)
        print(instance["name"], "agrees:", mine, flush=True)


LAGS = (1, 5, 15)


def stability(robot, table, threshold, k):
    """How an object's crop holds up on the robot's grainy clip: cosine of the taught crop to the
    same object's crop `lag` seconds later (the mean of k frames), and to the best other object in
    the same scene. `ratio` is the self distance over the threshold distance, so below 1 the
    object is recognized, and it compares across arms with different cosine scales."""
    from robot.detect import iou

    objects, out = robot["objects"], {}
    for lag in LAGS:
        self_, other, ratio = [], [], []
        for o in objects:
            later = [i for i in o["later"][lag][:k] if i is not None]
            if o["later"][lag][0] is None:
                continue
            taught_vector = table[o["taught"]]
            self_.append(float(taught_vector @ unit(table[later].mean(0))))
            ratio.append((1 - self_[-1]) / (1 - threshold))
            rivals = [
                p
                for p in objects
                if p["start"] == o["start"]
                and p["later"][lag][0] is not None
                and iou(np.array([p["box"]]), np.array([o["box"]]))[0, 0] < 0.5
            ]
            if rivals:
                other.append(max(float(taught_vector @ table[p["later"][lag][0]]) for p in rivals))
        out[lag] = {
            "n": len(self_),
            "self_mean": float(np.mean(self_)),
            "other_max_mean": float(np.mean(other)) if other else None,
            "other_over_threshold": float(np.mean(np.array(other) >= threshold)),
            "recognized": float(np.mean(np.array(ratio) <= 1)),
            "ratio_median": float(np.median(ratio)),
        }
    return out


def score_file(path):
    """All (average, gallery averaging, jitter) settings for one embedded arm and condition."""
    *variant, condition = path.stem.split("_")
    tables = np.load(path)
    robot_tables = np.load(str(path).replace(f"_{condition}.npz", "_clean.npz"))
    augmented = path.with_name("aug_" + path.name)
    jitter = np.load(augmented) if augmented.exists() else None
    out = []
    for pool in POOLS:
        table = tables[f"viewpoint_{pool}"]
        settings = [(1, False, None), (2, False, None), (3, False, None), (3, True, None)]
        if jitter is not None:
            settings += [
                (1, False, jitter[f"viewpoint_{pool}"]),
                (3, False, jitter[f"viewpoint_{pool}"]),
            ]
        for k, both, aug in settings:
            query = averaged(table, INSTANCES, k) if k > 1 else table
            rows = sweep(INSTANCES, POOLS_, query if both else table, query, aug)
            point = matched(rows, 116)
            entry = {
                "variant": variant,
                "pool": pool,
                "condition": condition,
                "average": k,
                "gallery_average": both,
                "jitter": aug is not None,
                "matched": {str(b): matched(rows, b) for b in (0, 10, *FALSE_BUDGETS)},
                "false_split_at_116": rows[rows[:, 0] == point[0]][0][3:].tolist()
                if point
                else None,
                "curve": [[float(r[0]), int(r[1]), int(r[3:].sum())] for r in rows[::4]],
            }
            if point:
                entry["instances_at_116"] = per_instance(
                    query if both else table, query, point[0], aug
                )
                entry["robot"] = stability(ROBOT, robot_tables[f"robot_{pool}"], point[0], k)
            out.append(entry)
    return out


def score():
    """Matched-false-match recognition and robot-clip stability for every embedded arm."""
    import json
    import multiprocessing

    global INSTANCES, POOLS_, ROBOT
    INSTANCES, POOLS_ = benchmark()
    ROBOT = pickle.loads((EMBED / "robot.pkl").read_bytes())
    pattern = sys.argv[2] if len(sys.argv) > 2 else "*.npz"
    paths = [
        p for p in sorted((EMBED / "emb").glob(pattern)) if not p.name.startswith(("aug_", "mic_"))
    ]
    with multiprocessing.get_context("fork").Pool(8) as workers:
        results = [e for chunk in workers.imap(score_file, paths) for e in chunk]
    import hashlib
    import platform
    import shlex
    import subprocess

    provenance = json.loads((EMBED / "emb/provenance.json").read_text())
    target = HERE / f"results/2026-10-12-embed-{int(time.time())}.json"
    target.write_text(
        json.dumps(
            {
                "code_revision": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "source_sha256": {
                    "bench/embed_arms.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
                },
                "command": shlex.join([sys.executable, *sys.argv]),
                "scoring_machine": {
                    "label": "E",
                    "platform": platform.platform(),
                    "numpy": np.__version__,
                },
                "embedding": provenance,
                "models": {
                    name: {"source": m[0], "revision": m[1], "license": m[2]}
                    for name, m in MODELS.items()
                },
                "limits": {
                    "base_match": BASE,
                    "false_budgets": [0, 10, *FALSE_BUDGETS],
                    "views_cap": CAP,
                    "grain_sigma": GRAIN,
                    "jitter": JITTER,
                    "average_spacing": "3 source frames",
                    "scored_views": 816,
                    "distractor_comparisons": 36918,
                    "recorded_baseline_2026_10_11": {"recognized": 530, "false": 116},
                },
                "notes": [
                    "Admission floor, duplicate and cap settings scale with each arm's "
                    "threshold so that the teaching window stays the same policy "
                    "(affine map fixing 1.0).",
                    "Rerunning the grain condition redraws the noise: baseline moves by about 10 "
                    "recognized views. Differences under about 15 views are noise.",
                    "Every shipped-arm false match is a same-kind lookalike pair (two cameras, two "
                    "cups); a few galleries hold most of them.",
                ],
                "entries": results,
            }
        )
        + "\n"
    )
    print(target)


OLD = {"match": 0.822, "band_floor": 0.772, "window_floor": 0.70, "duplicate": 0.95, "same": 0.86}
THRESHOLDS = np.round(np.arange(0.60, 0.9901, 0.001), 3)


def window_stats(arm, floor, duplicate):
    """Teaching-window candidates, skips, and admissions, with every later and distractor score."""
    table = np.load(EMBED / f"emb/{arm}_224_pad_0.0_none_clean.npz")["viewpoint_cat"]
    stats = {"eligible": 0, "skipped": 0, "admitted": 0}
    positive, final = [], []
    for instance, (pool, _, _) in zip(INSTANCES, POOLS_, strict=True):
        p, f, _ = replay(instance, table, table, pool, OLD["match"], None, floor, duplicate, stats)
        positive += [s for s in p if s is not None]
        final.append(f)
    return stats, np.array(positive), np.concatenate(final)


def lowest_within(threshold_counts, budget):
    """The lowest threshold whose count stays within the budget."""
    return float(next(t for t, c in threshold_counts if c <= budget))


def same_pairs(arm):
    """MaxSim scores of the taught crops against three later crops of the same instance, and
    against three crops of every other instance of its kind (lookalikes, a few windows each)."""
    table = np.load(EMBED / f"emb/{arm}_224_pad_0.0_none_clean.npz")["viewpoint_cat"]

    def windows(ids, most):
        triples = [ids[i : i + 3] for i in range(0, len(ids) - 2, 3)]
        return (
            [
                triples[i]
                for i in np.linspace(0, len(triples) - 1, min(most, len(triples)), dtype=int)
            ]
            if triples
            else []
        )

    def maxsim(a, b):
        return float((table[a] @ table[b].T).max(axis=1).mean())

    same, lookalike = [], []
    for a in INSTANCES:
        taught_ids = [int(i) for i in a["galleries"]["box"]]
        later = [
            r["vectors"]["box"]
            for r in a["records"]
            if r["frame"] > a["teaching_half_end_frame"] and r["vectors"] is not None
        ]
        # The robot's direction: each crop held now takes its best match among the earlier ones.
        same += [maxsim(w, taught_ids) for w in windows(later, 1000)]
        for b in INSTANCES:
            if b is not a and b["kind"] == a["kind"]:
                lookalike += [
                    maxsim(w, taught_ids)
                    for w in windows(
                        [g["vectors"]["box"] for g in b["ground_truth"] if g["vectors"]], 6
                    )
                ]
    return np.array(same), np.array(lookalike)


def calibrate():
    """DINOv3's match, guess_band, window_floor, duplicate, and same, each at DINOv2's operating
    point on the viewpoint benchmark (clean crops), written to
    results/2026-10-12-dinov3-calibration."""
    import json

    global INSTANCES, POOLS_
    INSTANCES, POOLS_ = benchmark()
    old, new = "dinov2-s", "dinov3-s"
    ref_stats, ref_positive, ref_final = window_stats(old, OLD["window_floor"], OLD["duplicate"])
    rates = {k: ref_stats[k] / ref_stats["eligible"] for k in ("skipped", "admitted")}
    # The floor never binds on a teaching window (no DINOv2 candidate scores under 0.70), so its
    # admission rate is the duplicate's complement. The floor is set by the distractor scores it
    # lets through, as match and guess_band are: the DINOv2 count at 0.70.
    passed = int((ref_final >= OLD["window_floor"]).sum())
    guess = affine(0.80)  # a start; the loop below moves both settings
    floor, duplicate = guess(0.70), guess(0.95)
    grid = np.round(np.arange(0.80, 0.995, 0.001), 3)
    for _ in range(3):
        runs = [window_stats(new, floor, d)[0] for d in grid]
        miss = [abs(r["skipped"] / r["eligible"] - rates["skipped"]) for r in runs]
        duplicate = float(grid[int(np.argmin(miss))])
        _, _, final = window_stats(new, floor, duplicate)
        floor = lowest_within([(t, int((final >= t).sum())) for t in THRESHOLDS], passed)
    stats, positive, final = window_stats(new, floor, duplicate)

    def counts(positive, final, thresholds):
        return [(float(t), int((final >= t).sum()), int((positive >= t).sum())) for t in thresholds]

    ref = {t: counts(ref_positive, ref_final, [t])[0] for t in (OLD["match"], OLD["band_floor"])}
    curve = counts(positive, final, THRESHOLDS)
    match = lowest_within([(t, c) for t, c, _ in curve], ref[OLD["match"]][1])
    low = lowest_within([(t, c) for t, c, _ in curve], ref[OLD["band_floor"]][1])
    at = {t: c for t, *c in curve}
    old_same, old_lookalike = same_pairs(old)
    new_same, new_lookalike = same_pairs(new)
    false_same = int((old_lookalike >= OLD["same"]).sum())
    same = lowest_within([(t, int((new_lookalike >= t).sum())) for t in THRESHOLDS], false_same)
    import shlex
    import subprocess

    result = {
        "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "command": shlex.join([sys.executable, *sys.argv]),
        "machine": "Mac, CPU (E)",
        "arms": {
            old: "viewpoint embeddings of the clean condition, pool cat, average 1",
            new: "same crops, same pool",
        },
        "operating_points_dinov2": OLD,
        "dinov2": {
            "window": ref_stats,
            "rates": rates,
            "false_and_recognized_at_match": ref[OLD["match"]][1:],
            "false_and_recognized_at_band_floor": ref[OLD["band_floor"]][1:],
            "scored_views": len(ref_positive),
        },
        "dinov3": {
            "window_floor": floor,
            "distractors_over_floor": [passed, int((final >= floor).sum())],
            "duplicate": duplicate,
            "window": stats,
            "rates": {k: stats[k] / stats["eligible"] for k in ("skipped", "admitted")},
            "match": match,
            "match_false_recognized": at[match],
            "guess_band": round(match - low, 3),
            "band_floor": low,
            "band_floor_false_recognized": at[low],
            "same": same,
            "scored_views": len(positive),
            "affine_for_comparison": {
                "window_floor": round(affine(match)(0.70), 3),
                "duplicate": round(affine(match)(0.95), 3),
            },
        },
        "same_pairs": {
            "same_windows": len(old_same),
            "lookalike_windows": len(old_lookalike),
            "dinov2": {
                "false_same_at_0.86": false_same,
                "same_recognized_at_0.86": int((old_same >= OLD["same"]).sum()),
                "lookalike_max": float(old_lookalike.max()),
                "same_p10": float(np.percentile(old_same, 10)),
            },
            "dinov3": {
                "false_same_at_new": int((new_lookalike >= same).sum()),
                "same_recognized_at_new": int((new_same >= same).sum()),
                "lookalike_max": float(new_lookalike.max()),
                "same_p10": float(np.percentile(new_same, 10)),
            },
        },
        "false_budget_note": "false counts sum the distractor comparisons of 17 final galleries",
    }
    target = HERE / "results/2026-10-12-dinov3-calibration.json"
    target.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


TEACH_SHOTS = (50, 58, 67)  # three crops a third of a second apart (runtime SHOTS)
WINDOW_END = 200  # teaching window of 6 s after the first shot, one admission per second


def mic_run(ids, table, threshold, k, window=True):
    """Teach on the first seconds, then score every later frame. `ids` maps frame to row of
    `table` (missing: the detector lost the object). Returns per-frame scores, None when lost."""
    f = affine(threshold)
    views = taught([ids[t] for t in TEACH_SHOTS], table, f(0.95))
    gallery, last = np.vstack(views), TEACH_SHOTS[0] / 25
    out = []
    for frame in range(TEACH_SHOTS[0], STATIC_END + 1):
        if frame not in ids:
            if frame > WINDOW_END:
                out.append(None)
            continue
        if frame <= WINDOW_END:
            now, v = frame / 25, table[ids[frame]]
            score = float(np.max(gallery @ v))
            if window and now - last >= 1 and f(0.70) <= score < f(0.95):
                if len(views) == CAP:
                    views.pop(1)
                views.append(v[None])
                gallery, last = np.vstack(views), now
            continue
        behind = [table[ids[t]] for t in (frame, frame - 2, frame - 4)[:k] if t in ids]
        out.append(float(np.max(gallery @ unit(np.mean(behind, 0)))))
    return out


def mic_stats(scores, threshold):
    """Fraction of frames the box would not show, and how often it flips per minute."""
    shown = np.array([s is not None and s >= threshold for s in scores])
    found = [s for s in scores if s is not None]
    return {
        "frames": len(scores),
        "lost": len(scores) - len(found),
        "below": int(sum(s < threshold for s in found)),
        "not_shown": float(1 - shown.mean()),
        "flips_per_min": float((shown[1:] != shown[:-1]).sum() / (len(scores) / 25 / 60)),
        "score_p5": float(np.percentile(found, 5)),
        "score_p50": float(np.percentile(found, 50)),
    }


def mic():
    """The taught microphone on the arm, per frame, for every arm.

    python embed_arms.py mic RESULTS."""
    import json

    mic_data = pickle.loads((EMBED / "mic.pkl").read_bytes())
    results = json.loads(Path(sys.argv[2]).read_text())["entries"]
    out = []
    for path in sorted((EMBED / "emb").glob("mic_*.npz")):
        variant = path.stem[4:].split("_")
        tables = np.load(path)
        for source in ("box", "masked"):
            ids = {r["frame"]: r[source] for r in mic_data["frames"] if r[source] is not None}
            for pool in ("cat", "sum"):
                table = tables[f"{source}_{pool}"]
                for k in (1, 2, 3):
                    match = next(
                        (
                            e["matched"]["116"]
                            for e in results
                            if e["variant"] == variant
                            and e["pool"] == pool
                            and e["condition"] == "clean"
                            and e["average"] == k
                            and not e["jitter"]
                            and not e["gallery_average"]
                        ),
                        None,
                    )
                    if match is None:
                        continue
                    threshold = match[0]
                    row = {
                        "variant": variant,
                        "crop": source,
                        "pool": pool,
                        "average": k,
                        "threshold": threshold,
                    }
                    row["window"] = mic_stats(mic_run(ids, table, threshold, k), threshold)
                    row["three_shots"] = mic_stats(
                        mic_run(ids, table, threshold, k, False), threshold
                    )
                    out.append(row)
    target = HERE / f"results/2026-10-12-embed-mic-{int(time.time())}.json"
    target.write_text(
        json.dumps(
            {
                "source_results": sys.argv[2],
                "clip": str(ROBOT_CLIP),
                "teach_frames": TEACH_SHOTS,
                "window_end": WINDOW_END,
                "scored_frames": [WINDOW_END + 1, STATIC_END],
                "rows": out,
            }
        )
        + "\n"
    )
    print(target)


if __name__ == "__main__":
    {
        "record": record,
        "record-robot": record_robot,
        "record-mic": record_mic,
        "embed": embed,
        "embed-mic": embed_mic,
        "mic": mic,
        "check": lambda: self_check(*benchmark()),
        "score": score,
        "calibrate": calibrate,
    }[sys.argv[1]]()
