"""Decode pauses at the first phrase and resumes with the same answer (D66); an interrupted turn
closes the brain's stream, whether it fails in the first synthesis or after the resume."""
from types import SimpleNamespace as Stub

import numpy as np
import pytest

from robot.main import Robot, Turn

REPLY = ["Nice ", "to ", "meet ", "you. ", "I ", "am ", "Edgy. ", "I ", "run ", "on ", "a ",
         "Jetson."]


class FakeBrain:
    """brain.Brain.answer: one delta per word, resumed after `prior`; counts open streams."""

    def __init__(self):
        self.priors, self.open = [], 0

    def answer(self, msgs, max_tokens=64, prior=""):
        self.priors.append(prior)
        self.open += 1
        try:
            yield from REPLY[min(k for k in range(len(REPLY) + 1)
                                 if len("".join(REPLY[:k])) >= len(prior)):]
        finally:
            self.open -= 1


def robot(fail_at: int = 0) -> Robot:
    r = Robot.__new__(Robot)  # only what _tokens and _speak use
    r.brain, r.stream, said = FakeBrain(), None, []

    def say(text: str) -> np.ndarray:
        said.append(text)
        if len(said) == fail_at:
            raise RuntimeError("synthesis failed")
        return np.zeros(160, np.float32)

    r.voice, r.speaker = Stub(say=say), Stub(play=lambda pcm: None)
    return r


def test_pause_and_resume() -> None:
    r, turn = robot(), Turn()
    assert len(r._speak(r._tokens([], turn), turn)) == 3
    assert turn.answer == "".join(REPLY) and turn.resumed
    assert r.brain.priors == ["", "Nice to meet you. "], "resumed after the first phrase"
    assert r.brain.open == 0 and r.stream is None


@pytest.mark.parametrize("fail_at", [1, 2])
def test_interrupted(fail_at: int) -> None:
    r, turn = robot(fail_at), Turn()
    tokens = r._tokens([], turn)  # held, so only _speak's close can stop it
    with pytest.raises(RuntimeError):
        r._speak(tokens, turn)
    assert r.brain.open == 0 and r.stream is None, "no stream left decoding"
    assert len(r.brain.priors) == fail_at, "a failed first synthesis never resumes"
