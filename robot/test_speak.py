"""Native decode continues through speech synthesis; interruption closes its stream."""
from types import SimpleNamespace as Stub

import numpy as np
import pytest

from robot.main import Robot, Turn

REPLY = ["Nice ", "to ", "meet ", "you. ", "I ", "am ", "Edgy. ", "I ", "run ", "on ", "a ",
         "Jetson."]


class FakeBrain:
    """Count active answer streams while the robot speaks."""

    def __init__(self):
        self.calls, self.open = 0, 0

    def answer(self, msgs, max_tokens=64):
        self.calls += 1
        self.open += 1
        try:
            yield from REPLY
        finally:
            self.open -= 1


def robot(fail_at: int = 0) -> Robot:
    r = Robot.__new__(Robot)  # only what _tokens and _speak use
    r.brain, r.stream, said = FakeBrain(), None, []

    def say(text: str) -> np.ndarray:
        assert r.brain.open == 1, "generation stays active through synthesis"
        said.append(text)
        if len(said) == fail_at:
            raise RuntimeError("synthesis failed")
        return np.zeros(160, np.float32)

    r.voice, r.speaker = Stub(say=say), Stub(play=lambda pcm: None)
    return r


def test_uninterrupted() -> None:
    r, turn = robot(), Turn()
    assert len(r._speak(r._tokens([], turn), turn)) == 3
    assert turn.answer == "".join(REPLY)
    assert r.brain.calls == 1
    assert r.brain.open == 0 and r.stream is None


@pytest.mark.parametrize("fail_at", [1, 2])
def test_interrupted(fail_at: int) -> None:
    r, turn = robot(fail_at), Turn()
    tokens = r._tokens([], turn)  # held, so only _speak's close can stop it
    with pytest.raises(RuntimeError):
        r._speak(tokens, turn)
    assert r.brain.open == 0 and r.stream is None, "no stream left decoding"
    assert r.brain.calls == 1, "interruption cancels the single generation"
