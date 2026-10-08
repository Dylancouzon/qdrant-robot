#!/usr/bin/env python3
"""Record real spoken versions of fixture questions on the Mac, one WAV per question
(16 kHz mono), next to the synthetic ones: <cases dir>/audio-real/<id>.wav.

    .venv/bin/python tools/record.py eval/dev/sessions.jsonl
Press Enter to start a question, speak, press Enter to stop. Type r then Enter to redo the last
one, q then Enter to stop. Already recorded questions are skipped; empty or silent takes are not
saved. `tools/record.py selftest` checks that rule.
"""
import json
import queue
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from robot.audio import write_wav  # noqa: E402

RATE = 16000
MIN_S, MIN_PEAK = 0.5, 0.02  # shorter or quieter takes are mistakes, never fixtures


def usable(audio: np.ndarray) -> str | None:
    """Why a take cannot be a fixture, or None when it can."""
    if len(audio) < MIN_S * RATE:
        return f"too short ({len(audio) / RATE:.1f} s)"
    if np.abs(audio).max() < MIN_PEAK:
        return "silent (is the microphone muted?)"
    return None


def record() -> np.ndarray:
    chunks: queue.Queue = queue.Queue()
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                        callback=lambda data, *_: chunks.put(data.copy())):
        input("   ... recording, press Enter when done ")
    audio = np.concatenate(list(chunks.queue) or [np.zeros((1, 1), np.float32)])[:, 0]
    return audio


def main(cases: Path) -> None:
    out = cases.parent / "audio-real"
    out.mkdir(exist_ok=True)
    steps = [st for line in cases.read_text().splitlines()
             for st in json.loads(line)["steps"] if "say" in st]
    todo = [st for st in steps if not (out / f"{st['id']}.wav").exists()]
    print(f"{len(todo)} of {len(steps)} questions to record, into {out}\n")
    k = 0
    while k < len(todo):
        st = todo[k]
        cmd = input(f"[{k + 1}/{len(todo)}] Say: \"{st['say']}\"\n   Enter to start (q quits): ")
        if cmd.strip() == "q":
            break
        if cmd.strip() == "r" and k > 0:
            k -= 1
            continue
        audio = record()
        if problem := usable(audio):
            print(f"   not saved: {problem}; once more\n")
            continue
        peak = float(np.abs(audio).max())
        write_wav(out / f"{st['id']}.wav", audio, RATE)
        print(f"   saved {len(audio) / RATE:.1f} s, peak {peak:.2f}"
              f"{'  (very quiet: move closer?)' if peak < 0.05 else ''}\n")
        k += 1


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        assert usable(np.zeros(RATE, np.float32)) and usable(np.full(100, 0.5, np.float32))
        assert usable(np.full(RATE, 0.3, np.float32)) is None
        print("selftest ok")
    else:
        main(Path(sys.argv[1]))
