"""Generic source selection, calibration, and delivered-span checks without inference."""

import hashlib
import json

import numpy as np
import pytest

from bench import event_retrieval as bench
from robot.memory import Memory


class Embed:
    def __call__(self, texts):
        return np.tile(np.eye(384, dtype=np.float32)[0], (len(texts), 1))

    def embed_units(self, text):
        return [{"start": 0, "end": len(text), "text": text, "tokens": 8}], self([text])


def case():
    return {"id": "generic", "question": "When does the venue open?", "query_at": 10.0,
            "visitor_since": 0, "sources": [],
            "source_kind_labels": [{"source_id": "source-a", "kind": "utterance",
                                    "relevant": True, "sufficient": True}],
            "decisive_spans": [{"source_id": "source-a", "kind": "utterance",
                                "start": 4, "end": 8, "text": "noon"}]}


def entry(kind="utterance", start=0, text="The noon opening."):
    return {"source_id": 1, "kind": kind, "score": 0.8, "text": text,
            "spans": [{"start": start, "end": start + len(text), "text": text}]}


def pairs(scores=(0.8,)):
    return [{"kind": kind, "eligible": True, "relevant": True, "sufficient": False,
             "score": score} for kind in bench.KINDS for score in scores]


def test_frozen_manifest_counts_without_printing_comparison():
    assert len(bench.frozen(bench.CAL)) == 32
    assert len(bench.frozen(bench.DEV)) == 32


def test_wrong_kind_and_missing_decisive_span_are_separate():
    truth, ids = case(), {1: "source-a"}
    wrong = bench.evaluate(truth, ids, [entry("observation")])
    assert wrong["supporting_source_recall"] == 0
    assert wrong["unrelated_returns"] == 1
    partial = bench.evaluate(truth, ids, [entry(text="The venue")])
    assert partial["supporting_source_recall"] == 1
    assert partial["decisive_span_coverage"] == 0
    assert bench.evaluate(truth, ids, [entry()])["decisive_span_coverage"] == 1
    assert bench.evaluate(truth, ids, [entry(text="The dusk opening.")])[
        "decisive_span_coverage"] == 0


def test_absent_but_related_evidence():
    truth = case()
    truth["source_kind_labels"][0]["sufficient"] = False
    truth["decisive_spans"] = []
    result = bench.evaluate(truth, {1: "source-a"}, [entry()])
    assert result["absence_case"]
    assert result["related_returns"] == 1
    assert result["absence_unrelated_returns"] == 0
    assert result["supporting_source_recall"] is None


def test_fixed_grid_includes_relevant_pairs_beyond_five():
    data = pairs((0.91,) * 19 + (0.121,))
    thresholds, counts = bench.calibrate(data)
    assert thresholds == dict.fromkeys(bench.KINDS, 0.91)
    assert counts["utterance"]["recall"] == 0.95
    thresholds, _ = bench.calibrate(pairs((0.91,) * 18 + (0.121,)))
    assert thresholds == dict.fromkeys(bench.KINDS, 0.12)
    thresholds, _ = bench.calibrate(pairs((-1.0, 1.0)))
    assert thresholds == dict.fromkeys(bench.KINDS, -1.0)
    with pytest.raises(ValueError, match="No relevant"):
        bench.calibrate([])


def test_cross_kind_ties_are_deterministic_and_bounded():
    data = [{**entry(kind), "source_id": pid} for kind in reversed(bench.KINDS)
            for pid in reversed(range(1, 8))]
    selected = bench.select(data, dict.fromkeys(bench.KINDS, -1.0))
    assert [(e["kind"], e["source_id"]) for e in selected] == [
        ("observation", pid) for pid in range(1, 6)]


def test_all_pair_inspection_and_gold_independence(tmp_path):
    memory, embedder = Memory(tmp_path), Embed()
    try:
        sources = [{"id": f"source-{i}", "ts": 1.0,
                    "said": "The venue opens at noon.", "caption": "A red schedule.",
                    "utterance_start": 2.0, "utterance_end": 3.0} for i in range(8)]
        ids, _, _ = bench.prepare(memory, embedder, sources)
        truth = {**case(), "sources": sources}
        query = embedder([truth["question"]])[0]
        candidates, ranks = bench.inspect_pairs(memory, query, truth, ids)
        assert len(candidates) == len(ranks) == 16
        changed = {**truth, "source_kind_labels": [], "decisive_spans": []}
        assert bench.inspect_pairs(memory, query, changed, ids) == (candidates, ranks)
        truth["source_kind_labels"] = [
            {"source_id": r["source_id"], "kind": r["kind"], "relevant": True,
             "sufficient": False} for r in ranks]
        scored = bench.calibration_pairs(truth, ranks)
        assert bench.calibrate(scored)[1]["utterance"]["relevant"] == 8
        assert len(bench.select(candidates, dict.fromkeys(bench.KINDS, -1.0))) == 5
    finally:
        memory.shard.close()


def test_actual_speech_and_visitor_eligibility(tmp_path):
    memory, embedder = Memory(tmp_path), Embed()
    try:
        ids, _, _ = bench.prepare(memory, embedder, [{"id": "source-a", "ts": 1.0,
            "said": "My venue opens at noon.", "utterance_start": 12.0, "utterance_end": 14.0}])
        source = memory.source_event(1, "utterance")
        assert (source["speech_start"], source["speech_end"]) == (12.0, 14.0)
        query = embedder(["Venue opening"])[0]
        assert not bench.inspect_pairs(memory, query, {**case(), "query_at": 13}, ids)[0]
        assert bench.inspect_pairs(memory, query, {**case(), "query_at": 15}, ids)[0]
        assert not bench.inspect_pairs(memory, query,
                                       {**case(), "query_at": 15, "visitor_since": 1}, ids)[0]
    finally:
        memory.shard.close()


def test_calibration_receipt_rejects_hash_completion_and_threshold_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "manifest", lambda: {"files": {str(bench.CAL): {"questions": 1}}})
    scored = [{**p, "source_id": "source-a", "case_id": "generic"} for p in pairs()]
    ranks = [{k: v for k, v in p.items() if k not in ("relevant", "sufficient", "case_id")}
             for p in scored]
    truth = {**case(), "source_kind_labels": [{"source_id": "source-a", "kind": kind,
             "relevant": True, "sufficient": False} for kind in bench.KINDS]}
    monkeypatch.setattr(bench, "frozen", lambda path: [truth])
    data = [{"type": "case", "id": "generic", "ranks": ranks}]
    thresholds, counts = bench.calibrate(scored)
    data += [{"type": "calibration_pair", **p, "retained": True} for p in scored]
    prefix = "".join(json.dumps(row) + "\n" for row in data)
    complete = {"type": "complete", "mode": "calibrate", "bindings": {"generic": "hash"},
                "records_sha256": hashlib.sha256(prefix.encode()).hexdigest(),
                "threshold_policy": bench.POLICY, "case_count": 1,
                "thresholds": thresholds, "counts": counts}
    path = tmp_path / "calibration.jsonl"
    def write(receipt):
        path.write_text(prefix + json.dumps(receipt) + "\n")
    write(complete)
    assert bench.load_thresholds(path, {"generic": "hash"}) == thresholds
    with pytest.raises(ValueError, match="provenance"):
        bench.load_thresholds(path, {"generic": "changed"})
    write({**complete, "thresholds": dict.fromkeys(bench.KINDS, 0.9)})
    with pytest.raises(ValueError, match="threshold"):
        bench.load_thresholds(path, {"generic": "hash"})
    write({**complete, "records_sha256": "bad"})
    with pytest.raises(ValueError, match="provenance"):
        bench.load_thresholds(path, {"generic": "hash"})
    path.write_text(prefix)
    with pytest.raises(ValueError, match="incomplete"):
        bench.load_thresholds(path, {"generic": "hash"})
