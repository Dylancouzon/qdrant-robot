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
