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
