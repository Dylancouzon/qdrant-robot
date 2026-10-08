#!/usr/bin/env python3
"""The acceptance run, from the Mac: deploy, replay the sessions on the Jetson, collect, judge
the answers, and transcribe the speech. Exits non-zero when the replay (keywords, evidence),
the judge, or the speech check fails any turn.

    python3 eval/run.py [--model qwen3vl-2b] [eval/dev/sessions.jsonl]
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ["line_s", "asr_s", "first_token_s", "first_phrase_s", "first_audio_s"]


def jetson(*args: str) -> int:
    return subprocess.run([sys.executable, str(ROOT / "tools/jetson.py"), *args]).returncode


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cases", nargs="?", default="eval/dev/sessions.jsonl")
    p.add_argument("--model")
    a = p.parse_args()
    if jetson("deploy"):
        return 2
    start = time.time()
    replay = jetson("run", "replay", "--wait", "--", "-m", "eval.replay", a.cases,
                    *(["--model", a.model] if a.model else []))
    jetson("collect")
    new = [f for f in (ROOT / "bench/results").glob("*-replay-*.jsonl")
           if not f.name.endswith(".judged.jsonl") and f.stat().st_mtime > start - 5]
    if not new:
        print("no replay result came back")
        return 2
    result = max(new, key=lambda f: f.stat().st_mtime)
    rows = [r for r in map(json.loads, result.read_text().splitlines()) if "id" in r]
    for k in STAGES:
        v = sorted(r[k] for r in rows)
        print(f"{k:15} p50 {statistics.median(v):.2f}  max {v[-1]:.2f}")
    judged = subprocess.run([sys.executable, str(ROOT / "eval/judge.py"), str(result),
                             a.cases]).returncode
    spoken = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "eval.speech", str(result)],
                            cwd=ROOT).returncode
    return 1 if replay or judged or spoken else 0


if __name__ == "__main__":
    sys.exit(main())
