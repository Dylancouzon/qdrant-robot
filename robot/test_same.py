"""Same-object answers: "Is this the same thing I showed you before?" from tracked crops, on the
real tracker and Edge with a stub crop embedder (one fixed vector per pixel value)."""
import queue
import time
from types import SimpleNamespace as Stub

import numpy as np
import pytest

from robot import main
from robot.detect import CONFIRM, Detection
from robot.main import Held, Turn
from robot.test_things import CENTER, LEFT, RIGHT, close_robot, open_robot
from robot.text_embed import DIM as TEXT_DIM
from robot.things import DIM

# What each pixel value embeds to: 200 and 30 are unrelated; 150 is 0.83 from 200, inside
# settings.guess_band below settings.same (0.86).
VECTORS = {200: (1, 0, 0), 150: (0.83, 0.5578, 0), 30: (0, 0, 1), 100: (0, 1, 0)}
ASK = "Is this the same as before?"


def answer(msgs, **_):
    yield "Ok."


def embed(crops: list[np.ndarray]) -> np.ndarray:
    return np.array([VECTORS[int(c.mean())] for c in crops], np.float32)


def held(label: str, value: int, track: int = 1, point: int = 7) -> Held:
    return Held(track, label, [np.full((40, 30, 3), value, np.uint8)] * 2, [10.0, 10.4], point)


@pytest.fixture
def robot(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    monkeypatch.setattr(main, "SETTLE_S", 0)
    r = open_robot(tmp_path)
    r.recognition.crops = embed
    r.asking, r.stream, r.wake_word, r.turns = None, None, False, queue.Queue()
    r.ready, r.last_frame, r.exchanges, r.detections = None, None, 0, 0
    r.out = tmp_path / "out"
    r.out.mkdir()
    r.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[[0] * len(texts)]
    r.knowledge, r.route = Stub(search=lambda q: []), lambda q: "sight"
    r.brain = Stub(prefill=lambda m: None, answer=answer,
                   caption=lambda *_: None)
    r.voice = Stub(say=lambda text: np.zeros(160, np.float32))
    r.speaker = Stub(play=lambda pcm: None)
    yield r
    close_robot(r)


def hold_up(robot, label: str, value: int, box=CENTER, at: float = 100.0) -> None:
    """The tracker sees `label` at `box` for several frames 0.4 s apart; the focus is on it."""
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[box[1]:box[3], box[0]:box[2]] = value
    for k in range(CONFIRM + 2):
        robot._track(frame, [Detection(label, 0.9, box)], at + 0.4 * k)
    robot.focus.focus = next(iter(robot.view[1]))


def test_held_crops(robot) -> None:
    turn = Turn(question=ASK)
    assert robot._hold(turn) is None, "no focus yet"
    hold_up(robot, "phone", 200)
    now = robot._hold(turn)
    assert now.label == "phone" and len(now.shots) == len(now.taken) == main.SHOTS
    assert now.taken == sorted(now.taken, reverse=True), "newest first, as _bind takes them"
    assert all(s.base is None and s.mean() == 200 for s in now.shots), "copies of the crop only"
    hold_up(robot, "person", 30, LEFT, at=200.0)
    robot.focus.focus = next(t for t, (label, _) in robot.view[1].items() if label == "person")
    assert robot._hold(turn) is None, "a person is not an object held up"


def test_same_answers(robot) -> None:
    turn = Turn(question="What is this?")
    assert robot._same_answer(turn, None) is None, "another question: the usual paths"
    turn = Turn(question=ASK)
    assert robot._same_answer(turn, None) == "Hold it up, and I will compare."
    now = held("cup", 200, track=2)
    assert robot._same_answer(turn, now) is None, "nothing earlier: the brain, as before"
    robot.held.append(held("teddy bear", 30, track=1))
    assert robot._same_answer(turn, now) == "No. Earlier you showed me a teddy bear; this is a cup."
    assert turn.compared == {"now": [10.0, 10.4], "earlier": [10.0, 10.4], "score": None,
                             "labels": ["cup", "teddy bear"]} and turn.memories == [7]
    some = lambda *entries: (robot.held.clear(), robot.held.extend(entries))  # noqa: E731
    some(held("teddy bear", 30, track=1), held("mug", 200, track=3))
    assert robot._same_answer(turn, now) == "Yes, it looks like the same mug.", "cup and mug"
    assert turn.compared["score"] == pytest.approx(1.0) and turn.compared["labels"][1] == "mug"
    some(held("mug", 150, track=1))
    assert robot._same_answer(turn, now) == \
        "It looks similar, but I am not sure it is the same mug."
    some(held("mug", 30, track=1))
    assert robot._same_answer(turn, now) == "No, this looks different from the mug you showed me."
    some(held("mug", 30, track=1), held("cup", 150, track=3), held("mug", 100, track=4))
    assert robot._same_answer(turn, now).startswith("It looks similar"), "the best kin decides"
    # A mug, a phone, then a mug again: every earlier object counts, not only the newest.
    some(held("mug", 200, track=1), held("phone", 30, track=2))
    turn = Turn(question="Have you seen this before?")
    assert robot._same_answer(turn, held("mug", 200, track=3)) == \
        "Yes, it looks like the same mug." and turn.memories == [7]
    some(held("phone", 30, track=2))
    now = held("cup", 200, track=5)
    assert robot._same_answer(turn, now) is None, "no word of comparing and no kin: sightings"
    assert robot._same_answer(Turn(question=ASK), now) == \
        "No. Earlier you showed me a phone; this is a cup."
    # One track whose object was swapped in hand, even with another label: MaxSim decides.
    swap = held("phone", 200, track=1)
    some(held("mug", 30, track=1))
    assert robot._same_answer(turn, swap) == "No, this looks different from the mug you showed me."
    some(held("cat", 200, track=1))
    assert robot._same_answer(turn, swap) == "Yes, it looks like the same cat."


def test_turns_compare_in_code_and_deletions_clear(robot) -> None:
    sent = []

    def counted(msgs, **_):
        sent.append(msgs)
        yield "Ok."

    robot.brain.answer = counted
    clock = iter(range(int(time.time()), int(time.time()) + 10_000))
    shot = np.zeros((720, 1280, 3), np.uint8)

    def ask(text: str, gap: float = 1.0) -> Turn:
        t = robot.last_line + gap if robot.last_line else float(next(clock))
        turn = Turn(question=text, speech_start=t, line=t, speech_end=t)
        robot._turn(turn, (shot, t))
        return turn

    hold_up(robot, "teddy bear", 200, LEFT)
    ask("What is this?")
    assert len(robot.held) == 1 and robot.held[0].label == "teddy bear"
    hold_up(robot, "cup", 100, RIGHT, at=110.0)
    asked = len(sent)
    turn = ask(ASK)
    assert turn.answer == "No. Earlier you showed me a teddy bear; this is a cup."
    assert turn.verbatim and len(sent) == asked, "code, not the brain"
    assert turn.compared["labels"] == ["cup", "teddy bear"] and len(robot.held) == 2
    turn = ask("Have you seen this before?")  # the cup again: the earlier cup is the kin
    assert turn.answer == "Yes, it looks like the same cup.", "the same crops"
    assert turn.compared["earlier"] == robot.held[1].taken
    robot.held.clear()
    ask("What is this?")
    hold_up(robot, "cup", 30, RIGHT, at=120.0)  # swapped in hand: one track, new object
    turn = ask("Is this the same cup as the one before?")
    assert turn.answer == "No, this looks different from the cup you showed me." and turn.verbatim
    turn = ask("What did I show you just now?")
    assert not turn.compared, "a recall question keeps its path"
    robot.focus = None
    assert ask("Is this the same thing I showed you earlier?").answer == \
        "Hold it up, and I will compare."
    hold_up(robot, "cup", 200, RIGHT, at=130.0)
    ask("What is this?", gap=main.CONVERSATION_S + 5)
    assert len(robot.held) == 1, "a new conversation forgets what was held"
    robot._clear_object_evidence("any")
    assert not robot.held, "every deletion clears it"
    robot.held.append(held("cup", 200))
    assert robot._forget(None, "Ana", np.zeros(DIM, np.float32), robot.conversation_visitor)
    assert not robot.held, "'forget me'"
