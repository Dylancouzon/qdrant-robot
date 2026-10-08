#!/usr/bin/env python3
"""Replay scripted sessions through the whole robot on the Jetson and score them: each session
starts with an empty memory, shows fixture frames, and speaks fixture WAVs at real-time pace.
Exits non-zero when a keyword or evidence check fails. Acceptance also needs the judge: run
both through `eval/run.py` on the Mac.

    python -m eval.replay [--model qwen3vl-4b] [--oracle | --audio audio-real] [cases]
"""
import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from robot.audio import paced, read_wav
from robot.brain import MODEL, MODELS
from robot.camera import FileCamera
from robot.config import SHARED
from robot.main import Robot

SILENCE_S = 1.5  # after each question, so the VAD can end the line
REACT_S = 1.0    # a visitor waits for the answer to finish, then this long, before speaking


def ok(step: dict, answer: str) -> bool:
    a = answer.lower().replace("\u2019", "'")
    return any(w in a for w in step["expect_any"] or [""]) and not any(
        w in a for w in step.get("expect_none", []))


def main(path: Path, model: str, oracle: bool, audio: str) -> int:
    sessions = [json.loads(line) for line in path.read_text().splitlines()]
    stamp = time.strftime("%Y-%m-%d")
    out = SHARED / "sessions" / f"replay-{int(time.time())}"
    camera = FileCamera()
    robot = Robot(camera, out, memory=Path(tempfile.mkdtemp()), model=model)
    rows = []
    for s in sessions:
        robot.reset(Path(tempfile.mkdtemp()))
        frames: dict[str, int] = {}  # step id -> the frame stored in that step
        for step in s["steps"]:
            if "show" in step:
                camera.show(path.parent / step["show"])
                continue
            if oracle:  # the fixture text as the transcript: brain quality without ASR
                robot.ask(step["say"])
                turn = robot.turns.get(timeout=60)
                time.sleep(turn.audio_s + REACT_S)
            else:
                for chunk in paced(read_wav(path.parent / audio / f"{step['id']}.wav"),
                                   SILENCE_S):
                    robot.hear(chunk)
                turn = robot.turns.get(timeout=60)
                # The microphone keeps running while the answer plays and the visitor reacts.
                for chunk in paced(np.zeros(0, np.float32), turn.audio_s + REACT_S):
                    robot.hear(chunk)
            frames[step["id"]] = turn.frame_id
            want = [frames[k] for k in step.get("evidence", [])]
            row = {"id": step["id"], "ok": ok(step, turn.answer), "heard": turn.question,
                   "evidence_ok": all(f in turn.memories for f in want) if want else None,
                   "answer": turn.answer, "memories": turn.memories, "facts": turn.facts,
                   "kind": turn.kind, "verbatim": turn.verbatim, "told": turn.told,
                   "prompt": turn.prompt,
                   "line_s": turn.line - turn.speech_end,
                   "asr_s": turn.transcribed - turn.speech_end,
                   "first_token_s": turn.first_token - turn.speech_end,
                   "first_phrase_s": turn.first_phrase - turn.speech_end,
                   "first_audio_s": turn.first_audio - turn.speech_end,
                   "speech_s": turn.speech_end - turn.speech_start, "wav": turn.wav}
            if oracle:  # no audio: speech, line, and transcript stages were not measured
                for k in ("line_s", "asr_s", "speech_s"):
                    row[k] = None
            rows.append(row)
            mark = {True: " +ev", False: " -EV", None: ""}[row["evidence_ok"]]
            print(f"{'ok ' if row['ok'] else 'BAD'} {row['first_audio_s']:.2f}s "
                  f"{step['id']}{mark}: [{turn.question}] {turn.answer}", flush=True)
    robot.close()
    firsts = sorted(r["first_audio_s"] for r in rows)
    summary = {"summary": "replay", "model": model, "oracle": oracle, "audio": audio,
               "cases": str(path),
               "machine": platform.node(),
               "release": os.environ.get("ROBOT_RELEASE"), "n": len(rows),
               "correct": sum(r["ok"] for r in rows),
               "evidence": f"{sum(r['evidence_ok'] is True for r in rows)}/"
                           f"{sum(r['evidence_ok'] is not None for r in rows)}",
               "first_audio_p50_s": statistics.median(firsts),
               "first_audio_max_s": firsts[-1],
               "asr_p50_s": None if oracle else statistics.median(r["asr_s"] for r in rows),
               "first_token_p50_s": statistics.median(r["first_token_s"] for r in rows),
               "first_phrase_p50_s": statistics.median(r["first_phrase_s"] for r in rows),
               "audio_dir": str(out),
               "note": ("oracle: latencies start when the text is submitted (text to audio)"
                        if oracle else
                        "first_audio = first phrase synthesized and queued; no speaker yet")}
    results = SHARED / "results" / f"{stamp}-replay-{int(time.time())}.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in [*rows, summary]))
    print(json.dumps(summary, indent=1))
    passed = all(r["ok"] and r["evidence_ok"] is not False for r in rows)
    return 0 if passed else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="?", default="eval/dev/sessions.jsonl", type=Path)
    ap.add_argument("--model", default=MODEL, choices=MODELS)
    ap.add_argument("--oracle", action="store_true", help="fixture text instead of audio")
    ap.add_argument("--audio", default="audio", help="audio-real: Dylan's recorded voice")
    a = ap.parse_args()
    if a.oracle and a.audio != "audio":
        ap.error("--oracle replays text, so --audio does not apply")
    sys.exit(main(a.cases, a.model, a.oracle, a.audio))
