"""Judge voting and preceding-conversation context, without calling a model."""
import json

from bench.conversation import contextual_cases
from eval.judge import key, vote


def test_vote() -> None:
    a, b = {"pass": True, "why": "ok"}, {"pass": False, "why": "no"}
    assert vote([[a], [b], [a]]) == [{**a, "votes": [True, False, True]}]
    assert vote([[b], [b], [a]])[0]["pass"] is False


def test_key() -> None:
    item = {"rubric": "Says a mug.", "visitor": "What is this?", "robot": "A mug."}
    assert key(item) == key(dict(item))
    assert key(item) != key(item, model="other") and key(item) != key(item, prompt="other")
    assert key(item) != key({**item, "robot": "A cup."})


def test_grading_context_has_no_current_answer_or_other_session():
    sessions = [{"id": "one", "steps": [
        {"id": "a", "say": "Hi.", "rubric": "Greet the visitor."},
        {"id": "b", "say": "Why?", "rubric": "Follow the previous answer."}]},
        {"id": "two", "steps": [{"id": "c", "say": "Hello.", "rubric": "Greet."}]}]
    rows = [{"id": key, "heard": key, "answer": answer}
            for key, answer in (("a", "first"), ("b", "second"), ("c", "third"))]
    prepared = contextual_cases(sessions, rows)
    contexts = [step["rubric"].split("Preceding conversation: ")[1]
                for session in prepared for step in session["steps"]]
    assert [json.loads(text) for text in contexts] == [
        [], [{"visitor": "a", "robot": "first"}], []]
    assert sessions[0]["steps"][0]["rubric"] == "Greet the visitor."
