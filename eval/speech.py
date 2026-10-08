#!/usr/bin/env python3
"""Check what the robot actually said: fetch a replay's answer WAVs from the Jetson, transcribe
each on the Mac with Parakeet, and compare with the answer text. Empty, truncated, or wrong
speech fails (word error rate above MAX_WER).

    .venv/bin/python -m eval.speech bench/results/<date>-replay-<id>.jsonl
"""
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from bench.asr_bench import wer
from robot.asr import Scribe

MAX_WER = 0.35  # Parakeet on Kokoro speech; names are normalized on both sides


def load_24k(path: Path) -> np.ndarray:
    """Answer WAVs are 24 kHz; Parakeet takes 16 kHz."""
    with wave.open(str(path)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return np.interp(np.arange(0, len(a), 1.5), np.arange(len(a)), a).astype(np.float32)


def main(result: Path) -> int:
    rows = [json.loads(line) for line in result.read_text().splitlines()]
    audio_dir = rows[-1]["audio_dir"]
    scribe, bad = Scribe(), 0
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["rsync", "-a", f"robot:{audio_dir}/", tmp], check=True)
        for r in rows[:-1]:
            heard = scribe(load_24k(Path(tmp) / r["wav"]))
            w = wer(r["answer"], heard)
            if w > MAX_WER or not heard:
                bad += 1
                print(f"SPEECH {r['id']}: wer {w:.2f}\n  text:  {r['answer']}\n  heard: {heard}")
    print(f"speech {len(rows) - 1 - bad}/{len(rows) - 1} match the answer text")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
