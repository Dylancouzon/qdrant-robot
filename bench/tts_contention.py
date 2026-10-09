#!/usr/bin/env python3
"""Kokoro first-phrase latency for 2, 5, and 10 words: warm and alone, first call after
idle, and while llama-server decodes a long answer (as in a turn), with and without the
detector at 15 fps, and with both CPU clusters held at full clock by one busy process each
(schedutil drops them to 729 MHz while the GPU does the work).

    python -m bench.tts_contention [--reps 20] [--idle 15]
"""
import argparse
import json
import math
import os
import statistics
import subprocess
import threading
import time
from pathlib import Path

import cv2

from robot.brain import Brain
from robot.config import ROOT, SHARED
from robot.detect import Detector
from robot.tts import Speaker

PHRASES = {2: "Two cats.", 5: "I see a black chair.",
           10: "Qdrant Edge runs inside my own process, right on this board."}
GPU_FREQ = Path("/sys/class/devfreq/17000000.gpu/cur_freq")
CPU_FREQ = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
FRAME = ROOT / "eval/dev/images/coco-000000000139.jpg"


def pct(xs: list[float], q: float) -> float:
    """Nearest-rank percentile."""
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, math.ceil(q * len(xs)) - 1))]


def decode_forever(brain: Brain, stop: threading.Event, tokens: list[int]) -> None:
    """Stream long text-only answers until `stop`, counting streamed chunks."""
    body = {"messages": [{"role": "user", "content": "Tell a very long story about a robot."}],
            "max_tokens": 1500, "stream": True, "ignore_eos": True}
    while not stop.is_set():
        with brain._post(body) as r:
            for raw in r:
                tokens[0] += raw.startswith(b"data: ")
                if stop.is_set():
                    break


def detect_forever(stop: threading.Event) -> None:
    """The robot's detector at its 15 fps cadence, in this process as in the robot."""
    detect, frame, due = Detector(), cv2.imread(str(FRAME)), time.time()
    while not stop.is_set():
        detect(frame)
        due = max(due + 1 / 15, time.time())
        time.sleep(max(0.0, due - time.time()))
    detect.close()


def timed(voice: Speaker, text: str) -> dict:
    t = time.perf_counter()
    voice.kokoro.tokenizer.phonemize(text, "en-us")
    phon = time.perf_counter() - t
    gpu, cpu = int(GPU_FREQ.read_text()) // 1000_000, int(CPU_FREQ.read_text()) // 1000
    t = time.perf_counter()
    voice.say(text)
    return {"synth_s": time.perf_counter() - t, "phonemize_s": phon, "gpu_mhz": gpu,
            "cpu0_mhz": cpu}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reps", type=int, default=20)
    p.add_argument("--idle", type=float, default=15.0, help="seconds idle before a cold call")
    a = p.parse_args()
    rows: list[dict] = []

    def measure(cond: str, reps: int, gap: float) -> None:
        for words, text in PHRASES.items():
            for _ in range(reps):
                time.sleep(gap)
                rows.append({"cond": cond, "words": words, **timed(voice, text)})

    voice = Speaker()
    for text in PHRASES.values():  # every shape seen once
        voice.say(text)
    measure("alone-warm", a.reps, 0.05)
    measure("alone-after-idle", 3, a.idle)
    brain = Brain()
    measure("server-idle", a.reps, 0.05)
    stop, tokens = threading.Event(), [0]
    worker = threading.Thread(target=decode_forever, args=(brain, stop, tokens), daemon=True)
    worker.start()
    time.sleep(2)  # decode in full swing
    t, n = time.perf_counter(), tokens[0]
    measure("during-decode", a.reps, 0.3)
    rate = (tokens[0] - n) / (time.perf_counter() - t)
    # ponytail: one busy process per CPU cluster (cores 0-3, 4-5) stands in for a pinned clock
    spin = [subprocess.Popen(["taskset", "-c", c, "sh", "-c", "while :; do :; done"])
            for c in ("3", "5")]
    time.sleep(1)
    measure("during-decode-cpu-busy", a.reps, 0.3)
    for s in spin:
        s.kill()
    halt = threading.Event()
    detector = threading.Thread(target=detect_forever, args=(halt,), daemon=True)
    detector.start()
    time.sleep(3)
    measure("during-decode-detector", a.reps, 0.3)
    halt.set()
    detector.join()
    stop.set()
    worker.join()
    brain.close()

    summary = []
    for cond in dict.fromkeys(r["cond"] for r in rows):
        for words in PHRASES:
            xs = [r["synth_s"] for r in rows if r["cond"] == cond and r["words"] == words]
            ph = [r["phonemize_s"] for r in rows if r["cond"] == cond and r["words"] == words]
            summary.append({"cond": cond, "words": words, "n": len(xs),
                            "p50_s": round(statistics.median(xs), 3),
                            "p95_s": round(pct(xs, 0.95), 3),
                            "phonemize_p50_s": round(statistics.median(ph), 4)})
            print(json.dumps(summary[-1]), flush=True)
    stamp = f"{time.strftime('%Y-%m-%d')}-tts-contention-{int(time.time())}"
    out = SHARED / "results" / f"{stamp}.jsonl"
    meta = {"summary": summary, "release": os.environ.get("ROBOT_RELEASE"),
            "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "decode_chunks_per_s": round(rate, 1),
            "command": "python -m bench.tts_contention " + " ".join(f"--{k} {v}" for k, v in
                                                               vars(a).items())}
    out.write_text("".join(json.dumps(r) + "\n" for r in [meta, *rows]))
    print(f"decode {rate:.1f} chunks/s; wrote {out}")


if __name__ == "__main__":
    main()
