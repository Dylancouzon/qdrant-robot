#!/usr/bin/env python3
"""Memory budget: load and exercise each robot component in turn, as the robot does, and report
what it costs: the drop in MemAvailable (CPU and GPU share it on a Jetson), the robot process's
resident (anonymous and file), malloc in-use (CUDA module images loaded at a session's first
run land here), and GPU (nvmap) memory, and llama-server's. Also saves llama-server's buffer
sizes.

    python -m bench.memory_budget [--model qwen3vl-4b] [--server-arg=-ctk --server-arg=q8_0 ...]
        [--cuda-option cudnn_conv_use_max_workspace=0 ...]
"""
import argparse
import ctypes
import json
import os
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from robot import brain
from robot.config import ROOT, SHARED

FRAME = ROOT / "eval/dev/images/coco-000000000139.jpg"


def available_mb() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise RuntimeError("no MemAvailable")


def rss_mb(pid: int | None) -> tuple[int, int]:
    """Resident anonymous memory (GPU buffers included on a Jetson) and resident file pages
    (mapped weights, reclaimable)."""
    if not pid:
        return 0, 0
    kb = dict(line.split()[:2] for line in Path(f"/proc/{pid}/status").read_text().splitlines()
              if line.startswith(("RssAnon:", "RssFile:")))
    return int(kb["RssAnon:"]) // 1024, int(kb["RssFile:"]) // 1024


class _MallInfo2(ctypes.Structure):
    _fields_ = [(f, ctypes.c_size_t) for f in ("arena", "ordblks", "smblks", "hblks", "hblkhd",
                                                "usmblks", "fsmblks", "uordblks", "fordblks",
                                                "keepcost")]


def malloc_mb() -> int:
    """This process's malloc in-use bytes (glibc mallinfo2), all arenas and large blocks."""
    libc = ctypes.CDLL("libc.so.6")
    libc.mallinfo2.restype = _MallInfo2
    info = libc.mallinfo2()
    return (info.uordblks + info.hblkhd) >> 20


def nvmap_mb() -> dict[int, int]:
    """GPU buffers per process (Jetson nvmap; root only, passwordless sudo on the robot)."""
    out = subprocess.run(["sudo", "-n", "cat", "/sys/kernel/debug/nvmap/iovmm/clients"],
                         capture_output=True, text=True, check=True).stdout
    rows = [r.split() for r in out.splitlines()[1:] if r.startswith("user")]
    return {int(r[2]): int(r[3].rstrip("K")) // 1024 for r in rows}


def with_cuda_options(options: dict[str, str]) -> None:
    """Add `options` to every ORT CUDA session this process creates (a what-if, not a default)."""
    make = ort.InferenceSession

    def session(*args, providers=(), **kw):
        providers = [(p[0], {**p[1], **options}) if isinstance(p, tuple) else
                     (p, options) if p == "CUDAExecutionProvider" else p for p in providers]
        return make(*args, providers=providers, **kw)

    ort.InferenceSession = session


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=brain.MODEL, choices=brain.MODELS)
    p.add_argument("--server-arg", action="append", default=[],
                   help="extra llama-server argument (a later flag overrides the robot's)")
    p.add_argument("--cuda-option", action="append", default=[], help="KEY=VALUE")
    a = p.parse_args()
    with_cuda_options(dict(o.split("=", 1) for o in a.cuda_option))
    weights, mmproj, extra = brain.MODELS[a.model]
    brain.MODELS[a.model] = (weights, mmproj, [*extra, *a.server_arg])
    steps, last, server = [], available_mb(), None
    me = os.getpid()

    def mark(name: str) -> None:
        nonlocal last
        now, gpu = available_mb(), nvmap_mb()
        sp = server.proc.pid if server else None
        (ra, rf), (sa, sf) = rss_mb(me), rss_mb(sp)
        row = {"step": name, "mb": last - now, "available_mb": now, "robot_anon_mb": ra,
               "robot_file_mb": rf, "robot_malloc_mb": malloc_mb(), "robot_gpu_mb": gpu.get(me, 0),
               "server_anon_mb": sa, "server_file_mb": sf, "server_gpu_mb": gpu.get(sp, 0)}
        steps.append(row)
        print(json.dumps(row), flush=True)
        last = now

    frame = cv2.imread(str(FRAME))
    mark("start")
    from robot.text_embed import TextEmbedder
    embed = TextEmbedder()
    for k in range(1, 30):
        embed([" ".join(["word"] * k)])
    mark("bge-small (ORT CUDA), 29 lengths")
    from robot.faces import Faces
    faces = Faces()
    for _ in range(5):
        faces.vectors(frame)
    mark("YuNet + face embedder")
    from robot.things import MODEL, Crops
    crops = Crops()
    for k in range(1, 9):
        crops([frame[:200, :200]] * k)
    mark(f"{MODEL.parent.name} crops, batch 1 to 8")
    from robot.detect import Detector
    detect = Detector()
    for _ in range(50):
        detect(frame)
    mark("YOLO detector, 50 frames")
    from robot.asr import Scribe, Vad
    scribe, vad = Scribe(), Vad()  # both stay resident to the final measurement
    for k in range(1, 15):
        speech = np.random.default_rng(k).normal(0, 0.05, 16000 * k).astype(np.float32)
        scribe(speech)
        vad(speech[:512])
    mark("Parakeet int8 + Silero (CPU), 1 to 14 s")
    from robot.tts import Speaker
    voice = Speaker()
    for k in range(1, 40):
        voice.say(" ".join(["word"] * k) + ".")
    mark("Kokoro (ORT CUDA), 39 phrase lengths")
    server = brain.Brain(a.model)
    mark(f"llama-server {a.model} loaded")
    image = brain.jpeg(frame)
    brain_msgs = brain.messages([], image, question="What do you see? Describe everything.")
    "".join(server.answer(brain_msgs, max_tokens=200))
    server.caption(image, lambda: False)
    mark("llama-server after answer and caption")
    log = [line.strip() for line in brain.LOG.read_text().splitlines()
           if "buffer size" in line or "n_ctx" in line or "image_max" in line]
    server.close()
    server = None
    mark("llama-server stopped")
    stamp = f"{time.strftime('%Y-%m-%d')}-memory-{int(time.time())}"
    meta = {"summary": "memory", "model": a.model, "server_args": a.server_arg,
            "cuda_options": a.cuda_option,
            "release": os.environ.get("ROBOT_RELEASE"),
            "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "server_log": log}
    (SHARED / "results" / f"{stamp}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in [meta, *steps]))


if __name__ == "__main__":
    main()
