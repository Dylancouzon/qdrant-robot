#!/usr/bin/env python3
"""Replay scripted sessions through the whole robot on the Jetson and score them: each session
starts with an empty memory, shows fixture frames, speaks fixture WAVs at real-time pace, waits,
and restarts the robot on the same memory. Exits non-zero when a keyword or evidence check
fails. Acceptance also needs the judge: run both through `eval/run.py` on the Mac.
Read past scores offline with `python3 tools/results.py`; `correct` is a keyword heuristic.

    python -m eval.replay [--model qwen3vl-4b] [--oracle | --audio audio-real] [cases]
"""
import argparse
import gc
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from robot.audio import paced, read_wav
from robot.brain import MODEL, MODELS, SYSTEM
from robot.camera import FileCamera
from robot.config import SHARED
from robot.main import Robot
from robot.memory import is_question

SILENCE_S = 1.5  # after each question, so the VAD can end the line
REACT_S = 1.0    # a visitor waits for the answer to finish, then this long, before speaking
STAGES = ("line_s", "asr_s", "first_token_s", "first_phrase_s", "first_audio_s", "speech_s",
          "detect_fps")


def ok(step: dict, answer: str) -> bool:
    a = answer.lower().replace("\u2019", "'")
    return any(w in a for w in step["expect_any"] or [""]) and not any(
        w in a for w in step.get("expect_none", []))


def converse(robot: Robot, step: dict, wav: Path | None) -> list:
    """Say the step (its WAV at real-time pace, or its text when `wav` is None) and return
    every turn it produced, then wait while the answer plays and the visitor reacts."""
    asked = robot.asked
    if wav is None:  # oracle: the fixture text as the transcript, brain quality without ASR
        robot.ask(step["say"])
    else:
        for chunk in paced(read_wav(wav), SILENCE_S):
            robot.hear(chunk)
        robot.lines.join()  # every line of this step is transcribed
    # A pause inside a question can split it into several lines, each answered.
    turns = [robot.turns.get(timeout=60) for _ in range(robot.asked - asked)]
    idle(robot, (turns[-1].audio_s if turns else 0) + REACT_S, wav is None)
    return turns


def idle(robot: Robot, seconds: float, oracle: bool) -> None:
    """Nobody speaks for `seconds`. The microphone keeps running (silence at real-time pace),
    except in oracle replays, which have no audio."""
    if oracle:
        time.sleep(seconds)
    else:
        for chunk in paced(np.zeros(0, np.float32), seconds):
            robot.hear(chunk)


def score(step: dict, turns: list, frames: dict[str, tuple], oracle: bool) -> dict:
    """The step's row: a split step is BAD, and its last turn (the question's end) is scored.
    Evidence: a named step's statement must be among the recalled statements (the robot stores
    statements, robot/main.py); a named question step's frame, or one of a named wait step's
    sightings, among the recalled memories."""
    if not turns:  # the VAD or the transcript dropped the question
        return {"id": step["id"], "ok": False, "split": 0, "heard": "", "answer": "",
                "evidence_ok": None, **dict.fromkeys(STAGES)}
    turn = turns[-1]
    frames[step["id"]] = ({turn.frame_id}, None if is_question(turn.question) else turn.question)
    want = [frames.get(k, (set(), None)) for k in step.get("evidence", [])]
    row = {"id": step["id"], "ok": ok(step, turn.answer) and len(turns) == 1,
           "heard": " | ".join(t.question for t in turns), "split": len(turns),
           "evidence_ok": all(said in turn.told if said else bool(ids & set(turn.memories))
                               for ids, said in want)
                           if want else None,
           "answer": turn.answer, "memories": turn.memories, "facts": turn.facts,
           "kind": turn.kind, "verbatim": turn.verbatim, "told": turn.told,
           "prompt": turn.prompt,
           "line_s": turn.line - turn.speech_end,
           "asr_s": turn.transcribed - turn.speech_end,
           "first_token_s": turn.first_token - turn.speech_end,
           "first_phrase_s": turn.first_phrase - turn.speech_end,
           "first_audio_s": turn.first_audio - turn.speech_end,
           "speech_s": turn.speech_end - turn.speech_start, "wav": turn.wav,
           "detect_fps": turn.detect_fps, "identity": turn.identity}
    if oracle:  # no audio: speech, line, and transcript stages were not measured
        for k in ("line_s", "asr_s", "speech_s"):
            row[k] = None
    return row


def reported(step: dict, turns: list, frames: dict[str, tuple], oracle: bool) -> dict:
    row = score(step, turns, frames, oracle)
    mark = {True: " +ev", False: " -EV", None: ""}[row["evidence_ok"]]
    mark += f" split: {len(turns)}" if len(turns) > 1 else ""
    print(f"{'ok ' if row['ok'] else 'BAD'} {row['first_audio_s'] or 0:.2f}s "
          f"{step['id']}{mark}: [{row['heard']}] {row['answer']}", flush=True)
    return row


def sighted(sightings: list[dict], shown: tuple[float, float], step: dict,
            in_view: set[int]) -> set[int]:
    """Ids of the sightings of a named wait step's object: seen while the frame was `shown`
    (from, to), with one of its `labels`, and in its `region` when the step names one. A point
    whose track is still `in_view` is being seen now: its stored last_seen is not its end."""
    return {s["id"] for s in sightings if s["first_seen"] <= shown[1]
            and (s["id"] in in_view or s["last_seen"] >= shown[0])
            and s["label"] in step["labels"] and step.get("region", s["region"]) == s["region"]}


def run(sessions: list[dict], start: Callable[[Path], Robot], cases: Path, oracle: bool,
        audio: str) -> list[dict]:
    """Play each session from an empty memory and return the scored rows. A restart closes the
    robot and starts a new one on the session's memory folder, as after a power cycle."""
    robot, rows = None, []
    for s in sessions:
        memory = Path(tempfile.mkdtemp())
        if robot is None:
            robot = start(memory)
        else:
            robot.reset(memory)
        frames: dict[str, tuple] = {}  # step id -> (memory ids stored there, statement or None)
        shown = time.time()  # when the frame in view was shown
        for step in s["steps"]:
            if "show" in step:
                robot.camera.show(cases.parent / step["show"])
                shown = time.time()
            elif "wait" in step:  # the frame stays in view
                idle(robot, step["wait"], oracle)
                if "id" in step:
                    robot.jobs.join()  # the sightings queued while it waited are stored
                    found = robot.memory.sightings(before=time.time(), n=50)
                    with robot.detecting:
                        in_view = {robot.points.get(t) for t in robot.tracker.in_view()}
                    frames[step["id"]] = (sighted(found, (shown, time.time()), step, in_view),
                                          None)
            elif "restart" in step:
                t = time.time()
                robot.close()
                del robot
                gc.collect()  # free the old models before the new ones load
                closed = time.time()
                robot = start(memory)
                print(f"restart: closed in {closed - t:.1f}s, "
                      f"started in {time.time() - closed:.1f}s", flush=True)
            else:
                wav = None if oracle else cases.parent / audio / f"{step['id']}.wav"
                rows.append(reported(step, converse(robot, step, wav), frames, oracle))
            if robot.detect_failed:  # answers without sightings would score a different robot
                raise RuntimeError("detection stopped") from robot.detect_failed
    robot.close()
    return rows


def p50(rows: list[dict], k: str) -> float | None:
    v = [r[k] for r in rows if r[k] is not None]
    return statistics.median(v) if v else None


def main(path: Path, model: str, oracle: bool, audio: str) -> int:
    sessions = [json.loads(line) for line in path.read_text().splitlines()]
    stamp = time.strftime("%Y-%m-%d")
    out = SHARED / "sessions" / f"replay-{int(time.time())}"
    camera = FileCamera()
    rows = run(sessions, lambda memory: Robot(camera, out, memory=memory, model=model,
                                              wake_word=False), path, oracle, audio)
    firsts = sorted(r["first_audio_s"] for r in rows if r["first_audio_s"] is not None)
    summary = {"summary": "replay", "model": model, "oracle": oracle, "audio": audio,
               "cases": str(path), "system": SYSTEM,  # the prompt rows leave it out
               "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
               "machine": platform.node(),
               "release": os.environ.get("ROBOT_RELEASE"), "n": len(rows),
               "n_expected": sum("say" in st for s in sessions for st in s["steps"]),
               "score_type": "keyword_and_split; answer correctness is in .judged.jsonl",
               "correct": sum(r["ok"] for r in rows),
               "split": sum(r["split"] > 1 for r in rows),
               "evidence": f"{sum(r['evidence_ok'] is True for r in rows)}/"
                           f"{sum(r['evidence_ok'] is not None for r in rows)}",
               "first_audio_p50_s": p50(rows, "first_audio_s"),
               "first_audio_max_s": firsts[-1] if firsts else None,
               "asr_p50_s": p50(rows, "asr_s"),
               "first_token_p50_s": p50(rows, "first_token_s"),
               "first_phrase_p50_s": p50(rows, "first_phrase_s"),
               "detect_fps_p50": p50(rows, "detect_fps"),
               "detect_fps_min": min((r["detect_fps"] for r in rows if r["detect_fps"] is not None),
                                     default=None),
               "audio_dir": str(out),
               "note": ("oracle: latencies start when the text is submitted (text to audio)"
                        if oracle else
                        "first_audio = first phrase synthesized and queued; no speaker yet")}
    results = SHARED / "results" / f"{stamp}-replay-{int(time.time())}.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in [*rows, summary]))
    # Preserve the full prompt in the evidence file, keep the console summary readable.
    print(json.dumps({k: v for k, v in summary.items() if k != "system"}, indent=1))
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
