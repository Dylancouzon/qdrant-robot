"""Offline score handling, including the difference between keywords and judged answers."""
import json
from pathlib import Path

import pytest

import results


def write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def evidence(tmp_path):
    path = tmp_path / "run.jsonl"
    rows = [{"id": "a", "heard": "Where is it?", "answer": "On the moon.",
             "ok": True, "evidence_ok": False},
            {"id": "b", "heard": "Hello", "answer": "Hi", "ok": True,
             "evidence_ok": None}]
    meta = {"summary": "replay", "machine": "robot", "model": "small", "release": "abc",
            "oracle": True, "cases": "eval/dev/m2.jsonl", "n": 2, "correct": 2}
    write(path, rows + [meta])
    judged = [{"id": "a", "visitor": "Where is it?", "robot": "On the moon.", "pass": False}]
    write(path.with_suffix(".judged.jsonl"), judged)
    return path, rows, meta, judged


def test_partial_judging_and_keyword_score_are_separate(evidence):
    path, *_ = evidence
    r, = results.report(path)
    assert (r["judged"], r["keyword"], r["retrieval"]) == ("0/1", "2/2", "0/1")
    assert r["run"] == "complete" and r["judging"] == "partial" and r["unjudged_n"] == 1
    assert r["mode"] == "oracle" and r["release"] == "abc"


def test_missing_footer_and_sidecar_cannot_pass(evidence):
    path, rows, *_ = evidence
    write(path, rows)
    path.with_suffix(".judged.jsonl").unlink()
    r, = results.report(path)
    assert (r["run"], r["judging"], r["judged"]) == ("incomplete", "unjudged", "unmeasured")
    assert r["machine"] == r["release"] == r["model"] == "unknown"


def test_inconsistent_completion_count(evidence):
    path, rows, meta, _ = evidence
    write(path, rows + [{**meta, "n_expected": 3}])
    assert results.report(path)[0]["run"] == "incomplete"


@pytest.mark.parametrize("change", ["duplicate_raw", "duplicate_judge", "stale", "extra"])
def test_ambiguous_or_stale_verdicts_are_errors(evidence, change):
    path, rows, meta, js = evidence
    if change == "duplicate_raw":
        write(path, rows + [rows[0], meta])
    elif change == "duplicate_judge":
        write(path.with_suffix(".judged.jsonl"), js * 2)
    elif change == "stale":
        write(path, [{**rows[0], "answer": "Here."}, rows[1], meta])
    else:
        write(path.with_suffix(".judged.jsonl"), [{**js[0], "id": "other"}])
    with pytest.raises(ValueError):
        results.report(path)


def test_bakeoff_variants_never_pool_scores(evidence):
    path, rows, meta, _ = evidence
    write(path, [{**rows[0], "variant": "A"}, {**rows[1], "variant": "B"},
                 {**meta, "summary": "brain_bakeoff", "variants": ["A", "B"]}])
    a, b = results.report(path)
    assert (a["variant"], a["judged"], a["n"]) == ("A", "0/1", 1)
    assert (b["variant"], b["judging"], b["n"]) == ("B", "unjudged", 1)


def test_newest_run_uses_timestamp_not_model_name(tmp_path):
    early = tmp_path / "2026-10-09-bakeoff-z-1791520325.jsonl"
    late = tmp_path / "2026-10-08-bakeoff-a-1791521394.jsonl"
    early.touch()
    late.touch()
    assert results.raw_paths([tmp_path]) == [early, late]


def test_unsupported_summary_is_rejected(evidence):
    path, rows, meta, _ = evidence
    write(path, rows + [{**meta, "summary": "unrelated_benchmark"}])
    with pytest.raises(ValueError, match="unsupported result format"):
        results.report(path)


def test_replay_telemetry_is_skipped_in_directories_and_rejected_explicitly(tmp_path):
    trace = tmp_path / "2026-10-08-replay-memory-1791503571.jsonl"
    write(trace, [{"time": 1, "rss": 50}])
    assert results.raw_paths([tmp_path]) == []
    with pytest.raises(ValueError, match="unsupported"):
        results.report(trace)


def test_cli_filters_files_without_pooling_releases(evidence, monkeypatch, capsys):
    path, rows, meta, _ = evidence
    other = path.parent / "other.jsonl"
    write(other, rows + [{**meta, "release": "def"}])
    monkeypatch.setattr(results.sys, "argv", ["results", str(path), str(other),
                                            "--release", "abc", "--json"])
    assert results.main() == 0
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(output) == 1 and output[0]["release"] == "abc"


@pytest.mark.parametrize("run,keyword,judged", [
    ("2026-10-08-replay-1791518506", "61/74", "39/74"),
    ("2026-10-09-replay-1791520659", "18/21", "17/21"),
    ("2026-10-09-replay-1791520325", "56/74", "38/74"),
    ("2026-10-09-replay-1791521394", "62/74", "44/74"),
    ("2026-10-09-replay-1791521641", "19/21", "16/21"),
])
def test_d75_existing_evidence(run, keyword, judged):
    path = results.ROOT / "bench/results" / f"{run}.jsonl"
    if not path.exists():
        pytest.skip("collected evidence is local and gitignored")
    r, = results.report(path)
    assert (r["keyword"], r["judged"]) == (keyword, judged)
    assert r["run"] == r["judging"] == "complete"
