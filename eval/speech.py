#!/usr/bin/env python3
"""Check what the robot actually said: fetch a replay's answer WAVs from the Jetson, transcribe
each on the Mac with Parakeet, and compare with the answer text. Empty, truncated, or wrong
speech fails (word error rate above MAX_WER).

    .venv/bin/python -m eval.speech bench/results/<date>-replay-<id>.jsonl
"""

import json
import platform
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from bench.asr_bench import wer
from robot.asr import Scribe
from robot.config import ROOT
from eval.continuous import digest

MAX_WER = 0.35  # Parakeet on Kokoro speech; names are normalized on both sides


def load_24k(path: Path) -> np.ndarray:
    """Answer WAVs are 24 kHz; Parakeet takes 16 kHz."""
    with wave.open(str(path)) as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (24000, 1, 2):
            raise ValueError("answer WAV must be 24 kHz mono signed-16 PCM")
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if not len(a):
        return np.empty(0, np.float32)
    return np.interp(np.arange(0, len(a), 1.5), np.arange(len(a)), a).astype(np.float32)


def speech_rows(rows):
    """Keep every continuous utterance, including missing and split outputs."""
    if rows[0].get("type") != "metadata" or "duration_s" not in rows[0]:
        return rows[:-1], rows[-1]["audio_dir"]
    footer = rows[-1]
    utterances = [row for row in rows if row.get("type") == "utterance"]
    if (
        footer.get("type") != "completion"
        or footer.get("completed") is not True
        or footer.get("worker_exit") != 0
        or [row["id"] for row in utterances] != footer.get("utterance_ids")
    ):
        raise ValueError("continuous speech requires completed full utterance coverage")
    answers = []
    for row in utterances:
        for turn in row["turns"] or [{}]:
            answers.append(
                {
                    "id": row["id"],
                    "answer": turn.get("answer", ""),
                    "wav": turn.get("wav"),
                    "structural_ok": row["ok"],
                }
            )
    return answers, footer["audio_dir"]


def main(result: Path) -> int:
    rows, audio_dir = speech_rows([json.loads(line) for line in result.read_text().splitlines()])
    scribe, bad = Scribe(), 0
    output = result.with_suffix(".speech.jsonl")
    with tempfile.TemporaryDirectory() as tmp, output.open("w") as stream:
        subprocess.run(["rsync", "-a", f"robot:{audio_dir}/", tmp], check=True, timeout=120)
        for r in rows:
            path = Path(tmp) / r["wav"] if r.get("wav") else None
            exists = path is not None and path.is_file()
            audio = load_24k(path) if exists else np.empty(0, np.float32)
            heard = scribe(audio) if len(audio) else ""
            w = wer(r["answer"], heard)
            ok = bool(heard and r["answer"] and w <= MAX_WER and r.get("structural_ok", True))
            bad += not ok
            stream.write(
                json.dumps(
                    {
                        "id": r["id"],
                        "wav": r.get("wav"),
                        "answer": r["answer"],
                        "heard": heard,
                        "wer": w,
                        "pass": ok,
                        "wav_sha256": digest(path) if exists else None,
                    }
                )
                + "\n"
            )
            stream.flush()
            print(f"speech {r['id']}: {'PASS' if ok else 'FAIL'}, wer {w:.2f}", flush=True)
        stream.write(
            json.dumps(
                {
                    "summary": "speech",
                    "completed": True,
                    "n": len(rows),
                    "passed": len(rows) - bad,
                    "max_wer": MAX_WER,
                    "result_sha256": digest(result),
                    "audio_dir": audio_dir,
                    "machine": platform.node(),
                    "python": platform.python_version(),
                    "command": sys.argv,
                    "code_sha256": digest(Path(__file__)),
                    "models_manifest_sha256": digest(ROOT / "models.json"),
                    "asr": {
                        "model": "nemo-parakeet-tdt-0.6b-v2",
                        "precision": "int8",
                        "provider": "CPUExecutionProvider",
                        "input_rate": 16000,
                    },
                    "mode": "independent Mac Parakeet transcription; synthesized output",
                }
            )
            + "\n"
        )
    print(f"speech {len(rows) - bad}/{len(rows)} match the answer text")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
