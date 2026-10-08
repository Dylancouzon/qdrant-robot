#!/usr/bin/env python3
"""TTS bench: Kokoro synthesis time for short, medium, and long phrases on one ORT provider.

    python -m bench.tts_bench --provider cuda|tensorrt
"""
import argparse
import json
import os
import statistics
import time

import onnxruntime as ort
from kokoro_onnx import Kokoro

from robot.config import MODELS, SHARED
from robot.tts import RATE, VOICE

PHRASES = ["Two cats.", "You're holding up a stop sign.",
           "Qdrant Edge is the embedded version of Qdrant, running inside my own process.",
           "That looks like an old custom motorcycle, with a long front fork and two fat tires at "
           "the back."]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=["cuda", "tensorrt"], default="cuda")
    a = p.parse_args()
    cuda = ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"})
    providers = [cuda] if a.provider == "cuda" else [
        ("TensorrtExecutionProvider", {"trt_fp16_enable": True, "trt_engine_cache_enable": True,
                                       "trt_engine_cache_path": str(SHARED / "trt-cache")}), cuda]
    t = time.perf_counter()
    sess = ort.InferenceSession(str(MODELS / "kokoro/kokoro-v1.0.onnx"), providers=providers)
    kokoro = Kokoro.from_session(sess, str(MODELS / "kokoro/voices-v1.0.bin"))
    for text in PHRASES * 2:  # warm-up, including engine builds for new shapes
        kokoro.create(text, voice=VOICE, lang="en-us")
    print(f"load and warm-up {time.perf_counter() - t:.1f} s")
    rows = []
    for text in PHRASES:
        times = []
        for _ in range(3):
            t = time.perf_counter()
            pcm, _ = kokoro.create(text, voice=VOICE, lang="en-us")
            times.append(time.perf_counter() - t)
        rows.append({"words": len(text.split()), "audio_s": len(pcm) / RATE,
                     "synth_s": statistics.median(times)})
        print(json.dumps(rows[-1]))
    print(json.dumps({"provider": a.provider, "release": os.environ.get("ROBOT_RELEASE"),
                      "rtf": statistics.mean(r["synth_s"] / r["audio_s"] for r in rows)}))


if __name__ == "__main__":
    main()
