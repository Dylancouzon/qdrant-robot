"""Fixture integrity: every scripted session parses, every spoken step has its WAV, evidence points
to an earlier step, shown images exist, and held-out never shows a dev image."""
import hashlib
import json
from pathlib import Path

EVAL = Path(__file__).parent
KINDS = {"show", "say", "wait", "restart"}  # one per step; eval/replay.py must run each


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_session(path: Path, session: dict) -> None:
    seen = set()
    for step in session["steps"]:
        kinds = KINDS & step.keys()
        assert len(kinds) == 1, f"{path.name} {session['id']}: step needs one of {KINDS}: {step}"
        if "show" in step:
            assert (path.parent / step["show"]).is_file(), f"{path.name}: no {step['show']}"
        if "say" in step:
            assert (path.parent / "audio" / f"{step['id']}.wav").is_file(), f"no WAV {step['id']}"
            missing = set(step.get("evidence", [])) - seen
            assert not missing, f"{step['id']}: evidence {missing} is not an earlier step"
            assert step["rubric"], f"{step['id']}: empty rubric"
            seen.add(step["id"])


def test_sessions() -> None:
    for path in sorted(EVAL.glob("*/*.jsonl")):
        sessions = [r for r in records(path) if "steps" in r]  # brain.jsonl holds single cases
        ids = [s["id"] for r in sessions for s in r["steps"] if "say" in s]
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate step ids"
        for session in sessions:
            check_session(path, session)


def test_heldout_shows_no_dev_image() -> None:
    dev = {digest(p) for p in (EVAL / "dev").rglob("*.jpg")}
    # ponytail: m2.jsonl only; heldout/sessions.jsonl shows ../dev/live/closet-night.jpg (M1).
    for session in records(EVAL / "heldout" / "m2.jsonl"):
        for step in session["steps"]:
            if "show" in step:
                shown = (EVAL / "heldout" / step["show"]).resolve()
                assert shown.is_relative_to(EVAL / "heldout"), f"held-out shows {shown}"
                assert digest(shown) not in dev, f"held-out {step['show']} is a dev image"
