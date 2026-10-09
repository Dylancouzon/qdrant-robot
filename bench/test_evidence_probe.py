"""Offline manifest and paired-prompt integrity tests for F0."""

import copy
import hashlib
import json
from collections import Counter

import pytest

from bench import evidence_probe as probe
from robot import brain
from robot.memory import about_now


def test_frozen_selection_and_sources():
    rows = probe.load()
    assert Counter(r["cases"] for r in rows) == {
        "eval/dev/m2.jsonl": 10,
        "eval/dev/sessions.jsonl": 10,
        "eval/dev/visitor.jsonl": 4,
    }
    assert sum("control" in tag for r in rows for tag in r["cause_tags"]) == 4
    for row in rows:
        assert "eval/probes" not in json.dumps(row)
        assert row["image_present"] == (
            about_now(row["question"])
            or (
                row["kind"] == "sight"
                and brain.PAST.strip() not in row["original_prompt"][-1]["content"][-1]["text"]
            )
        )
        assert len(row["log_sha256"]) == 64


def test_pair_changes_evidence_only():
    image = {"type": "image_url", "image_url": {"url": "test-image"}}
    for row in probe.load():
        original = copy.deepcopy(row)
        left, right = (
            probe.messages(row, "original", image),
            probe.messages(row, "sufficient", image),
        )
        assert row == original, "construction must not mutate the frozen manifest"
        assert left[:-1] == right[:-1]
        assert left[0] == {"role": "system", "content": row["system"]}
        assert left[1:-1] == row["original_prompt"][:-1]
        assert left[-1]["content"][:-1] == right[-1]["content"][:-1]
        assert bool(left[-1]["content"][:-1]) == row["image_present"]
        a, b = (msgs[-1]["content"][-1]["text"] for msgs in (left, right))
        assert probe.BLOCK.sub("", a) == probe.BLOCK.sub("", b)
        assert probe.evidence(b) == row["sufficient_evidence"]
        assert a.endswith("Visitor: " + row["question"])
        assert row["rubric"] not in b
        assert (a == b) == row["unchanged_control"]


@pytest.mark.parametrize(
    "mutation",
    ["count", "duplicate", "source", "frame", "question", "evidence", "rubric", "prompt"],
)
def test_invalid_manifest_rejected(tmp_path, mutation):
    rows = probe.load()
    row = rows[0]
    if mutation == "count":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = row
    elif mutation == "source":
        row["sources"][0]["step"]["say"] = "Altered transcript"
    elif mutation == "frame":
        row["frame_sha256"] = "0" * 64
    elif mutation == "question":
        row["question"] = "A different question"
    elif mutation == "evidence":
        row["sufficient_evidence"] = ["Expected answer: leaked target"]
    elif mutation == "rubric":
        row["rubric"] = "Altered rubric"
    elif mutation == "prompt":
        row["original_prompt"][0]["content"] = "Altered history"
    path = tmp_path / "bad.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError):
        probe.load(path)


def test_manifest_hash_matches_bytes():
    assert probe.digest(probe.MANIFEST) == hashlib.sha256(probe.MANIFEST.read_bytes()).hexdigest()
