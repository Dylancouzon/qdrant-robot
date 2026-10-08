#!/usr/bin/env python3
"""Record real spoken versions of fixture questions on the Mac, one WAV per question
(16 kHz mono), next to the synthetic ones: <cases dir>/audio-real/<id>.wav. Every take is
transcribed (Parakeet) and shown back; a take whose transcript misses the fixture text is
saved only on request, so a slip of the finger or a line read out of order never lands in
the fixtures unnoticed. A replay that hears the wrong question is then a robot defect (a pause
split the line), never a bad fixture.

    .venv/bin/python tools/record.py eval/dev/sessions.jsonl          record what is missing
    .venv/bin/python tools/record.py eval/dev/sessions.jsonl --check  list missing or wrong WAVs
Press Enter to start a question, speak, press Enter to stop. Type r then Enter to redo the last
one, q then Enter to stop. Already recorded questions are skipped. `tools/record.py selftest`
checks the take rule.
"""
import json
import queue
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.asr_bench import wer  # noqa: E402
from robot.audio import read_wav, write_wav  # noqa: E402

RATE = 16000
MIN_S, MIN_PEAK = 0.5, 0.02  # shorter or quieter takes are mistakes, never fixtures
MAX_WER = 0.5  # a real voice misses a few words; a different question misses most of them


def usable(audio: np.ndarray) -> str | None:
    """Why a take cannot be a fixture, or None when it can."""
    if len(audio) < MIN_S * RATE:
        return f"too short ({len(audio) / RATE:.1f} s)"
    if np.abs(audio).max() < MIN_PEAK:
        return "silent (is the microphone muted?)"
    return None


def wrong(scribe, audio: np.ndarray, text: str) -> str | None:
    """Why a take is not the fixture question, or None when the transcript matches it."""
    heard = scribe(audio)
    w = wer(text, heard)
    return None if w <= MAX_WER else f"heard {heard!r} (wer {w:.2f})"


def record() -> np.ndarray:
    import sounddevice as sd
    chunks: queue.Queue = queue.Queue()
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                        callback=lambda data, *_: chunks.put(data.copy())):
        input("   ... recording, press Enter when done ")
    audio = np.concatenate(list(chunks.queue) or [np.zeros((1, 1), np.float32)])[:, 0]
    return audio


def questions(cases: Path) -> list[dict]:
    return [st for line in cases.read_text().splitlines()
            for st in json.loads(line)["steps"] if "say" in st]


def check(cases: Path) -> int:
    """Transcribe every recorded fixture and list the missing or wrong ones."""
    from robot.asr import Scribe
    out, scribe, bad = cases.parent / "audio-real", Scribe(), 0
    steps = questions(cases)
    for st in steps:
        path = out / f"{st['id']}.wav"
        problem = wrong(scribe, read_wav(path), st["say"]) if path.exists() else "missing"
        if problem:
            bad += 1
            print(f"{st['id']}: {problem}; say: {st['say']!r}")
    print(f"{len(steps) - bad}/{len(steps)} recordings match their question")
    return 1 if bad else 0


def main(cases: Path) -> None:
    from robot.asr import Scribe
    out = cases.parent / "audio-real"
    out.mkdir(exist_ok=True)
    steps = questions(cases)
    todo = [st for st in steps if not (out / f"{st['id']}.wav").exists()]
    print(f"{len(todo)} of {len(steps)} questions to record, into {out}\n")
    scribe, k = Scribe(), 0
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
        # A real voice can miss words ("favourite colour"); only the human knows a wrong line.
        if (problem := wrong(scribe, audio, st["say"])) and input(
                f"   {problem}; keep it? (y keeps, Enter retakes) ").strip() != "y":
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
        said = lambda _audio: "what did I show you"  # noqa: E731
        assert wrong(said, np.zeros(1), "What did I show you?") is None
        assert wrong(said, np.zeros(1), "Where is your memory stored?")
        print("selftest ok")
    elif sys.argv[2:] == ["--check"]:
        sys.exit(check(Path(sys.argv[1])))
    else:
        main(Path(sys.argv[1]))
