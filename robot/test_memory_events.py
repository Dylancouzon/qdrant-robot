"""Generic source lifecycle checks; no challenge data."""

from pathlib import Path

import numpy as np
import pytest
from qdrant_edge import CountRequest

from robot.memory import Memory, RETAIN_S

FRAME = np.zeros((36, 64, 3), np.uint8)
VECTORS = np.eye(384, dtype=np.float32)[:2]


def index(memory, pid, kind, text, vectors=VECTORS[:1], **times):
    source = memory.source_event(pid, kind)
    return memory.index_event(
        pid,
        kind,
        source["source_hash"],
        [{"start": 0, "end": len(text), "text": text, "tokens": 8}],
        vectors,
        **times,
    )


def test_source_lifecycle_and_legacy(tmp_path):
    memory = Memory(tmp_path)
    pid = memory.add(FRAME, "I like tea. The booth closes at five.", ts=100.0)
    memory.set(pid, caption="A red cup.")
    assert index(memory, pid, "observation", "A red cup.")
    assert index(
        memory,
        pid,
        "utterance",
        "I like tea. The booth closes at five.",
        speech_start=101.0,
        speech_end=102.0,
    )
    observed = memory.events(VECTORS[0], 200.0, pid, 0.0, "observation")
    assert observed[0]["text"] == "A red cup."
    assert "said" not in observed[0] and observed[0]["scope"] == "shared"
    assert memory.events(VECTORS[0], 200.0, pid, 0.0, "utterance") == []
    speech = memory.events(VECTORS[0], 200.0, 0, 0.0, "utterance")[0]
    assert (speech["speech_start"], speech["speech_end"]) == (101.0, 102.0)
    old = memory.source_event(pid, "observation")
    memory.set(pid, caption="A blue cup.")  # rollback writes invalidate the old slot
    assert memory.events(VECTORS[0], 200.0, 0, 0.0, "observation") == []
    assert not memory.index_event(
        pid,
        "observation",
        old["source_hash"],
        [{"start": 0, "end": 10, "text": "A red cup.", "tokens": 8}],
        VECTORS[:1],
    )
    assert memory.recent(200.0)[0]["caption"] == "A blue cup."
    assert memory.events(VECTORS[0], 200.0, 0, 0.0, "utterance")
    memory.shard.close()
    memory = Memory(tmp_path)
    assert memory.events(VECTORS[0], 200.0, pid, 0.0, "utterance") == []  # restart boundary
    assert memory.recent(200.0)[0]["caption"] == "A blue cup."
    jpg = memory.points([pid])[0]["frame"]
    source = memory.source_event(pid, "utterance")
    memory.forget([pid])
    assert not (tmp_path / "frames" / jpg).exists()
    assert not memory.index_event(
        pid,
        "utterance",
        source["source_hash"],
        [{"start": 0, "end": len(source["text"]), "text": source["text"], "tokens": 8}],
        VECTORS[:1],
    )
    assert memory.shard.count(CountRequest()) == 0
    memory.shard.close()


def test_distinct_overflow_reopen_retention(tmp_path):
    memory = Memory(tmp_path)
    pid = memory.add(FRAME, "question?", ts=100.0)
    text = "A red cup. A blue bag."
    memory.set(pid, caption=text)
    source = memory.source_event(pid, "observation")
    units = [
        {"start": 0, "end": 11, "text": text[:11], "tokens": 8},
        {"start": 11, "end": len(text), "text": text[11:], "tokens": 8},
    ]
    with pytest.raises(ValueError, match="overflow"):
        memory.index_event(pid, "observation", source["source_hash"], units[:1], VECTORS[:1])
    assert memory.index_event(pid, "observation", source["source_hash"], units, VECTORS)
    memory.shard.close()
    memory = Memory(tmp_path)
    assert memory.events(VECTORS[1], 200.0, 0, 0.9, "observation")[0]["text"] == text[11:]
    assert memory.events(VECTORS[1], 200.0, 0, 0.9, "observation", skip=lambda s: "bag" in s) == []
    assert memory.events(VECTORS[1], RETAIN_S + 200.0, 0, 0.9, "observation") == []
    assert memory.retain(RETAIN_S + 200.0, ()) == [pid]
    assert not list((tmp_path / "frames").glob("*.jpg"))
    memory.shard.close()


def test_shared_and_private_sources(tmp_path):
    memory = Memory(tmp_path)
    private = memory.add(FRAME, "My favorite fruit is pear.", ts=100.0)
    shared = memory.add(FRAME, "The booth closes at five.", ts=101.0)
    assert index(memory, private, "utterance", "My favorite fruit is pear.")
    assert index(memory, shared, "utterance", "The booth closes at five.")
    events = memory.events(VECTORS[0], 200.0, private, 0.9, "utterance")
    assert [e["source_id"] for e in events] == [shared]
    assert events[0]["speech_start"] is None  # capture time is not speech time
    assert (
        memory.source_event(private, "utterance")["source_hash"]
        != (memory.source_event(shared, "utterance")["source_hash"])
    )
    with pytest.raises(ValueError, match="Unknown"):
        memory.source_event(shared, "assistant")
    memory.shard.close()


def test_newest_first_legacy(tmp_path: Path):
    memory = Memory(tmp_path)
    for ts in (100.0, 300.0, 200.0):
        pid = memory.add(FRAME, "question?", ts=ts)
        memory.set(pid, caption=f"Main object: cup {ts}.")
        assert index(memory, pid, "observation", f"Main object: cup {ts}.")
    assert [r["ts"] for r in memory.recent(400.0)] == [300.0, 200.0, 100.0]
    memory.shard.close()


def test_actual_speech_after_query(tmp_path):
    memory = Memory(tmp_path)
    pid = memory.add(FRAME, "The booth closes at five.", ts=100.)
    assert index(memory, pid, "utterance", "The booth closes at five.",
                 speech_start=250., speech_end=251.)
    assert memory.events(VECTORS[0], 200., 0, .9, "utterance") == []
    assert memory.events(VECTORS[0], 300., 0, .9, "utterance")
    memory.shard.close()
