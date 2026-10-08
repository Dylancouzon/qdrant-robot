"""The judge's majority vote, without calling a model."""
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
