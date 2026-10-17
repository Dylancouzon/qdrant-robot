"""Visitor filtering, statement admission, persistence, and deletion on real Edge stores."""
import numpy as np
import pytest

from robot.memory import Filter, HasVectorCondition, Memory, ScrollRequest, is_statement
from robot.text_embed import DIM


def vector(first=1.):
    result = np.zeros(DIM, np.float32)
    result[:2] = first, np.sqrt(1 - first * first)
    return result


def quotes(memory, visitor):
    """The answers of this visitor's quoted exchanges before t=200."""
    return [row["answer"] for row in memory.exchanges(visitor, 200, 5, vector(), "answer")]


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
    memory.add(None, "Where is it stored?", ts=100, dialog_vec=vector(), visitor="Mira",
               answer="In Qdrant Edge.")
    memory.add(None, "Hi!", ts=110, dialog_vec=vector(), visitor="Jo", answer="Hello!")
    memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert quotes(memory, "Mira") == ["In Qdrant Edge."]
        memory.forget_visitor("Mira")
        assert quotes(memory, "Mira") == []
        assert quotes(memory, "Jo") == ["Hello!"]
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
    memory.add(None, "I bought it in Paris.", vector(), ts=100, dialog_vec=vector(),
               visitor="Mira", answer="You bought it in Paris.")
    memory.add(None, "Hi!", ts=101, dialog_vec=vector(), visitor="Jo", answer="Hello!")
    memory.forget_answers("Mira")
    memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert quotes(memory, "Mira") == [], "no quote of the pronoun-only answer"
        assert quotes(memory, "Jo") == ["Hello!"]
    finally:
        memory.shard.close()


def test_backfill_gives_old_answers_vectors_and_forget_answers_removes_them(tmp_path):
    embed = lambda texts: np.stack([vector() for _ in texts])  # noqa: E731
    with_dialog = lambda m: [r.id for r in m.shard.scroll(ScrollRequest(  # noqa: E731
        limit=10, filter=Filter(must=[HasVectorCondition("dialog")])))[0]]
    memory = Memory(tmp_path)
    old = memory.add(None, "Is it fast?", ts=100, visitor="Mira", answer="Under 1 ms.")
    new = memory.add(None, "Where?", ts=101, dialog_vec=vector(), visitor="Mira", answer="Here.")
    memory.add(None, "No answer stored.", ts=102, visitor="Mira")
    memory.shard.close()
    memory = Memory(tmp_path)  # as after a rollback write: vectors created, one turn missing
    try:
        assert sorted(with_dialog(memory)) == [new]
        assert memory.backfill(embed) == 1 and memory.backfill(embed) == 0
        assert sorted(with_dialog(memory)) == [old, new]
        memory.forget_answers("Mira")
        assert with_dialog(memory) == [] and quotes(memory, "Mira") == []
    finally:
        memory.shard.close()


def test_backfill_drops_vectors_an_older_release_left_after_forgetting(tmp_path):
    from robot.memory import Filter, FieldCondition, MatchValue, UpdateOperation
    memory = Memory(tmp_path)
    memory.add(None, "I bought it in Paris.", ts=100, dialog_vec=vector(), visitor="Mira",
               answer="You bought it in Paris.")
    # An older release forgets the answer payload only.
    memory.shard.update(UpdateOperation.delete_payload_by_filter(Filter(must=[FieldCondition(
        key="visitor", match=MatchValue("Mira"))]), ["answer"]))
    memory.shard.close()
    memory = Memory(tmp_path)
    try:
        assert memory.backfill(lambda texts: np.stack([vector() for _ in texts])) == 0
        assert quotes(memory, "Mira") == []
        assert not memory.shard.scroll(ScrollRequest(limit=5, filter=Filter(
            must=[HasVectorCondition("dialog")])))[0], "no answer-derived vector survives"
    finally:
        memory.shard.close()


def test_rollback_strip_removes_every_answer_vector_and_backfill_restores_them(tmp_path):
    memory = Memory(tmp_path)
    try:
        kept = memory.add(None, "Is it fast?", ts=100, dialog_vec=vector(), visitor="Mira",
                          answer="Under 1 ms.")
        memory.drop_exchange_vectors()
        with_dialog = Filter(must=[HasVectorCondition("dialog")])
        assert not memory.shard.scroll(ScrollRequest(limit=5, filter=with_dialog))[0]
        assert not memory.shard.scroll(ScrollRequest(limit=5, filter=Filter(
            must=[HasVectorCondition("words")])))[0]
        assert memory.backfill(lambda texts: np.stack([vector() for _ in texts])) == 1
        assert [r.id for r in memory.shard.scroll(ScrollRequest(limit=5, filter=with_dialog))[
            0]] == [kept]
    finally:
        memory.shard.close()
