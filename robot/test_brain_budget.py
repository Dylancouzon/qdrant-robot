"""The rendered prompt bound includes template markers, image reserve, and spoken output."""

from robot.brain import Brain, CONTEXT_TOKENS, IMAGE_TOKENS, MAX_TOKENS


def test_budget_renders_all_messages_and_counts_special_tokens(monkeypatch):
    brain = Brain.__new__(Brain)
    calls = []
    messages = [{"role": "system", "content": "system"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,x"}},
                    {"type": "text", "text": "question"}]}]

    def response(path, body):
        calls.append((path, body))
        return ({"prompt": "<special>rendered"} if path == "apply-template"
                else {"tokens": [1, 2, 3]})

    monkeypatch.setattr(brain, "_json", response)
    assert brain.budget(messages) == {
        "rendered_tokens": 3, "image_token_reserve": IMAGE_TOKENS,
        "prompt_token_bound": 3 + IMAGE_TOKENS,
        "output_token_reserve": MAX_TOKENS, "context_tokens": CONTEXT_TOKENS}
    assert calls[0] == ("apply-template", {"messages": messages,
                                          "chat_template_kwargs": {"enable_thinking": False}})
    assert calls[1] == ("tokenize", {"content": "<special>rendered", "parse_special": True,
                                    "add_special": False})


def test_text_only_budget_has_no_image_reserve(monkeypatch):
    brain = Brain.__new__(Brain)
    monkeypatch.setattr(brain, "_json", lambda path, body: {"prompt": "rendered"}
                        if path == "apply-template" else {"tokens": [1] * 1985})
    budget = brain.budget([{"role": "user", "content": "long question"}])
    assert budget["image_token_reserve"] == 0
    assert budget["prompt_token_bound"] + budget["output_token_reserve"] > CONTEXT_TOKENS


def test_context_drops_ranked_spans_before_complete_history(monkeypatch):
    brain = Brain.__new__(Brain)
    history = [{"role": "user", "content": "older question"},
               {"role": "assistant", "content": "older answer"},
               {"role": "user", "content": "newer question"},
               {"role": "assistant", "content": "newer answer"}]
    events = [{"source_id": i, "kind": "utterance", "capture_ts": 100.,
               "text": f"source {i}", "source_hash": str(i), "spans": []} for i in (1, 2)]
    calls = []

    def budget(msgs):
        calls.append(msgs)
        final = msgs[-1]["content"][-1]["text"]
        count = 1800 + 200 * (len(msgs) - 2) + 200 * final.count("source")
        return {"prompt_token_bound": count, "output_token_reserve": MAX_TOKENS}

    monkeypatch.setattr(brain, "budget", budget)
    msgs, kept, bound = brain.context(history, None, events, question="current question")
    assert [event["source_id"] for event in bound["dropped_events"]] == [2, 1]
    assert kept == [] and bound["history_turns_removed"] == 2
    assert "current question" in msgs[-1]["content"][-1]["text"]
    assert len(calls[2]) == 6  # both old exchanges survived until all evidence was removed
    assert calls[3][1:-1] == history[2:]  # the newer complete exchange survived first
    assert history[0]["content"] == "older question" and len(events) == 2


def test_context_preserves_exact_spans_and_capture_order(monkeypatch):
    brain = Brain.__new__(Brain)
    events = [{"kind": "observation", "capture_ts": 90., "text": "newer", "spans": ["n"]},
              {"kind": "observation", "capture_ts": 10., "text": "older", "spans": ["o"]}]
    monkeypatch.setattr(brain, "budget", lambda msgs: {
        "prompt_token_bound": 500, "output_token_reserve": MAX_TOKENS})
    msgs, kept, bound = brain.context([], None, events, question="what?", before=100.)
    text = msgs[-1]["content"][-1]["text"]
    assert text.index("older") < text.index("newer")
    assert kept == events and bound["dropped_events"] == []


def test_context_rejects_fixed_input_overflow(monkeypatch):
    import pytest
    brain = Brain.__new__(Brain)
    monkeypatch.setattr(brain, "budget", lambda msgs: {
        "prompt_token_bound": CONTEXT_TOKENS, "output_token_reserve": MAX_TOKENS})
    with pytest.raises(ValueError, match="fixed facts"):
        brain.context([], None, question="current question")
