"""Wake phrase dev check (D65, arm A): transcribe the eval/dev/wake.jsonl WAVs (macOS `say`
voices, eval/make_wavs.py) with Parakeet and spot "hey Edgy" as the robot does. Prints one JSON
row per line and the counts; exits non-zero when a background line is accepted or a wake line
rejected.

    python -m eval.wake | tee bench/results/<date>-wake-<id>.jsonl
"""
import json
import sys
from pathlib import Path

from robot.asr import Scribe, woken
from robot.audio import read_wav

CASES = Path(__file__).parent / "dev/wake.jsonl"


def main() -> int:
    scribe, rows = Scribe(), []
    for case in map(json.loads, CASES.read_text().splitlines()):
        heard = scribe(read_wav(CASES.parent / "audio" / f"{case['id']}.wav"))
        rows.append({"id": case["id"], "wake": case["wake"], "heard": heard,
                     "accepted": woken(heard) is not None})
        print(json.dumps(rows[-1]), flush=True)
    count = lambda wake, accepted: sum(r["wake"] == wake and r["accepted"] == accepted  # noqa: E731
                                       for r in rows)
    print(json.dumps({"summary": "wake", "machine": "mac", "asr": "parakeet-tdt-0.6b-v2 int8",
                      "wake_accepted": count(True, True), "wake_rejected": count(True, False),
                      "background_accepted": count(False, True),
                      "background_rejected": count(False, False)}))
    return 0 if all(r["wake"] == r["accepted"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
