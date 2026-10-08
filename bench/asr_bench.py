#!/usr/bin/env python3
"""ASR bench: play every fixture WAV, then silence, at real-time pace into one continuous
`robot.asr.Ears` stream (Silero VAD), as on the robot, and transcribe each line with `Scribe`.
Measures the end of speech (end of the WAV) to the line (VAD endpointing) and to the
transcript, and the word error rate.

    python -m bench.asr_bench
"""
import argparse
import json
import os
import platform
import re
import statistics
import time
from pathlib import Path

import numpy as np

from robot.asr import Ears, Scribe
from robot.audio import paced, read_wav

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval/dev/brain.jsonl"
SILENCE_S = 2.0  # trailing silence after speech; no line within it counts as a miss


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(len(r), 1)


def play(ears: Ears, audio: np.ndarray) -> float:
    """Feed speech then silence at real-time pace; return the wall time speech ended."""
    end = time.time() + len(audio) / 16000
    for chunk in paced(audio, SILENCE_S):
        ears.feed(chunk)
    return end


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    scribe = Scribe()
    lines: list[tuple[float, str, float]] = []  # (line time, text, transcript time)

    def on_line(audio: np.ndarray, _end: float) -> None:
        t = time.time()
        lines.append((t, scribe(audio), time.time()))

    ears = Ears(lambda: None, on_line)
    cases = [json.loads(line) for line in CASES.read_text().splitlines()]
    play(ears, read_wav(CASES.parent / "audio" / f"{cases[0]['id']}.wav"))  # warm-up
    out = Path(os.environ.get("ROBOT_SHARED", ROOT / "bench")) / "results"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{time.strftime('%Y-%m-%d')}-asr-{int(time.time())}.jsonl"
    rows = []
    for c in cases:
        lines.clear()
        end = play(ears, read_wav(CASES.parent / "audio" / f"{c['id']}.wav"))
        text = " ".join(t for _, t, _ in lines)
        row = {"id": c["id"], "ref": c["say"], "hyp": text, "wer": wer(c["say"], text),
               "line_s": lines[-1][0] - end if lines else None,
               "transcript_s": lines[-1][2] - end if lines else None}
        rows.append(row)
        print(f"{(row['transcript_s'] or -1) * 1000:5.0f} ms wer {row['wer']:.2f} {text}")
    done = [r for r in rows if r["transcript_s"] is not None]
    summary = {"summary": "asr: silero vad + parakeet int8 cpu",
               "machine": platform.node(), "release": os.environ.get("ROBOT_RELEASE"),
               "n": len(rows), "not_completed": len(rows) - len(done),
               "mean_wer": statistics.mean(r["wer"] for r in rows),
               "line_p50_s": statistics.median(r["line_s"] for r in done),
               "transcript_p50_s": statistics.median(r["transcript_s"] for r in done),
               "transcript_max_s": max(r["transcript_s"] for r in done),
               "audio": "synthetic macOS voices"}
    dest.write_text("".join(json.dumps(r) + "\n" for r in [*rows, summary]))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
