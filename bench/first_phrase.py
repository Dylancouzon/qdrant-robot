#!/usr/bin/env python3
"""First-phrase fix candidates in a simulated turn (prefilled frame, streamed answer cut into
phrases, each phrase synthesized as robot/main.py does, detector at 15 fps throughout):
`base`; `pause-decode`: stop the stream at the first phrase, synthesize it, then resume with
the text so far as an assistant prefill; `pause-detector`: no detection while the first
phrase is synthesized; `pause-both`.

    python -m bench.first_phrase [--reps 8]
"""
import argparse
import json
import itertools
import math
import os
import statistics
import threading
import time
from collections.abc import Iterator

import cv2

from robot import brain
from robot.config import ROOT, SHARED
from robot.detect import Detector
from robot.tts import Speaker, phrases

CASES = [("eval/dev/images/coco-000000000139.jpg", "What do you see?"),
         ("eval/dev/images/coco-000000000632.jpg", "What is on the left?"),
         ("eval/dev/images/coco-000000000139.jpg", "Does Qdrant Edge need a server?")]
MODES = ["base", "pause-decode", "pause-detector", "pause-both"]


def turn(b: brain.Brain, voice: Speaker, msgs: list[dict], mode: str,
         idle: threading.Event) -> dict:
    t0, said, marks = time.perf_counter(), [], {}
    gen = b.answer(msgs)

    def feed(source: Iterator[str]) -> Iterator[str]:
        for d in source:
            marks.setdefault("first_token", time.perf_counter() - t0)
            said.append(d)
            yield d

    cut = phrases(feed(gen))
    first = next(cut)
    marks["first_phrase"] = time.perf_counter() - t0
    if mode in ("pause-decode", "pause-both"):
        gen.close()  # closes the connection: llama-server stops this generation
    if mode in ("pause-detector", "pause-both"):
        idle.set()
    voice.say(first)
    marks["first_audio"] = time.perf_counter() - t0
    idle.clear()
    if mode in ("pause-decode", "pause-both"):
        prior = "".join(said)
        rest = prior[prior.index(first) + len(first):]  # cut but not yet a phrase
        t = time.perf_counter()
        resumed = feed(b.answer(msgs, prior=prior))
        nxt = next(resumed, "")
        marks["resume_s"] = time.perf_counter() - t
        cut = phrases(itertools.chain([rest, nxt], resumed))  # streamed, as in a turn
    for p in cut:
        voice.say(p)
    marks["done"] = time.perf_counter() - t0
    return {**marks, "answer": "".join(said).strip()}


def p95(values: list[float]) -> float:
    """Nearest-rank 95th percentile of sorted values."""
    return values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reps", type=int, default=8)
    a = p.parse_args()
    voice, b = Speaker(), brain.Brain()
    halt, idle = threading.Event(), threading.Event()
    frames = {f: cv2.imread(str(ROOT / f)) for f, _ in CASES}

    def detect_forever() -> None:
        detect, due = Detector(), time.time()
        while not halt.is_set():
            if not idle.is_set():
                detect(frames[CASES[0][0]])
            due = max(due + 1 / 15, time.time())
            time.sleep(max(0.0, due - time.time()))
        detect.close()

    detector = threading.Thread(target=detect_forever, daemon=True)
    detector.start()
    rows = []
    for _ in range(a.reps):
        for f, q in CASES:
            image = brain.jpeg(frames[f])
            for mode in MODES:
                b.prefill(brain.messages([], image))
                msgs = brain.messages([], image, question=q)
                rows.append({"mode": mode, "question": q, **turn(b, voice, msgs, mode, idle)})
    halt.set()
    detector.join()
    b.close()
    base = {r["question"]: r["answer"] for r in rows if r["mode"] == "base"}
    summary = []
    for mode in MODES:
        got = [r for r in rows if r["mode"] == mode]
        tts = sorted(r["first_audio"] - r["first_phrase"] for r in got)
        audio = sorted(r["first_audio"] for r in got)
        summary.append({
            "mode": mode, "n": len(got),
            "tts_p50_s": round(statistics.median(tts), 3), "tts_p95_s": round(p95(tts), 3),
            "first_audio_p50_s": round(statistics.median(audio), 3),
            "first_audio_p95_s": round(p95(audio), 3),
            "done_p50_s": round(statistics.median(r["done"] for r in got), 3),
            "resume_p50_s": round(statistics.median(r.get("resume_s", 0) for r in got), 3),
            "same_answer": sum(r["answer"] == base[r["question"]] for r in got)})
        print(json.dumps(summary[-1]), flush=True)
    for r in rows:
        if r["answer"] != base[r["question"]]:
            print("differs:", r["mode"], repr(r["answer"]), "vs", repr(base[r["question"]]))
    stamp = f"{time.strftime('%Y-%m-%d')}-first-phrase-{int(time.time())}"
    meta = {"summary": summary, "release": os.environ.get("ROBOT_RELEASE"),
            "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "model": brain.MODEL,
            "command": f"python -m bench.first_phrase --reps {a.reps}",
            "note": "p95 is the nearest-rank 95th percentile; times from the request start"}
    (SHARED / "results" / f"{stamp}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in [meta, *rows]))


if __name__ == "__main__":
    main()
