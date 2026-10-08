#!/usr/bin/env python3
"""Memory budget: load each robot component in turn and report how much MemAvailable drops
(CPU and GPU share it on a Jetson), then exercise TTS and ASR with varied inputs and report
the growth.

    python -m bench.memory_budget
"""
import json
import os
import time
from pathlib import Path

import numpy as np

from robot.config import SHARED


def available_mb() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise RuntimeError("no MemAvailable")


def main() -> None:
    steps, last = [], available_mb()

    def mark(name: str) -> None:
        nonlocal last
        now = available_mb()
        steps.append({"step": name, "mb": last - now, "available_mb": now})
        print(f"{name:32} {last - now:6d} MB   available {now} MB", flush=True)
        last = now

    mark("start")
    from robot.text_embed import TextEmbedder
    embed = TextEmbedder()
    embed(["warm up"])
    mark("bge-small (ORT CUDA)")
    from robot.tts import Speaker
    voice = Speaker()
    mark("Kokoro (ORT CUDA)")
    from robot.asr import Scribe, Vad
    scribe = Scribe()
    Vad()
    mark("Parakeet int8 + Silero (CPU)")
    from robot.brain import Brain
    brain = Brain()
    mark("llama-server Qwen3-VL-2B")
    for k in range(1, 40):
        voice.say(" ".join(["word"] * k) + ".")
    mark("Kokoro after 39 phrase lengths")
    for k in range(1, 15):
        scribe(np.random.default_rng(k).normal(0, 0.05, 16000 * k).astype(np.float32))
    mark("Parakeet after 1 to 14 s inputs")
    brain.close()
    mark("llama-server stopped")
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-memory-{int(time.time())}.jsonl"
    out.write_text("".join(json.dumps({**s, "release": os.environ.get("ROBOT_RELEASE")}) + "\n"
                           for s in steps))


if __name__ == "__main__":
    main()
