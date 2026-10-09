"""Naming, recall by name, forget, and ignore through the robot's own tracking and
answers, on real Edge shards and the real tracker, with a stub crop embedder (one vector per
color), including restarts."""
import queue
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

from robot import main
from robot.detect import CONFIRM, LOST, Detection, Tracker
from robot.main import Robot, Turn
from robot.memory import CountRequest, Memory, ScrollRequest
from robot.text_embed import DIM as TEXT_DIM
from robot.things import DIM, SHOTS, Things

GOLD, BLACK = 200, 30  # the pixel value of each phone: the stub tells them apart by it
LEFT, CENTER, RIGHT = (100, 300, 300, 600), (540, 300, 740, 600), (1000, 300, 1200, 600)


def stub_crops(crops: list[np.ndarray]) -> np.ndarray:
    return np.eye(DIM, dtype=np.float32)[[int(c.mean()) for c in crops]]


def open_robot(root: Path) -> Robot:
    robot = Robot.__new__(Robot)  # no models: memory, things, tracker, and the stub embedder
    robot.memory, robot.things, robot.crops = Memory(root), Things(root), stub_crops
    robot.named, robot.ignored = robot.things.labels(), robot.things.ignored()
    robot.tracker, robot.points, robot.away, robot.visitors = Tracker(), {}, set(), {}
    robot.view, robot.views = (None, {}), deque(maxlen=SHOTS)
    robot.view_at, robot.mine = 0.0, {}
    robot.detecting, robot.detect_failed, robot.history = threading.Lock(), None, []
    robot.vocab = {"phone", "cup", "mug", "chair", "person"}
    robot.faces, robot.hiding, robot.jobs, robot.uncaptioned = None, None, queue.Queue(), []
    robot.told, robot.focus, robot.last_line = None, None, 0.0
    return robot


def store(robot: Robot, turn: Turn) -> int:
    """Robot._store after the turn is spoken (no face in the frame); the points it added."""
    before = robot.memory.shard.count(CountRequest())
    robot._store(turn, (np.zeros((9, 9, 3), np.uint8), time.time(), {}), None, None)
    return robot.memory.shard.count(CountRequest()) - before


def statements(robot: Robot) -> list[str]:
    return [r.payload.get("said", "") for r in robot.memory.shard.scroll(
        ScrollRequest(limit=999, with_payload=True))[0]]


def show(robot: Robot, objects: list[tuple[int, tuple]], frames: int = CONFIRM) -> None:
    """The detection loop on a frame with `objects` (pixel value, box) as phones."""
    frame = np.zeros((720, 1280, 3), np.uint8)
    for value, (x1, y1, x2, y2) in objects:
        frame[y1:y2, x1:x2] = value
    dets = [Detection("phone", 0.9, box) for _, box in objects]
    for _ in range(frames):
        if found := robot._track(frame, dets):
            robot._sight(found, frame)


def ask(robot: Robot, text: str) -> tuple[str | None, Turn]:
    turn = Turn(question=text, speech_start=time.time() + 1)
    return robot._things(turn), turn


def test_things(monkeypatch) -> None:
    monkeypatch.setattr(main, "SETTLE_S", 0)  # the test's speech starts after its frames
    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        show(robot, [(GOLD, CENTER)])
        said, turn = ask(robot, "This is my phone.")
        assert said == "Got it, that is your phone. I will remember it." and turn.named == "phone"
        assert store(robot, turn) == 1
        naming = turn.frame_id
        assert ask(robot, "Is this my phone?")[0] == "Yes, this is your phone."
        show(robot, [], LOST + 1)  # taken away
        robot.memory.set(naming, caption="Main object: a gold keypad phone. Around it: a desk.")
        said, turn = ask(robot, "Have you seen my phone?")
        assert said.startswith("I last saw your phone ") and naming in turn.memories
        named = robot.things.named("phone", ["phone"])
        lines = robot.named_evidence(Turn(speech_start=time.time() + 1), named)[0]
        assert lines[0].startswith("The visitor's phone: a gold keypad phone, named ")
        assert lines[1].startswith("Matched sighting: phone, last seen "), lines
        show(robot, [(BLACK, LEFT), (GOLD, RIGHT)])
        assert ask(robot, "Where is my phone?")[0] == "Yes, your phone is here now."
        mine = [s for s in robot.memory.sightings(time.time() + 1, 9) if s.get("named")]
        assert [s["region"] for s in mine] == ["right", "center"], "a new track is matched"
        show(robot, [], LOST + 1)
        show(robot, [(BLACK, CENTER)])
        assert ask(robot, "Is this my phone?")[0] == "No, I don't think this is your phone."
        assert ask(robot, "Where is my phone?")[0] == "I see a phone, but I am not sure it " \
            "is yours.", "a same-kind phone under MATCH is never called the visitor's"
        show(robot, [], LOST + 1)
        assert ask(robot, "Where is my phone?")[0].startswith("I last saw your phone ")
        robot.memory.shard.close()
        robot.things.shard.close()

        robot = open_robot(Path(tmp))  # a restart
        show(robot, [(GOLD, LEFT)])
        assert ask(robot, "Where is my phone?")[0] == "Yes, your phone is here now."
        assert ask(robot, "Do you remember my phone?")[0].startswith("Yes, I remember your phone.")
        said, turn = ask(robot, "Forget my phone.")
        assert said == "Done. I have forgotten your phone." and store(robot, turn) == 0, \
            "the forget turn is not stored: it would be a new statement about the phone"
        assert not robot.memory.points([naming]), "the naming turn's frame and words go too"
        assert not [s for s in robot.memory.sightings(time.time() + 1, 99) if s.get("named")]
        assert ask(robot, "Is this my phone?")[0] == "I don't know which phone is yours."
        assert ask(robot, "Do you remember my phone?")[0] == "No, I don't know which phone " \
            "is yours."
        robot.memory.shard.close()
        robot.things.shard.close()

        robot = open_robot(Path(tmp))
        assert ask(robot, "Where is my phone?")[0] == "I don't know which phone is yours."
        assert not any("phone" in x for x in statements(robot)), "nothing of it after a restart"
        show(robot, [(BLACK, LEFT), (GOLD, RIGHT)])
        assert ask(robot, "This is my phone.")[0] == "I see more than one thing. Please hold " \
            "your phone up alone and say it again."
        show(robot, [], LOST + 1)
        show(robot, [(GOLD, CENTER)])
        assert ask(robot, "This is my phone.")[0].startswith("Got it")
        show(robot, [], LOST + 1)
        show(robot, [(BLACK, LEFT), (GOLD, RIGHT)])
        assert ask(robot, "Can you see my phone?")[0] == "Yes, your phone is here now."
        robot.memory.shard.close()
        robot.things.shard.close()

        robot = open_robot(Path(tmp))
        frame = np.full((720, 1280, 3), 90, np.uint8)
        dets = [Detection("bag", 0.9, CENTER), Detection("chair", 0.9, LEFT)]
        for _ in range(CONFIRM):  # a cup the detector calls a bag, by a chair
            robot._track(frame, dets)
        assert robot._shown()[0] is frame and {b[4:] for b in robot._shown()[1].boxes} == {
            ("", "other")}, "the view draws the tracked frame's objects"
        assert ask(robot, "This is my cup.")[0].startswith("I see more than one thing."), \
            "no cup track and two objects: no guess"
        robot.tracker = Tracker()
        for _ in range(CONFIRM):
            robot._track(frame, dets[:1])
        assert ask(robot, "This is my cup.")[0].startswith("Got it"), "the one object binds"
        assert robot.things.named("cup", ["cup"])["labels"] == ["bag", "cup", "mug"]
        robot.tracker, robot.mine = Tracker(), {}  # as Robot.reset: track ids start over
        frame[300:600, 540:740] = GOLD
        for _ in range(CONFIRM):  # the gold phone, now called a bag
            if found := robot._track(frame, [Detection("bag", 0.9, CENTER)]):
                robot._sight(found, frame)
        assert robot.memory.sightings(time.time() + 1, 1)[0]["named"] == "phone", \
            "matched across detector labels"
        robot.tracker, robot.mine = Tracker(), {}
        frame[:] = 0
        frame[300:600, 540:740] = BLACK
        found = [s for _ in range(CONFIRM)
                 for s in robot._track(frame, [Detection("phone", 0.9, CENTER)])]
        assert ask(robot, "This is my phone.")[0].startswith("Got it")
        assert ask(robot, "Forget my phone.")[0].startswith("Done")
        robot._sight(found, frame)  # the track's sighting, queued behind those two turns
        assert not [x for x in robot.memory.sightings(time.time() + 1, 99)
                    if x.get("named") == "phone"], "a queued sighting brings no tag back"


def test_ignore(monkeypatch) -> None:
    monkeypatch.setattr(main, "SETTLE_S", 0)
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        assert ask(robot, "Ignore the chair.")[0] == "Okay, I will ignore chairs."
        robot.memory.shard.close()
        robot.things.shard.close()
        robot = open_robot(Path(tmp))  # the rule survives a restart
        frame = np.zeros((720, 1280, 3), np.uint8)
        chair = [Detection("chair", 0.9, LEFT)]
        found = [s for _ in range(CONFIRM) for s in robot._track(frame, chair)]
        robot._sight(found, frame)
        assert found and robot.memory.sightings(time.time() + 1, 9) == [], \
            "an ignored kind is not stored"
        assert ask(robot, "Are you still ignoring chairs?")[0] == "Yes, I am ignoring chairs."
        v = np.eye(TEXT_DIM, dtype=np.float32)[0]
        robot.memory.add(frame, "My chair at home is red.", v, ts=time.time())
        assert robot._told(v, time.time() + 1) == [], "a statement about chairs is not recalled"
        turn = Turn(question="Did you notice any chairs?", speech_start=time.time() + 1)
        assert robot._sighted(turn) == "I am ignoring chairs, so I do not remember any."
        assert ask(robot, "You can stop ignoring chairs now.")[0] == \
            "Okay, I will notice chairs again."
        assert [m["said"] for m in robot._told(v, time.time() + 1)] == ["My chair at home is red."]
        robot.tracker = Tracker()  # a chair that arrives now
        robot._sight([s for _ in range(CONFIRM) for s in robot._track(frame, chair)], frame)
        assert [s["label"] for s in robot.memory.sightings(time.time() + 1, 9)] == ["chair"]
