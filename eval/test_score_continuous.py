"""Reject incomplete runs and keep current-frame storage separate from retrieved evidence."""

import json

import pytest

from eval import score_continuous as scoring
from eval.continuous import counts, digest


def test_retrieval_requires_delivered_unambiguous_sources():
    turn = {
        "memories": [7],
        "payloads": [{"id": 7, "ts": 5, "caption": "A red book."}],
        "prompt": [
            {"content": [{"type": "text", "text": "Memories:\n- 5 seconds ago: A red book.\n\n"}]}
        ],
        "source_mappings": [
            {"runtime_id": 8, "mapping": "matched", "source_ids": ["old-book"]},
            {"runtime_id": 7, "mapping": "missing_or_ambiguous", "source_ids": ["old-book"]},
        ],
        "retrieved_statements": [{"step_ids": ["statement-a", "statement-b"]}],
    }
    row = {"turns": [turn]}
    visual = {"category": "older_observation", "source_ids": ["old-book"]}
    assert scoring.retrieval(row, visual)["recall"] == 0
    turn["source_mappings"][1]["mapping"] = "matched"
    assert scoring.retrieval(row, visual)["all_present"]
    dialogue = {"category": "correction", "source_ids": ["statement-a"]}
    assert scoring.retrieval(row, dialogue)["recall"] == 0
    turn["retrieved_statements"][0]["step_ids"] = ["statement-a"]
    assert scoring.retrieval(row, dialogue)["all_present"]
    assert not scoring.retrieval(row, {"category": "visual_detail"})["applicable"]


def test_duplicate_caption_cannot_credit_the_removed_source():
    turn = {
        "memories": [2, 1],
        "payloads": [
            {"id": 1, "ts": 10, "caption": "A book."},
            {"id": 2, "ts": 20, "caption": "A  book."},
        ],
        "prompt": [
            {
                "content": [
                    {
                        "type": "text",
                        "text": "Memories:\n- 10 seconds ago: A book.\n\nVisitor: What was there?",
                    }
                ]
            }
        ],
        "source_mappings": [
            {"runtime_id": 1, "mapping": "matched", "source_ids": ["older-source"]},
            {"runtime_id": 2, "mapping": "matched", "source_ids": ["newer-source"]},
        ],
    }
    row = {"turns": [turn]}
    old = scoring.retrieval(row, {"category": "older_observation", "source_ids": ["older-source"]})
    assert old["recall"] == 0 and old["returned"] == ["newer-source"]
    turn["prompt"] = []
    unknown = scoring.retrieval(
        row, {"category": "older_observation", "source_ids": ["newer-source"]}
    )
    assert unknown["recall"] == 0 and unknown["unknown_runtime_ids"] == [2]


def fixture(tmp_path):
    cases, rubrics, result = [
        tmp_path / name for name in ("cases.jsonl", "rubrics.jsonl", "run.jsonl")
    ]
    step = {
        "id": "question-a",
        "say": "Tell me the color.",
        "scored": True,
        "category": "visual_detail",
    }
    visits = [{"id": "visit-a", "start_at_s": 0, "duration_s": 10, "steps": [step]}]
    cases.write_text(json.dumps(visits[0]) + "\n")
    rubrics.write_text(
        json.dumps({"id": step["id"], "category": step["category"], "rubric": "State the color."})
        + "\n"
    )
    rows = [
        {"type": "metadata", "sha256": digest(cases)},
        {"type": "event", "id": step["id"]},
        {
            "type": "utterance",
            "id": step["id"],
            "scored": True,
            "category": step["category"],
            "ok": False,
            "split": 0,
            "heard": "",
            "answer": "",
            "turns": [],
            "failure": "missing",
        },
        {
            "type": "completion",
            "completed": True,
            "worker_exit": 0,
            "counts": counts(visits, [step]),
            "elapsed_s": 10.1,
            "samples": 160000,
            "utterance_ids": [step["id"]],
            "event_ids": [step["id"]],
            "visit_ids": [visits[0]["id"]],
            "failed_steps": 1,
        },
    ]
    result.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return cases, rubrics, result, rows


@pytest.mark.parametrize(
    "fault", ["missing_footer", "missing_event", "wrong_hash", "wrong_samples"]
)
def test_incomplete_or_changed_run_cannot_be_scored(tmp_path, fault):
    cases, rubrics, result, rows = fixture(tmp_path)
    if fault == "missing_footer":
        rows.pop()
    elif fault == "missing_event":
        rows.pop(1)
    elif fault == "wrong_hash":
        rows[0]["sha256"] = "changed"
    else:
        rows[-1]["samples"] -= 1
    result.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError):
        scoring.inputs(result, cases, rubrics)


def test_missing_answer_remains_failed_without_judge(tmp_path, monkeypatch):
    cases, rubrics, result, _ = fixture(tmp_path)
    seen = []
    monkeypatch.setattr(scoring.judge, "score_items", lambda items: (seen.extend(items) or [], 0))
    assert scoring.score(result, cases, rubrics) == 1
    assert seen == []
    row = json.loads(result.with_suffix(".judged.jsonl").read_text())
    assert row["pass"] is False and row["votes"] == [] and row["why"] == "missing"


def test_shared_judge_cache_avoids_another_vote(tmp_path, monkeypatch):
    cache = tmp_path / "judge-cache.jsonl"
    item = {"id": "a", "visitor": "hello", "robot": "hello", "rubric": "Return a greeting."}
    cache.write_text(
        json.dumps(
            {
                "key": scoring.judge.key(item),
                "pass": True,
                "why": "greeting",
                "votes": [True, True, True],
            }
        )
        + "\n"
    )
    monkeypatch.setattr(scoring.judge, "CACHE", cache)

    def unexpected(_):
        raise AssertionError("cached answers must not call the judge")

    monkeypatch.setattr(scoring.judge, "judge", unexpected)
    verdicts, new = scoring.judge.score_items([item])
    assert new == 0 and verdicts[0]["pass"]
