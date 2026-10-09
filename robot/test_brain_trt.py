"""Check native request serialization and cancellation, without claiming model inference."""

import base64
import queue
import threading
from types import SimpleNamespace as Stub

import pytest
import numpy as np

from robot.brain import Brain, native_request
from robot.main import Robot


def bindings():
    return Stub(
        MessageContent=lambda kind, content: Stub(type=kind, content=content),
        Message=lambda role, contents: Stub(role=role, contents=contents),
        Request=lambda **kwargs: Stub(**kwargs),
        LLMGenerationRequest=Stub,
        load_image_from_bytes=lambda data: data,
    )


def test_source_image_and_evidence_order():
    rt = bindings()
    image = {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64," + base64.b64encode(b"source JPEG").decode()}}
    request = native_request(rt, [{"role": "user", "content": [
        image, {"type": "text", "text": "Memories: source point 23"}]}], 64)
    row = request.requests[0]
    assert row.image_buffers == [b"source JPEG"]
    assert [(part.type, part.content) for part in row.messages[0].contents] == [
        ("image", ""), ("text", "Memories: source point 23")]
    assert request.max_generate_length == 64 and not request.enable_thinking
    with pytest.raises(ValueError, match="source-owned"):
        native_request(rt, [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "https://example.com/frame.jpg"}}]}], 64)


class Channel:
    def __init__(self):
        self.queue = queue.Queue()
        self.cancelled = threading.Event()
        self.finished = False

    def set_skip_special_tokens(self, value):
        assert value

    def wait_pop(self, timeout_ms):
        try:
            return self.queue.get(timeout=timeout_ms / 1000)
        except queue.Empty:
            return None

    def cancel(self):
        self.cancelled.set()

    def is_cancelled(self):
        return self.cancelled.is_set()

    def is_finished(self):
        return self.finished


def test_close_cancels_and_joins_before_next_generation():
    brain = Brain.__new__(Brain)
    brain.rt, brain.lock, brain.channel = bindings(), threading.Lock(), None
    brain.closed, brain.worker = False, None
    channels, retired = [], []

    def create():
        channel = Channel()
        channels.append(channel)
        return channel

    def generate(request):
        channel = request.stream_channels[0]
        channel.queue.put(Stub(text="Hello", finished=False))
        assert channel.cancelled.wait(2), "close must cancel native generation"
        retired.append(channel)

    brain.rt.StreamChannel = Stub(create=create)
    brain.runtime = Stub(handle_request=generate)
    brain.context = lambda msgs, max_tokens: msgs
    first = brain.answer([{"role": "user", "content": "Hi"}])
    assert next(first) == "Hello"
    first.close()
    assert retired == channels and brain.channel is None
    second = brain.answer([{"role": "user", "content": "Again"}])
    assert next(second) == "Hello"
    brain.close()  # a paused consumer cannot prevent shutdown from joining its producer
    assert len(retired) == 2 and brain.runtime is None
    second.close()
    with pytest.raises(RuntimeError, match="closed"):
        next(brain.answer([]))


def test_template_budget_preserves_image_position_and_complete_exchanges(monkeypatch):
    brain = Brain.__new__(Brain)
    brain.rt, brain.image_tokens, brain.input_tokens = bindings(), 512, 2048
    requests = []

    def count(request):
        requests.append(request)
        return [1600 if len(request.requests[0].messages) > 2 else 100]

    brain.runtime = Stub(count_prompt_tokens=count)
    image = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,eA=="}}
    history = [{"role": "user", "content": "Old"}, {"role": "assistant", "content": "Answer"}]
    robot = Robot.__new__(Robot)
    robot.history, robot.exchanges = history, 1
    robot.last_frame = np.zeros((2, 2, 3), dtype=np.uint8)
    monkeypatch.setattr("robot.main.scene_change", lambda previous, current: float("inf"))
    monkeypatch.setattr("robot.main.brain.jpeg", lambda frame: image)
    robot._look((np.ones((2, 2, 3), dtype=np.uint8), 1.0))
    assert robot.ready.changed and robot.ready.history == history
    current = {"role": "user", "content": [robot.ready.image,
                                           {"type": "text", "text": "Where?"}]}
    system = {"role": "system", "content": "Use source evidence"}
    assert brain.context([system, *robot.ready.history, current]) == [system, current]
    assert history == [{"role": "user", "content": "Old"},
                       {"role": "assistant", "content": "Answer"}]
    for request in requests:
        assert not request.requests[0].image_buffers
        parts = request.requests[0].messages[-1].contents
        assert [p.content for p in parts] == ["<|image|>", "Where?"]
