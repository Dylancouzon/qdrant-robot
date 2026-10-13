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
# settings.guess_band below settings.same.
VECTORS = {200: (1, 0, 0), 150: (0.83, 0.5578, 0), 30: (0, 0, 1), 100: (0, 1, 0)}
ASK = "Is this the same as before?"
DIFFERENT = "No, this looks different from the one you showed me."


def answer(msgs, **_):
    yield "Ok."


def embed(crops: list[np.ndarray]) -> np.ndarray:
    """Unit vectors of the shard's size: the pixel value's vector, zero-padded."""
    v = np.zeros((len(crops), DIM), np.float32)
    v[:, :3] = [VECTORS[int(c.mean())] for c in crops]
    return v / np.linalg.norm(v, axis=1, keepdims=True)


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
    assert robot._same_answer(turn, now) == main.NOTHING_EARLIER, "never the brain's default yes"
    assert robot._same_answer(Turn(question="Have you seen this before?"), now) is None, \
        "no word of comparing and nothing earlier: the stored sightings"
    robot.held.append(held("teddy bear", 30, track=1))
    assert robot._same_answer(turn, now) == DIFFERENT, "labels never decide"
    assert turn.compared == {"now": [10.0, 10.4], "earlier": [10.0, 10.4], "score": 0.0,
                             "labels": ["cup", "teddy bear"]} and turn.memories == [7]
    some = lambda *entries: (robot.held.clear(), robot.held.extend(entries))  # noqa: E731
    some(held("teddy bear", 30, track=1), held("mug", 200, track=3))
    assert robot._same_answer(turn, now) == "Yes, it looks like the same one.", "cup and mug"
    assert turn.compared["score"] == pytest.approx(1.0) and turn.compared["labels"][1] == "mug"
    some(held("mug", 150, track=1))
    assert robot._same_answer(turn, now) == \
        "It looks similar, but I am not sure it is the same one."
    some(held("mug", 30, track=1))
    assert robot._same_answer(turn, now) == "No, this looks different from the one you showed me."
    some(held("mug", 30, track=1), held("cup", 150, track=3), held("mug", 100, track=4))
    assert robot._same_answer(turn, now).startswith("It looks similar"), "the best kin decides"
    # A mug, a phone, then a mug again: every earlier object counts, not only the newest.
    some(held("mug", 200, track=1), held("phone", 30, track=2))
    turn = Turn(question="Have you seen this before?")
    assert robot._same_answer(turn, held("mug", 200, track=3)) == \
        "Yes, it looks like the same one." and turn.memories == [7]
    some(held("phone", 30, track=2))
    now = held("cup", 200, track=5)
    assert robot._same_answer(turn, now) == "No, this looks different from the one you showed me."
    assert robot._same_answer(Turn(question=ASK), now) == DIFFERENT
    # One track whose object was swapped in hand, even with another label: MaxSim decides.
    swap = held("phone", 200, track=1)
    some(held("mug", 30, track=1))
    assert robot._same_answer(turn, swap) == "No, this looks different from the one you showed me."
    some(held("cat", 200, track=1))
    assert robot._same_answer(turn, swap) == "Yes, it looks like the same one."


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
    assert turn.answer == "No, this looks different from the one you showed me."
    assert turn.verbatim and len(sent) == asked, "code, not the brain"
    assert turn.compared["labels"] == ["cup", "teddy bear"] and len(robot.held) == 2
    turn = ask("Have you seen this before?")  # the cup again: the earlier cup scores best
    assert turn.answer == "Yes, it looks like the same one.", "the same crops"
    assert turn.compared["earlier"] == robot.held[1].taken
    robot.held.clear()
    ask("What is this?")
    hold_up(robot, "cup", 30, RIGHT, at=120.0)  # swapped in hand: one track, new object
    turn = ask("Is this the same cup as the one before?")
    assert turn.answer == "No, this looks different from the one you showed me." and turn.verbatim
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


def test_named_objects_compare_after_a_restart(robot) -> None:
    """RAM holds are gone after a restart; the visitor's named objects still compare."""
    visitor = "00000000-0000-4000-8000-0000000000aa"
    white = [np.full((12, 20, 3), 200, np.uint8)]
    robot.things.name(visitor, "controller", ["book"], embed(white), white, display="Dylan")
    turn = Turn(question="Am I holding the same controller as I showed you before?",
                visitor=visitor)
    assert not robot.held
    assert robot._same_answer(turn, held("camera", 200)) == "Yes, it looks like the same one."
    assert turn.compared["labels"] == ["camera", "controller"]
    assert robot._same_answer(turn, held("book", 30)) == \
        "No, this looks different from the one you showed me.", "another controller"


def test_a_held_object_moving_keeps_the_answers(robot) -> None:
    """The robot keeps its own answers while the visitor moves the same object (one track); a
    new object in view drops them, as any scene change does (D27)."""
    sent = []

    def counted(msgs, **_):
        sent.append(msgs)
        yield "Ok."

    robot.brain.answer = counted
    start = float(int(time.time()))

    def ask(text: str, at: float, shot: np.ndarray) -> list[str]:
        """The roles of the history in the turn's prompt (its first brain call)."""
        first = len(sent)
        robot._turn(Turn(question=text, speech_start=at, line=at, speech_end=at), (shot, at))
        return [m["role"] for m in sent[first][1:-1]]

    def frame(x: int, value: int = 200) -> np.ndarray:
        f = np.zeros((720, 1280, 3), np.uint8)
        f[300:600, x:x + 200] = value
        return f

    for k, x in enumerate(range(100, 181, 40)):
        robot._track(frame(x), [Detection("cup", 0.9, (x, 300, x + 200, 600))], 100 + 0.4 * k)
    ask("What is this?", start, frame(180))
    for k, x in enumerate(range(220, 541, 40)):  # moved across the frame: the same track
        robot._track(frame(x), [Detection("cup", 0.9, (x, 300, x + 200, 600))], 101 + 0.1 * k)
    assert ask("Do you still see it?", start + 5, frame(540)) == ["user", "assistant"], \
        "its answer stays"
    robot._track(frame(900, 100), [], 103)
    for k in range(CONFIRM + 16):  # the cup leaves; a book appears elsewhere
        robot._track(frame(900, 100), [Detection("book", 0.9, (900, 300, 1100, 600))],
                     103 + 0.1 * k)
    assert ask("And this?", start + 10, frame(900, 100)) == ["user", "user"], \
        "a new view drops the answers"
