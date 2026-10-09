"""Pinned fixture checks and honest partial-source accounting."""

import numpy as np

from bench.event_retrieval import CAL, DEV, diagnose, evaluate, frozen, prepare
from robot.memory import Memory


class Embed:
    def __call__(self, texts):
        return np.tile(np.eye(384, dtype=np.float32)[0], (len(texts), 1))

    def embed_units(self, text):
        return [{"start": 0, "end": len(text), "text": text, "tokens": 8}], self([text])

def test_frozen_fixtures_and_partial_evidence():
    assert len(frozen(CAL)) == 12
    assert len(frozen(DEV)) == 24
    case = {"expected_source_ids": []}
    result = evaluate(case, {1: "related"}, [{"source_id": 1}])
    assert result["partial_source_returns"] == ["related"]
    assert result["supporting_source_recall"] is None
    assert result["absence_case"]


def test_source_id_with_wrong_kind_does_not_support_fact():
    case = {"expected_source_ids": ["source-a"],
            "sources": [{"id": "source-a", "kind": "observation"}]}
    result = evaluate(case, {1: "source-a"}, [{"source_id": 1, "kind": "utterance"}])
    assert result["source_id_recall"] == 1
    assert result["supporting_source_recall"] == 0


def test_prepare_uses_actual_fixture_utterance_times(tmp_path):
    memory = Memory(tmp_path)
    prepare(memory, Embed(), [{"id": "source-a", "ts": 1.0,
                               "said": "The venue opens at noon.",
                               "utterance_start": 12.0, "utterance_end": 14.0}])
    source = memory.source_event(1, "utterance")
    assert (source["speech_start"], source["speech_end"]) == (12.0, 14.0)
    query = np.eye(384, dtype=np.float32)[0]
    assert memory.events(query, 13.0, 0, 0.5, "utterance") == []
    assert memory.events(query, 15.0, 0, 0.5, "utterance")
    memory.shard.close()


def test_calibration_slot_kind_matches_utterance_event():
    case = {"expected_source_ids": ["source-a"],
            "sources": [{"id": "source-a", "kind": "dialogue"}]}
    result = evaluate(case, {1: "source-a"}, [{"source_id": 1, "kind": "utterance"}])
    assert result["supporting_source_recall"] == 1


def test_diagnostic_selection_ignores_expected_answer_labels(tmp_path):
    memory, embedder = Memory(tmp_path), Embed()
    sources = [{"id": "source-a", "ts": 1.0, "said": "The venue opens at noon.",
                "utterance_start": 2.0, "utterance_end": 3.0, "kind": "utterance"}]
    ids, _, _ = prepare(memory, embedder, sources)
    case = {"question": "When does the venue open?", "query_at": 10.0, "visitor_since": 0,
            "sources": sources, "expected_source_ids": ["source-a"]}
    original = diagnose(memory, embedder, case, ids)
    changed = diagnose(memory, embedder, {**case, "expected_source_ids": []}, ids)
    assert original["selected"] == changed["selected"]
    assert original["after_selection_result"]["supporting_source_recall"] == 1
    assert changed["after_selection_result"]["supporting_source_recall"] is None
    assert not original["unfiltered_ranks"][0]["exclusions"]
    memory.shard.close()
