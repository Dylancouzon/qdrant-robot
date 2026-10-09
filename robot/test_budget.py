"""Evidence roles, complete-exchange budgeting, and dialogue request consistency."""
import json
from contextlib import contextmanager

import pytest

from robot import brain


def test_evidence_sequence():
    history = [{"role": "user", "content": "Earlier question?"},
               {"role": "assistant", "content": "An incorrect old answer."}]
    now = "speech-start camera frame captured at 123.456, 0 seconds ago: no"
    memories = ["2 minutes ago: a red bus"]
    told = ["1 minute ago: I live in Lisbon."]
    facts = ["Qdrant is a vector search engine."]
    msgs = brain.messages(history, now, memories, facts, "What did I show you?", True, told)
    assert msgs[1:3] == history
    assert msgs[3] == {"role": "user", "content": "What did I show you?"}
    call = msgs[4]["tool_calls"][0]
    assert call["type"] == "function" and call["function"] == {
        "name": brain.EVIDENCE_TOOL["function"]["name"], "arguments": "{}"}
    assert msgs[5] == {"role": "tool", "tool_call_id": call["id"], "content":
                         f"Camera now:\n- {now}\n\n{brain.EVIDENCE}"
                         "Memories:\n- 2 minutes ago: a red bus\n\n"
                         "The visitor told you:\n- 1 minute ago: I live in Lisbon.\n\n"
                         "Facts:\n- Qdrant is a vector search engine.\n\n" + brain.PAST}
    plain = brain.messages(history, question="Tell me a joke.")
    assert plain == [{"role": "system", "content": brain.SYSTEM}, *history,
                     {"role": "user", "content": "Tell me a joke."}]
    assert "tools" not in brain.template(plain)
    assert history == msgs[1:3]  # synthetic calls/results never enter retained exchanges


def test_evidence_budget():
    b = brain.Brain.__new__(brain.Brain)
    b.rendered = lambda msgs: 100 + 100 * sum(m["role"] == "user" for m in msgs)
    history = [{"role": role, "content": f"{role} {i}"}
               for i in range(50) for role in ("user", "assistant")]
    msgs, kept, budget = b.context(history, "Exact camera source.", question="Now?")
    assert 0 < len(kept) < len(history) and kept == history[-len(kept):]
    assert len(kept) % 2 == 0 and all(m["role"] != "tool" for m in kept)
    assert msgs[1:1 + len(kept)] == kept
    assert "Exact camera source." in msgs[-1]["content"]
    assert budget["rendered_tokens"] + brain.MAX_TOKENS <= brain.CONTEXT_TOKENS
    assert b.rendered(brain.messages(history[-len(kept) - 2:], "Exact camera source.",
                                     question="Now?")) + brain.MAX_TOKENS > brain.CONTEXT_TOKENS
    b.rendered = lambda msgs: brain.CONTEXT_TOKENS
    with pytest.raises(ValueError, match="current evidence"):
        b.context([], "Exact camera source.", question="Now?")


def test_template_generation_resume(monkeypatch):
    b = brain.Brain.__new__(brain.Brain)
    msgs = brain.messages([], "A stop sign is on a table.", question="What am I holding?")
    rendered, submitted = [], []

    def fake_json(path, body):
        if path == "apply-template":
            rendered.append(body)
            return {"prompt": "rendered"}
        return {"tokens": [1, 2]}

    @contextmanager
    def fake_open(req, timeout):
        submitted.append(json.loads(req.data))
        prior = submitted[-1]["messages"][-1]
        delta = (prior["content"] if prior["role"] == "assistant" else "") + " More text."
        class Response:
            def read(self):
                return b""

            def __iter__(self):
                yield ("data: " + json.dumps({"choices": [{"delta": {"content": delta}}]})).encode()
        yield Response()

    monkeypatch.setattr(b, "_json", fake_json)
    monkeypatch.setattr(brain.urllib.request, "urlopen", fake_open)
    assert b.rendered(msgs) == 2
    b.prefill(msgs)
    assert list(b.answer(msgs)) == [" More text."]
    assert list(b.answer(msgs, prior="Partial answer.")) == [" More text."]
    metadata = brain.template(msgs)
    assert metadata["tool_choice"] == "none" and metadata["tools"] == [brain.EVIDENCE_TOOL]
    for body in [*rendered, *submitted]:
        assert {key: body[key] for key in metadata} == metadata
    assert submitted[-1]["messages"] == msgs + [{"role": "assistant", "content": "Partial answer."}]
    assert submitted[-1]["max_tokens"] == brain.MAX_TOKENS - 2
    assert submitted[-1]["messages"][:-1] == rendered[0]["messages"]
    assert all(body["repeat_penalty"] == 1.0 for body in submitted[1:])
    assert brain.MAX_TOKENS == 128 and brain.CONTEXT_TOKENS == 4096
