"""Acceptance selects its own complete result and preserves failures from every stage."""
import json
import sys
from types import SimpleNamespace

import pytest

from eval import run


@pytest.fixture
def acceptance(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({"steps": [{"id": "one", "say": "Hello"},
                                          {"id": "two", "say": "Goodbye"}]}) + "\n")
    results = tmp_path / "bench/results"
    results.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", ["run.py", str(cases)])
    return cases, results


def write_result(path, cases="cases.jsonl", ids=("one", "two"), footer=True):
    rows = [{"id": ident, "heard": "Hello", "answer": "Hi", "ok": True} for ident in ids]
    if footer:
        rows.append({"summary": "replay", "cases": cases, "n": len(ids), "n_expected": 2})
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


@pytest.mark.parametrize("change", ["missing", "partial", "duplicate", "wrong_ids", "wrong_cases",
                                   "empty"])
def test_incomplete_or_wrong_replay_cannot_pass(acceptance, change):
    cases, results = acceptance
    result = results / "run.jsonl"
    write_result(result, cases="other.jsonl" if change == "wrong_cases" else str(cases),
                 ids={"partial": ("one",), "duplicate": ("one", "one"),
                      "wrong_ids": ("one", "other"), "empty": ()}.get(change, ("one", "two")),
                 footer=change != "missing")
    with pytest.raises(ValueError):
        run.replay_rows(result, cases)


@pytest.mark.parametrize("replay_code,collect_code,judge_code,speech_code,expected", [
    (0, 0, 0, 0, 0), (1, 0, 0, 0, 1), (0, 1, 0, 0, 2),
    (0, 0, 1, 0, 1), (0, 0, 0, 1, 1),
])
def test_exact_result_and_stage_failures(acceptance, monkeypatch, replay_code, collect_code,
                                       judge_code, speech_code, expected):
    cases, results = acceptance
    stale = results / "old-replay-1000000000.jsonl"
    write_result(stale)
    commands, checked = [], []

    def jetson(*args):
        commands.append(args)
        if args[0] == "run":
            name = args[args.index("--output") + 1]
            write_result(results / name, str(cases))
            return replay_code
        return collect_code if args[0] == "collect" else 0

    def check(args, **kwargs):
        checked.append(args)
        assert kwargs["cwd"] == run.ROOT
        assert str(stale) not in args
        return SimpleNamespace(returncode=judge_code if len(checked) == 1 else speech_code)

    monkeypatch.setattr(run, "jetson", jetson)
    monkeypatch.setattr(run.subprocess, "run", check)
    assert run.main() == expected
    assert [cmd[0] for cmd in commands] == ["deploy", "run", "collect"]
    assert len(checked) == (0 if collect_code else 2)


def test_missing_named_result_never_uses_an_old_run(acceptance, monkeypatch):
    _, results = acceptance
    write_result(results / "old-replay-1000000000.jsonl")
    monkeypatch.setattr(run, "jetson", lambda *args: 0)
    monkeypatch.setattr(run.subprocess, "run", lambda *args, **kw: pytest.fail("stale result"))
    assert run.main() == 2
