"""Naming, recall by name, forget, and ignore through the robot's own tracking and
answers, on real Edge shards and the real tracker, with a stub crop embedder (one vector per
color), including restarts."""
import queue
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from robot import main
from robot.detect import CONFIRM, LOST, Detection, Tracker
from robot.focus import Track
from robot.main import Robot, Turn
from robot.memory import CountRequest, Memory, ScrollRequest
from robot.people import DIM as FACE_DIM, People
from robot.text_embed import DIM as TEXT_DIM
from robot.things import DIM, SHOTS, Things, command

GOLD, BLACK = 200, 30  # the pixel value of each phone: the stub tells them apart by it
LEFT, CENTER, RIGHT = (100, 300, 300, 600), (540, 300, 740, 600), (1000, 300, 1200, 600)


def stub_crops(crops: list[np.ndarray]) -> np.ndarray:
    return np.eye(DIM, dtype=np.float32)[[int(c.mean()) for c in crops]]


def open_robot(root: Path) -> Robot:
    robot = Robot.__new__(Robot)  # no models: real shards, tracker, and a stub crop embedder
    robot.memory, robot.things, robot.people = Memory(root), Things(root), People(root)
    robot.crops, robot.faces = stub_crops, None
    robot.named, robot.ignored = robot.things.labels(), robot.things.ignored()
    robot.tracker, robot.points, robot.away, robot.visitors = Tracker(), {}, set(), {}
    robot.view, robot.views = (None, {}), deque(maxlen=SHOTS)
    robot.view_at, robot.view_taken, robot.labeled = 0, 0, None
    robot.preview_cursor, robot.crop_times = 0, deque()
    robot.detecting, robot.detect_failed, robot.history = threading.Lock(), None, []
    robot.vocab = {"phone", "wallet", "cup", "mug", "chair", "person", "bag"}
    robot.hiding, robot.jobs, robot.lines = None, queue.Queue(), queue.Queue()
    robot.told, robot.focus, robot.last_line, robot.face, robot.since = None, None, 0, None, 0
    robot.panel, robot.ui_turn = None, None
    robot.ui_turns = deque(maxlen=8)
    robot.ui_thinking, robot.ui_play_until, robot.speaking = False, 0, False
    return robot


def store(robot: Robot, turn: Turn) -> int:
    """Robot._store after the turn is spoken (no face in the frame); the points it added."""
    before = robot.memory.shard.count(CountRequest())
    robot._store(turn, (np.zeros((9, 9, 3), np.uint8), time.time()), None, None)
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
            robot._sight(found)
    if robot.named:
        preview(robot)


def hold(robot: Robot, box: tuple) -> None:
    """The visitor holds up the object in `box`: the focus takes its track (Focus.freeze)."""
    robot.focus.freeze(next(t for t, (_, b) in robot.view[1].items() if b == box))


def ask(robot: Robot, text: str) -> tuple[str | None, Turn]:
    turn = Turn(question=text, speech_start=time.time() + 1)
    return robot._things(turn), turn


def test_things(monkeypatch) -> None:
    monkeypatch.setattr(main, "SETTLE_S", 0)  # the test's speech starts after its frames
    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: None)
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        show(robot, [(GOLD, CENTER)])
        assert ask(robot, "This is my phone.")[0] == "I don't see a phone held up. Hold it " \
            "up and say it again.", "an object nobody holds up is not the focus"
        hold(robot, CENTER)
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
        close_robot(robot)

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
        close_robot(robot)

        robot = open_robot(Path(tmp))
        assert ask(robot, "Where is my phone?")[0] == "I don't know which phone is yours."
        assert not any("phone" in x for x in statements(robot)), "nothing of it after a restart"
        show(robot, [(BLACK, LEFT), (GOLD, RIGHT)])
        hold(robot, RIGHT)
        assert ask(robot, "This is my phone.")[0].startswith("Got it"), "the focus, of two"
        robot.focus.thaw()
        show(robot, [], LOST + 1)
        show(robot, [(BLACK, LEFT), (GOLD, RIGHT)])
        assert ask(robot, "Can you see my phone?")[0] == "Yes, your phone is here now."
        close_robot(robot)

        robot = open_robot(Path(tmp))
        frame = np.full((720, 1280, 3), 90, np.uint8)
        dets = [Detection("bag", 0.9, CENTER), Detection("chair", 0.9, LEFT)]
        for _ in range(CONFIRM):  # a cup the detector calls a bag, by a chair
            robot._track(frame, dets)
        assert robot._shown()[0] is frame and {b[4:] for b in robot._shown()[1].boxes} == {
            ("", "other")}, "the view draws the tracked frame's objects"
        hold(robot, CENTER)
        assert ask(robot, "This is my cup.")[0].startswith("Got it"), "the focus, any label"
        robot.focus.thaw()
        assert robot.things.named("cup", ["cup"])["labels"] == ["bag", "cup", "mug"]
        robot.tracker, robot.points = Tracker(), {}  # as Robot.reset: track ids start over
        frame[300:600, 540:740] = GOLD
        for _ in range(CONFIRM):  # the gold phone, now called a bag
            if found := robot._track(frame, [Detection("bag", 0.9, CENTER)]):
                robot._sight(found)
        preview(robot)
        assert robot.memory.sightings(time.time() + 1, 1)[0]["named"] == "phone", \
            "matched across detector labels"
        robot.tracker, robot.points = Tracker(), {}
        frame[:] = 0
        frame[300:600, 540:740] = BLACK
        found = [s for _ in range(CONFIRM)
                 for s in robot._track(frame, [Detection("phone", 0.9, CENTER)])]
        hold(robot, CENTER)
        assert ask(robot, "This is my phone.")[0].startswith("Got it")
        assert ask(robot, "Forget my phone.")[0].startswith("Done")
        robot._sight(found)  # the track's sighting, queued behind those two turns
        assert not [x for x in robot.memory.sightings(time.time() + 1, 99)
                    if x.get("named") == "phone"], "a queued sighting brings no tag back"
        close_robot(robot)


def test_ignore(monkeypatch) -> None:
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: None)
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        assert ask(robot, "Ignore the chair.")[0] == "Okay, I will ignore chairs."
        close_robot(robot)
        robot = open_robot(Path(tmp))  # the rule survives a restart
        frame = np.zeros((720, 1280, 3), np.uint8)
        chair = [Detection("chair", 0.9, LEFT)]
        found = [s for _ in range(CONFIRM) for s in robot._track(frame, chair)]
        robot._sight(found)
        assert found and robot.memory.sightings(time.time() + 1, 9) == [], \
            "an ignored kind is not stored"
        assert ask(robot, "Are you still ignoring chairs?")[0] == "Yes, I am ignoring chairs."
        v = np.eye(TEXT_DIM, dtype=np.float32)[0]
        robot.memory.add(frame, "My chair at home is red.", v, ts=time.time())
        robot.last_line = time.time()  # the same conversation
        turn = Turn(speech_start=time.time() + 1)
        assert robot._told(v, turn) == [], "a statement about chairs is not recalled"
        turn = Turn(question="Did you notice any chairs?", speech_start=time.time() + 1)
        assert robot._sighted(turn) == "I am ignoring chairs, so I do not remember any."
        assert ask(robot, "You can stop ignoring chairs now.")[0] == \
            "Okay, I will notice chairs again."
        assert [m["said"] for m in robot._told(v, turn)] == ["My chair at home is red."]
        robot.since = time.time_ns() // 1000
        assert robot._told(v, turn) == [], "a first-person statement of an earlier visitor (D70)"
        robot.memory.add(frame, "The booth closes at five.", v, ts=time.time())
        assert [m["said"] for m in robot._told(v, turn)] == ["The booth closes at five."], \
            "a general statement is shared"
        robot.tracker = Tracker()  # a chair that arrives now
        robot._sight([s for _ in range(CONFIRM) for s in robot._track(frame, chair)])
        assert robot.memory.sightings(time.time() + 1, 9) == [], "unknown tracks stay in RAM"
        assert robot._sighted(Turn(question="Can you still see any chairs?",
                                   speech_start=time.time() + 1)).startswith("I see a chair")


def close_robot(r):
    for store in (r.memory, r.things, r.people):
        store.shard.close()


@pytest.fixture
def robot(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: None)
    r = open_robot(tmp_path)
    yield r
    close_robot(r)


def frame_of(r, color=GOLD, label="phone", box=CENTER, people=False):
    frame = np.zeros((720, 1280, 3), np.uint8)
    x1, y1, x2, y2 = box
    frame[y1:y2, x1:x2] = color
    dets = [Detection(label, 0.9, box)]
    if people:
        dets.append(Detection("person", 0.9, (300, 0, 1000, 720)))
    taken = time.time()
    for _ in range(CONFIRM):
        r._sight(r._track(frame, dets, taken))
    return frame


def preview(r):
    r.crop_times.clear()  # each call represents a later idle interval
    r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()])


def test_text_only_retrieval_and_person_deletion(robot, monkeypatch):
    r = robot
    v = np.eye(TEXT_DIM, dtype=np.float32)[0]
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [face, face], time.time())
    monkeypatch.setattr(r, "_whois", lambda frame: (face, "Ana"))
    turn = Turn(question="The booth closes at five.")
    r._store(turn, (frame_of(r), time.time()), v, None)
    rows = r.memory.told(v, time.time() + 1)
    assert rows[0]["id"] == turn.frame_id and rows[0]["said"] == turn.question
    assert not {"frame", "thumb", "caption"} & rows[0].keys()
    assert not list(r.memory.frames.iterdir()) and r.jobs.empty()
    assert r._forget(None, "Ana", face)
    assert not r.memory.points([turn.frame_id]) and not r.memory.told(v, time.time() + 1)


def test_unknown_current_answers_use_ram(robot):
    r = robot
    frame_of(r)
    assert r.memory.shard.count(CountRequest()) == 0
    turn = Turn(question="Can you still see any phones?", speech_start=time.time() + 1)
    assert r._sighted(turn) == "I see a phone in the center now."
    assert turn.memories == [] and r.points == {}


def test_binding_saves_source_crop_and_forget_clears_pending(robot):
    r = robot
    frame = frame_of(r)
    r.focus.freeze(next(iter(r.view[1])))
    assert command("Track this as my wallet", r.vocab)[0:2] == ("name", "wallet")
    answer, turn = ask(r, "Track this as my wallet")
    assert answer.startswith("Got it")
    [point] = r.memory.points(turn.memories)
    saved = cv2.imread(str(r.memory.frames / point["frame"]))
    assert saved.shape == (300, 200, 3) and abs(saved.mean() - GOLD) < 1
    assert point["ts"] == pytest.approx(r.view_taken, rel=0, abs=1e-6)
    assert point["box"] == list(CENTER)
    assert point["named"] == "wallet" and r.labeled[1] is frame
    assert r.labeled[2].boxes[0][4:] == ("wallet", "known")
    assert r.jobs.queue[0][0] == "caption"
    assert ask(r, "Forget my wallet")[0].startswith("Done")
    assert not list(r.memory.frames.iterdir()) and r.labeled is None and not r.focus.names()
    assert r.memory.shard.count(CountRequest()) == 0
    r.brain = SimpleNamespace(caption=lambda *args: pytest.fail("deleted crop was captioned"))
    r.jobs.put(None)
    r._work()  # queued caption sees its deleted point and does nothing
    preview(r)  # an already queued preview cannot resurrect the forgotten evidence
    assert r.memory.shard.count(CountRequest()) == 0
    assert all(b[5] != "known" for b in r._shown()[1].boxes)


def test_fresh_recognition_sightings_and_miss(robot):
    r = robot
    r.things.name("wallet", ["phone"], stub_crops([np.full((10, 10, 3), GOLD)]))
    r.named = r.things.labels()
    frame_of(r)
    calls = []
    r.crops = lambda crops: calls.append(1) or stub_crops(crops)
    for _ in range(3):
        r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()])
    assert r._shown()[1].boxes[0][4:] == ("wallet", "known")
    r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()])
    assert len(calls) == 3, "idle crop queries are bounded to three per second"
    assert all(b[5] != "known" for b in r._shown()[1].boxes), "no new query: anonymous source"
    [seen] = r.memory.sightings(time.time() + 1)
    assert seen["named"] == "wallet"
    frame_of(r, BLACK)
    preview(r)
    assert all(b[5] != "known" for b in r._shown()[1].boxes)
    assert r.memory.sightings(time.time() + 1)[0]["last_seen"] == seen["last_seen"]
    assert not list(r.memory.frames.iterdir()), "idle recognition saves sightings, not images"


def test_legacy_named_recall_filters_before_limit(robot):
    r = robot
    image = np.full((30, 30, 3), GOLD, np.uint8)
    legacy = r.memory.add(image, "This is my wallet", ts=10)
    r.memory.set(legacy, caption="Main object: a gold wallet.")
    r.things.name("wallet", ["phone"], stub_crops([image]))
    r.things.link("wallet", legacy)
    for ts in range(11, 16):
        pid = r.memory.add(image, "ambient", ts=ts)
        r.memory.set(pid, caption="Main object: a chair.")
        r.memory.sighting("chair", "left", ts)
    selected = r.things.visual_links()
    assert [m["id"] for m in r.memory.recent(20, 1, selected)] == [legacy]
    recalled, _ = r._recall(Turn(speech_start=20), np.zeros((720, 1280, 3), np.uint8))
    assert [m["id"] for m in recalled] == [legacy]
    assert r.memory.recent(20, 1, {}) == []
    assert r.memory.sightings(20, named={}) == []
    r.things.ignore(["phone"], True)
    r.ignored = r.things.ignored()
    assert r.memory.recent(20, 1, r.things.visual_links(r.ignored), r.ignored) == []
    assert r._recall(Turn(speech_start=20), image) == ([], [])
    assert len(list(r.memory.frames.iterdir())) == 6, "old ambient evidence remains intact"


def test_ignore_and_unignore_survive_restart_and_object_forget(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: None)
    r = open_robot(tmp_path)
    frame_of(r)
    r.focus.freeze(next(iter(r.view[1])))
    assert ask(r, "This is my phone")[0].startswith("Got it")
    count = r.memory.shard.count(CountRequest())
    assert ask(r, "Ignore phones")[0].startswith("Okay")
    frame_of(r, label="bag")  # relabeling cannot bypass the stored object's ignored kind
    preview(r)
    assert r.memory.shard.count(CountRequest()) == count
    assert ask(r, "This is my phone")[0].startswith("I am ignoring")
    assert ask(r, "Where is my phone?")[0].startswith("I am ignoring")
    assert ask(r, "Forget my phone")[0].startswith("Done")
    assert r.things.ignored() == {"phone"}
    close_robot(r)
    fresh = open_robot(tmp_path)
    assert fresh.ignored == {"phone"} and fresh.things.visual_links(fresh.ignored) == {}
    assert ask(fresh, "Stop ignoring phones")[0].startswith("Okay")
    close_robot(fresh)
    fresh = open_robot(tmp_path)
    assert fresh.ignored == set()
    close_robot(fresh)


def test_face_label_stays_on_exact_frame_and_expires(robot, monkeypatch):
    r = robot
    v = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [v, v], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (v, 100, (500, 100, 600, 200)))
    preview(r)
    newer = frame_of(r, BLACK, people=True)
    frame, screen = r._shown()
    assert frame is source and ("Ana", "known") in {b[4:] for b in screen.boxes}
    r.ui_thinking = True
    assert r._shown()[0] is newer and all(b[4] != "Ana" for b in r._shown()[1].boxes)
    r.ui_thinking = False
    taken, frame, screen = r.labeled
    r.labeled = taken - main.PREVIEW_TTL - 1, frame, screen
    assert r._shown()[0] is newer and all(b[4] != "Ana" for b in r._shown()[1].boxes)
    # A replacement face on the same person track cannot inherit the old name.
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (np.eye(FACE_DIM)[1], 100,
                                                                  (500, 100, 600, 200)))
    preview(r)
    assert all(b[4] != "Ana" for b in r._shown()[1].boxes)
    # Two overlapping person boxes make the face association ambiguous.
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (v, 100, (500, 100, 600, 200)))
    tracks = [Track(*t) for t in r.tracker.scored()]
    r._preview(r.view[0], r.view_taken, tracks + [Track(999, (400, 0, 900, 720), "person", 0.9)])
    assert all(b[4] != "Ana" for b in r._shown()[1].boxes)
    assert r._forget(None, "Ana", v) and r.labeled is None
