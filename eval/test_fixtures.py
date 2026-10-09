"""Fixture integrity: every scripted session parses, every spoken step has its WAV, evidence points
to an earlier step, shown images exist, and held-out never shows a dev image."""

import hashlib
import json
from pathlib import Path

EVAL = Path(__file__).parent
KINDS = {"show", "say", "wait", "restart"}  # one per step; eval/replay.py must run each
# Team photos and the face scenes built from them (eval/make_faces.py): gitignored, so absent on
# machines without them; sessions showing a missing face scene there are not checked for it.
SCENES = (EVAL / "faces" / "scenes").resolve()  # eval/faces is a symlink on the Jetson


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
            shown = (path.parent / step["show"]).resolve()
            assert shown.is_file() or not SCENES.parent.exists() and shown.is_relative_to(SCENES), (
                f"{path.name}: no {step['show']} (face scenes: python -m eval.make_faces)"
            )
        if "say" in step:
            assert (path.parent / "audio" / f"{step['id']}.wav").is_file(), f"no WAV {step['id']}"
            missing = set(step.get("evidence", [])) - seen
            assert not missing, f"{step['id']}: evidence {missing} is not an earlier step"
            assert step["rubric"], f"{step['id']}: empty rubric"
        if "wait" in step and "id" in step:  # its evidence: sightings of the named object
            assert step["labels"], f"{step['id']}: a named wait step needs the object's labels"
        if "id" in step:
            seen.add(step["id"])


def test_sessions() -> None:
    for path in sorted(EVAL.glob("*/*.jsonl")):
        sessions = [r for r in records(path) if "steps" in r]  # brain.jsonl holds single cases
        ids = [s["id"] for r in sessions for s in r["steps"] if "say" in s]
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate step ids"
        if sessions and "start_at_s" in sessions[0]:
            # Timed data has separate reviewer rubrics; its audio harness is a later task.
            from eval.prepare_challenge import check_manifest

            assert path.name == "visits.jsonl" and all("start_at_s" in s for s in sessions)
            check_manifest(path.parent)
            continue
        for session in sessions:
            check_session(path, session)


def test_heldout_shows_no_dev_image() -> None:
    dev = {digest(p) for p in [*(EVAL / "dev").rglob("*.jpg"), *SCENES.glob("dev-*.jpg")]}
    # ponytail: m2 and m3 only; heldout/sessions.jsonl shows ../dev/live/closet-night.jpg (M1).
    for name in ("m2.jsonl", "m3.jsonl"):
        for step in (st for s in records(EVAL / "heldout" / name) for st in s["steps"]):
            if "show" not in step:
                continue
            shown = (EVAL / "heldout" / step["show"]).resolve()
            if shown.is_relative_to(SCENES):
                assert shown.name.startswith("heldout-"), f"held-out shows {shown.name}"
            else:
                assert shown.is_relative_to(EVAL / "heldout"), f"held-out shows {shown}"
            assert not shown.exists() or digest(shown) not in dev, f"{step['show']} is a dev image"
