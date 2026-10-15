#!/usr/bin/env python3
"""The acceptance run, from the Mac: deploy, replay the sessions on the Jetson, collect, judge
the answers, and transcribe the speech. Exits non-zero when the replay (keywords, evidence),
the judge, or the speech check fails any turn.

    python3 eval/run.py [--model qwen3vl-2b] [--oracle | --audio audio-real] [cases]
"""
import argparse
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.results import by_id, records, report

ROOT = Path(__file__).resolve().parent.parent
STAGES = ["line_s", "asr_s", "first_token_s", "first_phrase_s", "first_audio_s"]


def jetson(*args: str) -> int:
    return subprocess.run([sys.executable, str(ROOT / "tools/jetson.py"), *args],
                          cwd=ROOT).returncode


def replay_rows(result: Path, cases: Path) -> list[dict]:
    """Require a completed replay of every spoken fixture before acceptance checks run."""
    summaries = report(result)
    if len(summaries) != 1 or summaries[0]["kind"] != "replay" or \
            summaries[0]["run"] != "complete":
        raise ValueError("Replay is incomplete")
    expected = by_id([step for session in records(cases) for step in session["steps"]
                      if "say" in step], cases)
    rows = [row for row in records(result) if "id" in row]
    if not expected or set(by_id(rows, result)) != set(expected):
        raise ValueError("Replay does not cover the requested fixtures")
    recorded = Path(summaries[0]["cases"])
    if (ROOT / recorded).resolve() != cases.resolve():
        raise ValueError("Replay used different fixtures")
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cases", nargs="?", default="eval/dev/sessions.jsonl")
    p.add_argument("--model")
    p.add_argument("--oracle", action="store_true", help="fixture text instead of audio")
    p.add_argument("--audio", help="audio-real: recorded human voices")
    a = p.parse_args()
    if a.oracle and a.audio:
        p.error("--oracle replays text, so --audio does not apply")
    cases = (ROOT / a.cases).resolve()
    if not cases.is_relative_to(ROOT) or not cases.is_file():
        p.error("cases must be an existing file inside the repository")
    # The caller names its result. Collection time cannot identify a run reliably.
    name = f"{time.strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}-replay-{int(time.time())}.jsonl"
    result = ROOT / "bench/results" / name
    if jetson("deploy"):
        return 2
    replay = jetson("run", "replay", "--wait", "--", "-m", "eval.replay",
                    str(cases.relative_to(ROOT)), "--output", name,
                    *(["--model", a.model] if a.model else []),
                    *(["--oracle"] if a.oracle else []),
                    *(["--audio", a.audio] if a.audio else []))
    if replay:
        print(f"replay exited with status {replay}; collecting its evidence", flush=True)
    if jetson("collect"):
        print("could not collect replay results")
        return 2
    try:
        rows = replay_rows(result, cases)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"invalid replay result: {error}")
        return 2
    for k in STAGES:
        if not (v := sorted(r[k] for r in rows if r.get(k) is not None)):
            continue  # not measured (oracle replays have no speech stages)
        print(f"{k:15} p50 {statistics.median(v):.2f}  max {v[-1]:.2f}")
    judged = subprocess.run([sys.executable, str(ROOT / "eval/judge.py"), str(result),
                             str(cases)], cwd=ROOT).returncode
    spoken = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "eval.speech", str(result)],
                            cwd=ROOT).returncode
    return 1 if replay or judged or spoken else 0


if __name__ == "__main__":
    sys.exit(main())
