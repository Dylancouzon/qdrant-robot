"""Visitor filtering, statement admission, persistence, and deletion on real Edge stores."""
import numpy as np
import pytest

from robot.memory import Memory, is_statement
from robot.text_embed import DIM


def vector(first=1.):
    result = np.zeros(DIM, np.float32)
    result[:2] = first, np.sqrt(1 - first * first)
    return result


def test_visitor_filter_precedes_similarity_limit_and_rejects_unowned_points(tmp_path):
    memory = Memory(tmp_path)
    try:
        own = memory.add(None, "I prefer tea.", vector(.8), ts=100, visitor="Mira")
        for _ in range(8):
            memory.add(None, "I prefer coffee.", vector(), ts=100, visitor="Jo")
        memory.add(None, "Legacy unowned statement.", vector(), ts=100)
        memory.add(None, "Future statement.", vector(), ts=300, visitor="Mira")
        assert [row["id"] for row in memory.told(
            vector(), before=200, visitor="Mira", n=1)] == [own]
        assert memory.told(vector(), before=100, visitor="Mira") == []
        assert memory.told(vector(), before=200, visitor="") == []
        assert memory.told(vector(), before=200, visitor="new-guest") == []
    finally:
        memory.shard.close()


def test_visitor_statement_survives_reopen_and_forget_removes_only_that_visitor(tmp_path):
    memory = Memory(tmp_path)
    own = memory.add(None, "My favorite season is autumn.", vector(), ts=100, visitor="Mira")
    other = memory.add(None, "The event starts at nine.", vector(), ts=100, visitor="Jo")
    memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert [row["id"] for row in memory.told(vector(), 200, visitor="Mira")] == [own]
        memory.forget_visitor("Mira")
    finally:
        memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert memory.told(vector(), 200, visitor="Mira") == []
        assert not memory.points([own])
        assert [row["id"] for row in memory.told(vector(), 200, visitor="Jo")] == [other]
    finally:
        memory.shard.close()


@pytest.mark.parametrize("text", ["", "  ", "Okay.", "THANK YOU!", "Yes", "No.", "um", "Hmm?",
                                 "What drink do I like?", "Is this blue."])
def test_questions_and_bare_acknowledgements_are_not_statements(text):
    assert not is_statement(text)


@pytest.mark.parametrize("text", ["I like tea.", "I'm tired.", "The booth closes at five.",
                                 "No sugar.", "Yes, I enjoy hiking.", "Thank you for the book."])
def test_short_meaningful_statements_remain_searchable(text):
    assert is_statement(text)


def test_exchanges_survive_reopen_and_forget_me_deletes_them(tmp_path):
    memory = Memory(tmp_path)
    memory.add(None, "Where is it stored?", ts=100, visitor="Mira", answer="In Qdrant Edge.")
    memory.add(None, "Hi!", ts=110, visitor="Jo", answer="Hello!")
    memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert [row["answer"] for row in memory.exchanges("Mira", 200, n=5)] == ["In Qdrant Edge."]
        memory.forget_visitor("Mira")
        assert memory.exchanges("Mira", 200, n=5) == []
        assert [row["answer"] for row in memory.exchanges("Jo", 200, n=5)] == ["Hello!"]
    finally:
        memory.shard.close()


def test_forgetting_an_object_forgets_what_was_said_about_it(tmp_path):
    memory = Memory(tmp_path)
    try:
        said = memory.add(None, "Where is my umbrella?", ts=100, visitor="Mira",
                          answer="I last saw your umbrella a minute ago.")
        told = memory.add(None, "My Umbrella is from Paris.", vector(), ts=101, visitor="Mira")
        other = memory.add(None, "Where is it stored?", ts=102, visitor="Mira", answer="On disk.")
        theirs = memory.add(None, "I lost my umbrella.", vector(), ts=103, visitor="Jo")
        memory.forget_mentions("Mira", {"umbrella"})
        assert not memory.points([said, told])
        assert [p["id"] for p in memory.points([other, theirs])] == [other, theirs]
    finally:
        memory.shard.close()


def test_forgetting_answers_survives_reopen_and_keeps_other_visitors(tmp_path):
    memory = Memory(tmp_path)
    memory.add(None, "I bought it in Paris.", vector(), ts=100, visitor="Mira",
               answer="You bought it in Paris.")
    memory.add(None, "Hi!", ts=101, visitor="Jo", answer="Hello!")
    memory.forget_answers("Mira")
    memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert memory.exchanges("Mira", 200, n=5) == [], "no quote of the pronoun-only answer"
        assert [row["answer"] for row in memory.exchanges("Jo", 200, n=5)] == ["Hello!"]
    finally:
        memory.shard.close()
