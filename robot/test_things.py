"""Naming, recall by name, forget, and ignore through the robot's own tracking and
answers, on real Edge shards and the real tracker, with a stub crop embedder (one vector per
color), including restarts."""
import dataclasses
import json
import queue
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from robot import main
from robot.settings import DEFAULTS, Settings, settings
from robot.detect import CONFIRM, LOST, Detection, Tracker
from robot.focus import SMOOTH, Track
from robot.main import Robot, Turn
from robot.head import Head
from robot.memory import CountRequest, Memory, ScrollRequest, UpdateOperation
from robot.people import DIM as FACE_DIM, NOT_YOU, People
from robot.recognition import Recognition
from robot.text_embed import DIM as TEXT_DIM
from robot.things import DIM, SHOTS, Things, command, add_vectors, name_slot

GOLD, BLACK = 200, 30  # the pixel value of each phone: the stub tells them apart by it
LEFT, CENTER, RIGHT = (100, 300, 300, 600), (540, 300, 740, 600), (1000, 300, 1200, 600)


OWNER = "00000000-0000-4000-8000-000000000001"


def thumbnail_crops(vectors):
    return [np.full((12, 20, 3), 90, np.uint8) for _ in vectors]


def object_id(things, owner, name):
    row = things.named(owner, name, [], include_ignored=True)
    return row["id"] if row else "00000000-0000-4000-8000-000000000099"


def stub_crops(crops: list[np.ndarray]) -> np.ndarray:
    return np.eye(DIM, dtype=np.float32)[[int(c.mean()) for c in crops]]


def open_robot(root: Path) -> Robot:
    robot = Robot.__new__(Robot)  # no models: real shards, tracker, and a stub crop embedder
    robot.memory, robot.people = Memory(root), People(root)
    robot.things = Things(root, robot.people)
    robot.conversation_visitor = OWNER
    robot.conversation_started = True
    robot.head, robot.head_view, robot.last_input = Head(), 0, 0.
    robot.turn_seen, robot.face_track = None, None
    robot.current_visitor = OWNER
    robot._clear_confirmation()
    if robot.things.visitor(OWNER) is None:
        allocated = robot.things.new_visitor()
        robot.things.pending[OWNER] = robot.things.pending.pop(allocated)
    class Owner:
        faces, crops, epoch = None, staticmethod(stub_crops), 0
        condition, active, latest = threading.Condition(), None, None
        def call(self, action, mutate=False):
            self.epoch += bool(mutate)
            return action(self.faces, self.crops)
        def submit(self, frame):
            pass
    robot.recognition = Owner()
    robot.named, robot.ignored = robot.things.labels(), robot.things.ignored()
    robot.tracker, robot.points, robot.away, robot.visitors = Tracker(), {}, set(), {}
    robot.view, robot.views, robot.offers = (None, {}), deque(maxlen=SHOTS), {}
    robot.view_at, robot.view_taken, robot.verified = 0, 0, None
    robot.camera_source = "Live camera"
    robot.shown_taken, robot.session_id, robot.control_message = 0, "test-session", ""
    robot.shown_frame, robot.shown_record = 0, 0
    robot.shown_known = False
    robot.crop_due, robot.crop_times, robot.matches_pending = {}, deque(), False
    robot.item_checked = {}
    robot.detecting, robot.detect_failed, robot.history = threading.Lock(), None, []
    robot.worker_failed = None
    robot.closing = threading.Event()
    robot.looked, robot.held = [], deque(maxlen=main.HISTORY_TURNS)
    robot.delivery = threading.Condition(robot.detecting)
    robot.vocab = {"phone", "wallet", "cup", "mug", "chair", "person", "bag"}
    robot.hiding, robot.jobs, robot.lines = None, queue.Queue(), queue.Queue()
    robot.told, robot.focus, robot.last_line, robot.face = None, None, 0, None
    robot.teaching, robot.start_target, robot.window, robot.asking = None, None, None, None
    robot.out = root
    robot.wake_word = False
    robot.panel, robot.ui_turn = None, None
    robot.ui_turns = deque(maxlen=8)
    robot.ui_thinking, robot.speaking = False, False
    robot.speaker, robot.muted, robot.volume = SimpleNamespace(playing=lambda: False), False, 62
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
    if robot.named or robot.things.items:
        for _ in range(max(1, len(robot.view[1]))):
            preview(robot)


def hold(robot: Robot, box: tuple) -> None:
    """Select the confirmed fixture track before exercising real naming and action paths."""
    robot.focus.focus = next(t for t, (_, b) in robot.view[1].items() if b == box)


def ask(robot: Robot, text: str) -> tuple[str | None, Turn]:
    turn = Turn(question=text, speech_start=time.time() + 1)
    turn.visitor = robot.conversation_visitor
    teaching, robot.teaching = robot.teaching, None  # as Robot._code_answer hands it over
    return robot._things(turn, teaching), turn


def forget(robot: Robot, text: str, answer: str = "Yes.") -> tuple[str | None, Turn]:
    """A deletion command asks first; `answer` on the next line then runs or drops it."""
    said, turn = ask(robot, text)
    assert said.startswith("Should I forget your "), said
    reply = Turn(question=answer, speech_start=time.time() + 1, visitor=turn.visitor)
    return robot._deletion_answer(reply), turn


def delete_thing(robot: Robot, owner: str, name: str) -> None:
    """Ask for and confirm the deletion of `owner`'s `name`."""
    robot._forget_thing(Turn(question="", visitor=owner), owner, name, [])
    robot.deleting[2]()


def test_things(monkeypatch) -> None:
    monkeypatch.setattr(main, "SETTLE_S", 0)  # the test's speech starts after its frames
    monkeypatch.setattr(main, "located_faces", lambda faces, frame: [])
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        show(robot, [(GOLD, CENTER)])
        assert ask(robot, "This is my phone.")[0] == "I don't see a phone held up. Hold it " \
            "up and say it again.", "an object nobody holds up is not the focus"
        hold(robot, CENTER)
        said, turn = ask(robot, "This is my phone.")
        assert said == "Got it, that is your phone. Turn it slowly so I can see all sides."
        assert turn.named == object_id(robot.things, robot.conversation_visitor, 'phone')
        assert store(robot, turn) == 1
        naming = turn.frame_id
        assert ask(robot, "Is this my phone?")[0] == "Yes, this is your phone."
        show(robot, [], LOST + 1)  # taken away
        robot.memory.set(naming, caption="Main object: a gold keypad phone. Around it: a desk.")
        said, turn = ask(robot, "Have you seen my phone?")
        assert said.startswith("I last saw your phone ") and naming in turn.memories
        named = robot.things.named(robot.conversation_visitor, 'phone', ['phone'])
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
        assert ask(robot, "Where is my phone?")[0].startswith("I last saw your phone "), \
            "another phone that scores far under MATCH is neither claimed nor half-claimed"
        show(robot, [], LOST + 1)
        assert ask(robot, "Where is my phone?")[0].startswith("I last saw your phone ")
        close_robot(robot)

        robot = open_robot(Path(tmp))  # a restart
        show(robot, [(GOLD, LEFT)])
        assert ask(robot, "Where is my phone?")[0] == "Yes, your phone is here now."
        assert ask(robot, "Do you remember my phone?")[0].startswith("Yes, I remember your phone.")
        said, turn = forget(robot, "Forget my phone.")
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
        show(robot, [], LOST + 1)
        show(robot, [(BLACK, LEFT), (GOLD, RIGHT)])
        assert ask(robot, "Can you see my phone?")[0] == "Yes, your phone is here now."
        close_robot(robot)

        robot = open_robot(Path(tmp))
        frame = np.full((720, 1280, 3), 90, np.uint8)
        dets = [Detection("bag", 0.9, CENTER), Detection("chair", 0.9, LEFT)]
        for _ in range(CONFIRM):  # a cup the detector calls a bag, by a chair
            robot._track(frame, dets)
        assert robot._shown()[0] is frame and len(robot._shown()[1].boxes) == 2 and \
            all(b[5] == "other" for b in robot._shown()[1].boxes), \
            "eligible objects have neutral outlines before teaching focus settles"
        hold(robot, CENTER)
        assert ask(robot, "This is my cup.")[0].startswith("Got it"), "the focus, any label"
        assert robot.things.named(robot.conversation_visitor, "cup", ["cup"])["labels"] == [
            "bag",
            "cup",
            "mug",
        ]
        # Robot.reset also clears the old associations.
        robot.tracker, robot.points, robot.focus = Tracker(), {}, None
        frame[300:600, 540:740] = GOLD
        for _ in range(CONFIRM):  # the gold phone, now called a bag
            if found := robot._track(frame, [Detection("bag", 0.9, CENTER)]):
                robot._sight(found)
        preview(robot)
        assert robot.memory.sightings(time.time() + 1, 1)[0]["named"] == object_id(
            robot.things, robot.conversation_visitor, "phone"
        ), "matched across detector labels"
        robot.tracker, robot.points = Tracker(), {}
        frame[:] = 0
        frame[300:600, 540:740] = BLACK
        found = [s for _ in range(CONFIRM)
                 for s in robot._track(frame, [Detection("phone", 0.9, CENTER)])]
        hold(robot, CENTER)
        assert ask(robot, "This is my phone.")[0].startswith("Got it")
        assert forget(robot, "Forget my phone.")[0].startswith("Done")
        robot._sight(found)  # the track's sighting, queued behind those two turns
        assert not [
            x
            for x in robot.memory.sightings(time.time() + 1, 99)
            if x.get("named") == object_id(robot.things, robot.conversation_visitor, "phone")
        ], "a queued sighting brings no tag back"
        close_robot(robot)


def test_ignore(monkeypatch) -> None:
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "located_faces", lambda faces, frame: [])
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        robot.things.ignore(["chair"], True)  # a stored rule: the UI writes only item rules
        close_robot(robot)
        robot = open_robot(Path(tmp))  # the rule survives a restart
        frame = np.zeros((720, 1280, 3), np.uint8)
        chair = [Detection("chair", 0.9, LEFT)]
        found = [s for _ in range(CONFIRM) for s in robot._track(frame, chair)]
        robot._sight(found)
        assert found and robot.memory.sightings(time.time() + 1, 9) == [], \
            "an ignored kind is not stored"
        assert robot.ignored == {"chair"}
        v = np.eye(TEXT_DIM, dtype=np.float32)[0]
        robot.memory.add(frame, "My chair at home is red.", v, ts=time.time(),
                         visitor=robot.current_visitor)
        robot.last_line = time.time()  # the same conversation
        turn = Turn(speech_start=time.time() + 1, visitor=robot.current_visitor)
        assert robot._told(v, turn) == [], "a statement about chairs is not recalled"
        turn = Turn(question="Did you notice any chairs?", speech_start=time.time() + 1,
                    visitor=robot.current_visitor)
        assert robot._sighted(turn) == "I am ignoring chairs, so I do not remember any."
        robot.things.ignore(["chair"], False)
        robot.ignored = robot.things.ignored()
        assert [m["said"] for m in robot._told(v, turn)] == ["My chair at home is red."]
        turn.visitor = "another-visitor"
        assert robot._told(v, turn) == [], "another visitor's personal statement stays private"
        robot.memory.add(frame, "The booth closes at five.", v, ts=time.time(),
                         visitor=robot.current_visitor)
        assert robot._told(v, turn) == [], "D206 also scopes general statements to their visitor"
        turn.visitor = robot.current_visitor
        assert {m["said"] for m in robot._told(v, turn)} == {
            "My chair at home is red.", "The booth closes at five."}
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
    monkeypatch.setattr(main, "located_faces", lambda faces, frame: [])
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


def preview(r, clear=True):
    if clear:
        r.crop_times.clear()  # each call represents a later idle interval
    r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()],
               {i: r.focus.epoch(i) for i in r.focus.visible}, r.session_id,
               r.focus.geometry([Track(*t) for t in r.tracker.scored()]), r.recognition.epoch)
    drain_matches(r)


def test_text_only_retrieval_and_person_deletion(robot, monkeypatch):
    r = robot
    v = np.eye(TEXT_DIM, dtype=np.float32)[0]
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [face, face], time.time())
    r.turn_seen = face, "Ana"  # The selected speech-start identity supplies storage links.
    turn = Turn(question="The booth closes at five.", visitor=r.people.person("Ana")["visitor"])
    r._store(turn, (frame_of(r), time.time()), v, None)
    rows = r.memory.told(v, time.time() + 1, visitor=turn.visitor)
    assert rows[0]["id"] == turn.frame_id and rows[0]["said"] == turn.question
    assert not {"frame", "thumb", "caption"} & rows[0].keys()
    assert not list(r.memory.frames.iterdir()) and r.jobs.empty()
    assert r._forget(None, "Ana", face, r.people.person("Ana")["visitor"])
    assert not r.memory.points([turn.frame_id]) and not r.memory.told(
        v, time.time() + 1, visitor=turn.visitor)


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
    r.focus.focus = next(iter(r.view[1]))
    r.focus.seen[next(iter(r.view[1]))].shown = (1, 2, 3, 4)
    assert command("Track this as my wallet", r.vocab)[0:2] == ("name", "wallet")
    answer, turn = ask(r, "Track this as my wallet")
    assert answer.startswith("Got it")
    [point] = r.memory.points(turn.memories)
    saved = cv2.imread(str(r.memory.frames / point["frame"]))
    assert saved.shape == (300, 200, 3) and abs(saved.mean() - GOLD) < 1
    assert point["ts"] == pytest.approx(r.view_taken, rel=0, abs=1e-6)
    assert point["box"] == list(CENTER)
    assert (
        point["named"] == object_id(r.things, r.conversation_visitor, "wallet")
        and r._shown()[0] is frame
    )
    assert r._shown()[1].boxes[0][4:] == ("Guest 1's wallet", "known")
    assert r.focus.named[next(iter(r.view[1]))].refreshed == r.view_taken
    assert r.jobs.queue[0][0] == "caption"
    assert forget(r, "Forget my wallet")[0].startswith("Done")
    assert not list(r.memory.frames.iterdir()) and r.verified is None and not r.focus.names()
    assert r.memory.shard.count(CountRequest()) == 0
    r.brain = SimpleNamespace(caption=lambda *args: pytest.fail("deleted crop was captioned"))
    r.jobs.put(None)
    r._work()  # queued caption sees its deleted point and does nothing
    preview(r)  # an already queued preview cannot resurrect the forgotten evidence
    assert r.memory.shard.count(CountRequest()) == 0
    assert all(b[5] != "known" for b in r._shown()[1].boxes)


def test_fresh_recognition_sightings_and_miss(robot):
    r = robot
    r.things.name(
        r.conversation_visitor,
        "wallet",
        ["phone"],
        stub_crops([np.full((10, 10, 3), GOLD)]),
        thumbnail_crops(stub_crops([np.full((10, 10, 3), GOLD)])),
    )
    r.named = r.things.labels()
    frame_of(r)
    calls = []
    r.recognition.crops = lambda crops: calls.append(1) or stub_crops(crops)
    for _ in range(3):
        r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()],
               {i: r.focus.epoch(i) for i in r.focus.visible}, r.session_id,
               r.focus.geometry([Track(*t) for t in r.tracker.scored()]), r.recognition.epoch)
    drain_matches(r)
    assert r._shown()[1].boxes[0][4:] == ("Guest 1's wallet", "known")
    [seen] = r.memory.sightings(time.time() + 1)
    newest = frame_of(r)
    r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()],
               {i: r.focus.epoch(i) for i in r.focus.visible}, r.session_id,
               r.focus.geometry([Track(*t) for t in r.tracker.scored()]), r.recognition.epoch)
    drain_matches(r)
    assert r._shown()[0] is newest
    assert len(calls) == 3, "idle crop queries are bounded to three per second"
    assert r._shown()[1].boxes[0][4:] == ("Guest 1's wallet", "known"), (
        "skipped query preserves display only"
    )
    assert r.memory.sightings(time.time() + 1)[0]["last_seen"] == seen["last_seen"], \
        "cached display does not authorize a new sighting"
    assert seen["named"] == object_id(r.things, r.conversation_visitor, 'wallet')
    frame_of(r, BLACK)
    preview(r)
    assert r._shown()[1].boxes[0][4:] == ("Guest 1's wallet", "known")
    assert r.memory.sightings(time.time() + 1)[0]["last_seen"] == seen["last_seen"]
    preview(r)
    assert r._shown()[1].boxes[0][4:] == ("Guest 1's wallet", "known")
    preview(r)
    assert all(b[5] != "known" for b in r._shown()[1].boxes)
    assert r.memory.sightings(time.time() + 1)[0]["last_seen"] == seen["last_seen"]
    assert not list(r.memory.frames.iterdir()), "idle recognition saves sightings, not images"


def test_legacy_named_recall_filters_before_limit(robot):
    r = robot
    image = np.full((30, 30, 3), GOLD, np.uint8)
    legacy = r.memory.add(image, "This is my wallet", ts=10)
    r.memory.set(legacy, caption="Main object: a gold wallet.")
    r.things.name(
        r.conversation_visitor,
        "wallet",
        ["phone"],
        stub_crops([image]),
        thumbnail_crops(stub_crops([image])),
    )
    r.things.link(object_id(r.things, r.conversation_visitor, 'wallet'), legacy)
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


def test_ignore_rule_survives_restart_and_object_forget(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "located_faces", lambda faces, frame: [])
    r = open_robot(tmp_path)
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    assert ask(r, "This is my phone")[0].startswith("Got it")
    count = r.memory.shard.count(CountRequest())
    r.things.ignore(["phone"], True)
    r.ignored = r.focus.ignored = r.things.ignored()
    frame_of(r)
    assert not r.focus.names(), "a stored rule clears stored-class display"
    frame_of(r, label="bag")  # relabeling cannot bypass the stored object's ignored kind
    preview(r)
    assert r.memory.shard.count(CountRequest()) == count
    assert not r.focus.names(), "detector relabeling cannot restore an ignored name"
    assert ask(r, "This is my phone")[0].startswith("I am ignoring")
    assert ask(r, "Where is my phone?")[0].startswith("I am ignoring")
    assert forget(r, "Forget my phone")[0].startswith("Done")
    assert r.things.ignored() == {"phone"}
    close_robot(r)
    fresh = open_robot(tmp_path)
    assert fresh.ignored == {"phone"} and fresh.things.visual_links(fresh.ignored) == {}
    fresh.things.ignore(["phone"], False)
    close_robot(fresh)
    fresh = open_robot(tmp_path)
    assert fresh.things.ignored() == set()
    close_robot(fresh)


def test_verified_face_frame_and_anonymous_replacement(robot, monkeypatch):
    r = robot
    v = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [v, v], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_faces",
                        lambda faces, frame: [(v, 100, (500, 100, 600, 200))])
    preview(r)
    newer = frame_of(r, BLACK, people=True)
    frame, screen = r._shown()
    assert frame is source and (500, 100, 600, 200, "Ana", "known") in screen.boxes
    assert not any(b[5] == "person" for b in r.screen[1].boxes)
    assert any(t[2] == "person" for t in r.tracker.scored()), "person tracking stays internal"
    monkeypatch.setattr(main, "located_faces", lambda faces, frame: [(np.eye(FACE_DIM)[1], 100,
                                                                  (500, 100, 600, 200))])
    preview(r)
    assert r.verified[1] is newer and r._shown()[0] is newer
    assert r.verified[3][1][4:] == ("", "other"), "unidentified face stays anonymous"
    assert not any(b[5] == "person" for b in r._shown()[1].boxes)
    assert r._forget(None, "Ana", v, r.people.person("Ana")["visitor"]) and r.verified is None


def delivery_job(r, frame, taken):
    tracks = [Track(*t) for t in r.tracker.scored()]
    return (frame, taken, tracks, {t.id: r.focus.epoch(t.id) for t in tracks}, r.session_id,
            r.focus.geometry(tracks), r.recognition.epoch)


@pytest.mark.parametrize("late", [False, True])
def test_completed_face_wakes_delivery_before_crops_and_after_timeout(robot, monkeypatch, late):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [vector, vector], time.time())
    source = frame_of(r, people=True)
    job = delivery_job(r, source, r.view_taken)
    r.recognition.active = job
    newer = frame_of(r, BLACK, people=True)
    r.recognition.latest = delivery_job(r, newer, r.view_taken)
    entered, release, crop_entered, crop_release = (threading.Event() for _ in range(4))
    def located(*args):
        entered.set()
        assert release.wait(2)
        return [(vector, 100, (500, 100, 600, 200))]
    def crop(*args):
        crop_entered.set()
        assert crop_release.wait(2)
        return {}, {}
    monkeypatch.setattr(main, "located_faces", located)
    monkeypatch.setattr(r, "_query_objects", crop)
    worker = threading.Thread(target=lambda: r._preview(*job))
    worker.start()
    try:
        assert entered.wait(1)
        if late:
            for _ in range(2):
                frame, screen = r._shown(deadline=time.monotonic()+.005)
                assert frame is source and not any(b[5] == "known" for b in screen.boxes)
                assert screen.valid(), "anonymous active pixels cannot advance to newer raw pixels"
            release.set()
        else:
            threading.Timer(.005, release.set).start()
        frame, screen = r._shown(deadline=time.monotonic()+.1)
        assert crop_entered.wait(1)
        assert frame is source and (500, 100, 600, 200, "Ana", "known") in screen.boxes
        assert screen.valid(), "identical anonymous pixels may gain their completed identity"
        assert not r.jobs.queue, "face publication does not wait for crop work"
        shown = r.shown_taken
        r._shown(False)
        assert r.shown_taken == shown, "state polling does not consume display sequence"
    finally:
        release.set()
        crop_release.set()
        worker.join(2)
    assert not worker.is_alive()


@pytest.mark.parametrize("invalid", ["expired", "gallery"])
def test_stale_active_uses_fresh_latest_without_overtaking(robot, invalid):
    r = robot
    source = frame_of(r, people=True)
    active = delivery_job(r, source, r.view_taken)
    r.recognition.active = (active[0], active[1] - 1, *active[2:]) if invalid == "expired" else \
        (*active[:6], active[6] - 1)
    pending = frame_of(r, BLACK, people=True)
    r.recognition.latest = delivery_job(r, pending, r.view_taken)
    newest = frame_of(r, 90, people=True)
    frame, screen = r._shown()
    assert frame is pending and frame is not newest
    assert screen.valid() and r.shown_taken == r.recognition.latest[1]


@pytest.mark.parametrize("fps", [10, 15])
def test_nonwaiting_completed_source_phase_and_encoding_margin(robot, monkeypatch, fps):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [vector, vector], time.time())
    origin = time.time()
    clock = [origin+.035]
    monkeypatch.setattr(main.time, "time", lambda: clock[0])
    monkeypatch.setattr(main, "located_faces", lambda *a: [(vector, 100, (500, 100, 600, 200))])
    first = frame_of(r, people=True)
    clock[0] = origin+.075
    preview(r)
    first_poll = .1 if fps == 10 else 2/15
    clock[0] = origin+first_poll
    frame, screen = r._shown()
    assert frame is first and any(b[4] == "Ana" for b in screen.boxes)
    clock[0] += .005
    assert screen.valid()
    first_emit = clock[0]
    clock[0] = origin+.168
    second = frame_of(r, BLACK, people=True)
    r.recognition.active = delivery_job(r, second, r.view_taken)
    clock[0] = origin+.2
    frame, screen = r._shown()
    assert frame is first and any(b[4] == "Ana" for b in screen.boxes)
    clock[0] = origin+.208
    preview(r)
    clock[0] = origin+(.3 if fps == 10 else 4/15)
    frame, screen = r._shown()
    assert frame is second and any(b[4] == "Ana" for b in screen.boxes)
    clock[0] += .007
    assert screen.valid()
    hold = clock[0]-first_emit
    assert hold == pytest.approx(.202 if fps == 10 else 2/15+.002, abs=1e-6)


@pytest.mark.parametrize("invalid", ["negative", "gallery", "session", "gap", "expired"])
def test_final_jpeg_validation_rejects_changed_face_authority(robot, monkeypatch, invalid):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [vector, vector], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_faces", lambda *a: [(vector, 100, (500, 100, 600, 200))])
    preview(r)
    frame, screen = r._shown()
    assert frame is source and any(b[4] == "Ana" for b in screen.boxes)
    if invalid == "negative":
        frame_of(r, BLACK, people=True)
        monkeypatch.setattr(main, "located_faces", lambda *a: [])
        preview(r)
    elif invalid == "gallery":
        r.recognition.epoch += 1
    elif invalid == "session":
        r.session_id = "replacement"
    elif invalid == "gap":
        frame_of(r, people=False)
    else:
        monkeypatch.setattr(main.time, "time", lambda: r.view_taken + .201)
    assert not screen.valid() and r.shown_taken == 0, "invalid encoding never consumes a source"


@pytest.mark.parametrize("detected", [False, True])
def test_unidentified_weak_person_gap_cannot_publish_face(robot, monkeypatch, detected):
    r = robot
    source = frame_of(r, people=True)
    tracks = [Track(*t) for t in r.tracker.scored()]
    weak = [Track(t.id, t.box, t.label, .21 if t.label == "person" else t.score) for t in tracks]
    job = delivery_job(r, source, r.view_taken)
    monkeypatch.setattr(main, "located_faces", lambda *a: [(np.eye(FACE_DIM)[0], 100,
                       (500, 100, 600, 200))] if detected else [])
    frame_of(r, people=False)
    r._preview(source, job[1], weak, *job[3:])
    assert r.verified is None


def test_fresh_two_person_ambiguity_replaces_known_completion(robot, monkeypatch):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [vector, vector], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_faces", lambda *a: [(vector, 100, (500, 100, 600, 200))])
    preview(r)
    assert r.verified[3][1][4] == "Ana"
    dets = [Detection("person", .9, (200, 50, 610, 700)),
            Detection("person", .9, (490, 50, 900, 700))]
    for _ in range(CONFIRM):
        r._track(source.copy(), dets)
    assert sum(t[2] == "person" for t in r.tracker.scored()) == 2
    preview(r)
    assert r.verified[1] is r.view[0] and r.verified[3][1][4:] == ("", "other")
    assert len(r.verified[4]) == 2
    _, screen = r._shown()
    assert screen.valid() and not any(b[5] == "known" for b in screen.boxes)


def test_no_face_completion_loses_departed_person_authority_but_background_delivers(robot):
    r = robot
    source = frame_of(r, people=True)
    preview(r)
    assert r.verified[1] is source and r.verified[3][1] is None and r.verified[4]
    _, screen = r._shown()
    background = frame_of(r, people=False)
    assert r.verified is None and not screen.valid()
    preview(r)
    frame, screen = r._shown()
    assert frame is background and not r.verified[4] and screen.valid()


@pytest.mark.parametrize("invalid", ["gap", "different_pixels"])
def test_final_publication_preserves_track_and_equal_source_authority(robot, invalid):
    r = robot
    source = frame_of(r)
    frame, screen = r._shown()
    if invalid == "gap":
        frame_of(r, box=LEFT)
    else:
        assert screen.valid()
        r.screen = (source.copy(), r.screen[1])
        frame, screen = r._shown()
    assert not screen.valid()


def test_same_source_known_identity_cannot_change_after_publication(robot, monkeypatch):
    r = robot
    vectors = np.eye(FACE_DIM, dtype=np.float32)
    for index, name in enumerate(("Ana", "Bob")):
        r.people.enroll(name, [vectors[index], vectors[index]], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_faces", lambda *a: [(vectors[0], 100, (500, 100, 600, 200))])
    preview(r)
    _, screen = r._shown()
    assert screen.valid() and r.shown_known
    monkeypatch.setattr(main, "located_faces", lambda *a: [(vectors[1], 100, (500, 100, 600, 200))])
    preview(r)
    frame, screen = r._shown()
    assert frame is source and any(b[4] == "Bob" for b in screen.boxes)
    assert not screen.valid(), "only anonymous identical pixels may receive an equal-source upgrade"


def test_verified_and_current_frames_publish_the_same_unknown_focus(robot, monkeypatch):
    r = robot
    v = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [v, v], time.time())
    show(r, [(GOLD, LEFT), (BLACK, CENTER), (90, RIGHT)])
    hold(r, LEFT)
    r.things.name(
        r.conversation_visitor,
        "Chosen",
        ["phone"],
        stub_crops([np.full((4, 4, 3), GOLD)]),
        thumbnail_crops(stub_crops([np.full((4, 4, 3), GOLD)])),
    )
    r.named = r.things.labels()
    taken = r.view_taken + 1.2
    monkeypatch.setattr(main.time, "time", lambda: taken)
    frame = r.view[0]
    dets = [Detection("phone", .9, b) for b in (LEFT, CENTER, RIGHT)]
    dets.append(Detection("person", .9, (300, 0, 1000, 720)))
    for _ in range(CONFIRM):
        r._track(frame, dets, taken)
    monkeypatch.setattr(main, "located_faces",
                        lambda faces, frame: [(v, 100, (500, 100, 600, 200))])
    for _ in range(2):
        r.crop_due.clear()
        preview(r)
    chosen = next(i for i, (_, b) in r.view[1].items() if b == LEFT)
    teaching = next(i for i, (_, b) in r.view[1].items() if b == CENTER)
    assert (
        r.focus.names() == {chosen: (object_id(r.things, r.conversation_visitor, "Chosen"), True)}
        and r.focus.focus == teaching
    )
    verified = r.verified
    assert verified is not None
    for source in [None, verified] * 4:
        r.verified = source
        _, screen = r._shown()
        assert r.focus.focus == teaching, "presentation does not change the selected focus"
        assert [b[:4] for b in screen.boxes if b[5] == "focus"] == [CENTER]
        assert any(b[4] == "Guest 1's Chosen" for b in screen.boxes)
        assert next(t for t in screen.control["targets"] if t["track"] == teaching)["title"] \
            == "Unknown phone"
        assert not any(b[5] == "person" for b in screen.boxes)
    # Newer movement cannot move an object overlay on the older verified image.
    moved = (580, 300, 780, 600)
    monkeypatch.setattr(main.time, "time", lambda: taken + .05)
    dets[1] = Detection("phone", .9, moved)
    r._track(frame.copy(), dets, taken + .05)
    shown, screen = r._shown(False)
    assert shown is frame and [b[:4] for b in screen.boxes if b[5] == "focus"] == [CENTER]
    # A short gap preserves the chosen association, but invalidates its older source geometry.
    r._track(frame.copy(), dets[1:], taken + .08)
    r._track(frame.copy(), dets, taken + .10)
    assert r.focus.name(chosen) == object_id(r.things, r.conversation_visitor, 'Chosen')
    assert not any(b[4] == "Guest 1's Chosen" for b in r._shown(False)[1].boxes)


def test_spoken_names_categories_case_and_restart(tmp_path):
    vocab = {"phone", "cup", "mug", "face", "person", "name"}
    assert command("Track this as my Dylan's smartphone", vocab) == (
        "name", "Dylan's smartphone", ["phone"])
    assert command("This is Dylan's smartphone", vocab) == (
        "name", "Dylan's smartphone", ["phone"])
    assert command("This is my red coffee mug", vocab) == (
        "name", "red coffee mug", ["cup", "mug"])
    assert command("This is Ana", vocab) is None
    assert command("This is my face", vocab) is None
    assert command("This is my name", vocab) is None
    assert command("Dylan's smartphone is charging", vocab) is None
    assert command("Ignore smartphones", vocab) is None, "ignore is a UI action, not a command"
    assert command("Forget my Dylan's smartphone", vocab)[:2] == ("forget", "Dylan's smartphone")
    assert command("Delete my red coffee mug from your memory", vocab)[:2] == (
        "forget", "red coffee mug")
    for said in ["Ignore that", "ignore this.", "Ignore that thing",
                 "Edgy, please ignore that object", "Don't track that", "Do not track this item",
                 "Stop tracking that", "Ignore it", "Ignore this one.", "ignore that one",
                 "Ignore this, please"]:
        assert command(said, vocab) == ("ignore", "", []), said
    for said in ["Ignore that, what do you see?", "Just ignore that question",
                 "Ignore smartphones", "Why do you ignore that?", "Do not track my phone",
                 "Can you ignore that?", "Ignore that phone", "Ignore it, what is it?"]:
        assert command(said, vocab) is None, said
    for said in [
                 "Do not forget my phone",
                 "Don't delete my cup",
                 "Should I forget my phone?",
                 "Why did you forget my phone?",
                 "Did you forget Dylan's smartphone?",
                 "Please tell me why you forget my phone",
                 "Can you not forget my phone",
                 "Please do not ever forget my phone",
                 "I do not want you to forget my phone",
                 "Can you tell me why you forget my phone",
                 "I said forget my phone",
                 "You forget my phone",
                 "Tell me how to delete my cup",
                 "When will you erase my cup?",
                 "How do I make you remove my phone",
                 "Never delete my cup",
                 "Do you forget my phone?",
    ]:
        assert command(said, vocab) is None, said
    for said in [
                 "Forget my phone",
                 "forget my phone.",
                 "Please delete my cup",
                 "Okay, erase my cup",
                 "Can you forget my phone?",
                 "could you please delete my cup",
                 "Would you remove my phone",
                 "I want you to forget my phone",
                 "I'd like you to please erase my cup",
                 "um so please forget my phone",
                 "Forget about my cup",
                 "Now remove Dylan's smartphone",
    ]:
        assert command(said, vocab)[0] == "forget", said
    from robot.things import Things, question
    assert question("Where is my Dylan's smartphone?", vocab)[:2] == ("where", "Dylan's smartphone")
    assert question("Where is Dylan's smartphone?", vocab)[:2] == ("where", "Dylan's smartphone")
    assert question("What's my cat's name?", vocab) is None
    things = Things(tmp_path)
    vectors = stub_crops([np.full((10, 10, 3), GOLD)])
    things.name(OWNER, "Dylan's smartphone", ['phone'], vectors, thumbnail_crops(vectors))
    things.link(object_id(things, OWNER, "DYLAN'S SMARTPHONE"), 17)
    things.name(OWNER, 'red coffee mug', ['cup', 'mug'], vectors, thumbnail_crops(vectors))
    things.name(OWNER, "Ana's smartphone", ['phone'], vectors, thumbnail_crops(vectors))
    asked = question("Where is Dylan's smartphone?", vocab)
    assert things.named(OWNER, asked[1], asked[2])["name"] == "Dylan's smartphone"
    assert things.named(OWNER, "phone", ["phone"])["name"] in {
        "Dylan's smartphone", "Ana's smartphone"}
    assert things.named(OWNER, 'RED COFFEE MUG', [])["name"] == "red coffee mug"
    assert (
        things.score(vectors[0], object_id(things, OWNER, "DYLAN'S SMARTPHONE"))[0]
        == object_id(things, OWNER, "Dylan's smartphone")
    )
    things.shard.close()
    things = Things(tmp_path)
    assert things.named(OWNER, "dylan's smartphone", [])["turns"] == [17]
    things.name(OWNER, "Dylan's Smartphone", ['phone'], vectors, thumbnail_crops(vectors))
    assert things.named(OWNER, "DYLAN'S SMARTPHONE", [])["name"] == "Dylan's smartphone"
    assert things.forget(object_id(things, OWNER, "dylan's smartphone")) == [17]
    assert things.named(OWNER, "dylan's smartphone", []) is None
    assert things.named(OWNER, 'phone', ['phone'])["name"] == "Ana's smartphone"
    assert things.named(OWNER, 'red coffee mug', [])["name"] == "red coffee mug"
    things.shard.close()


def test_case_only_reteach_and_forget_all_evidence(robot):
    r = robot
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    assert ask(r, "This is my Dylan's smartphone")[0].startswith("Got it")
    answer, turn = ask(r, "Track this as my DYLAN'S SMARTPHONE")
    assert "Dylan's smartphone" in answer and turn.named == object_id(
        r.things, r.conversation_visitor, "Dylan's smartphone"
    )
    assert r.focus.names() == {
        next(iter(r.view[1])): (
            object_id(r.things, r.conversation_visitor, "Dylan's smartphone"),
            True,
        )
    }
    assert r.memory.points(turn.memories)[0]["named"] == object_id(
        r.things, r.conversation_visitor, "Dylan's smartphone"
    )
    assert forget(r, "Forget my DYLAN'S SMARTPHONE")[0].startswith("Done")
    assert r.memory.shard.count(CountRequest()) == 0
    assert not r.focus.names() and not list(r.memory.frames.iterdir())


def test_distinct_reteaching_exact_name_replacement_links_and_ignore(tmp_path):
    basis = np.eye(DIM, dtype=np.float32)
    original = basis[:3]
    current = np.asarray([.9 * basis[0] + np.sqrt(1 - .9**2) * basis[3], basis[4], basis[5]],
                         dtype=np.float32)
    things = Things(tmp_path)
    things.name(OWNER, 'Chosen', ['phone'], original, thumbnail_crops(original))
    things.link(object_id(things, OWNER, 'chosen'), 17)
    things.name(OWNER, 'CHOSEN', ['wallet'], current, thumbnail_crops(current))
    things.link(object_id(things, OWNER, 'chosen'), 19)
    saved = things.descriptors(object_id(things, OWNER, 'Chosen'))
    assert len(saved) == 6
    np.testing.assert_array_equal(saved, np.concatenate([original, current]))
    payload = things.named(OWNER, "chosen", [])
    assert payload["name"] == "Chosen" and payload["labels"] == ["phone", "wallet"]
    assert payload["turns"] == [17, 19] and len(payload["views"]) == 6
    np.testing.assert_array_equal(add_vectors(basis[:1], basis[:8]), basis[:8])
    next_views = basis[[0, 6, 7]]
    expected = add_vectors(saved, next_views)
    things.name(OWNER, 'chosen', ['phone'], next_views, thumbnail_crops(next_views))
    np.testing.assert_array_equal(things.descriptors(object_id(things, OWNER, 'Chosen')), expected)
    assert len(expected) == 8
    things.name(
        OWNER, "Separate", ["phone"], basis[[12, 12, 12]], thumbnail_crops(basis[[12, 12, 12]])
    )
    assert len(things.descriptors(object_id(things, OWNER, 'Separate'))) == 1
    np.testing.assert_array_equal(things.descriptors(object_id(things, OWNER, 'Chosen')), expected)
    things.shard.close()
    things = Things(tmp_path)
    np.testing.assert_array_equal(things.descriptors(object_id(things, OWNER, 'chosen')), expected)
    ident = things.ignore_item("Chosen", expected)
    assert all(things.excluded(vector) == ident for vector in expected)
    assert things.excluded(basis[30]) is None and things.score(basis[12])[0] == object_id(
        things, OWNER, "Separate"
    )
    things.shard.close()
    things = Things(tmp_path)
    assert all(things.excluded(vector) == ident for vector in expected)
    assert things.restore_item(ident) and all(things.excluded(v) is None for v in expected)
    # Same-owner reteaching appends even when the new crop does not match.
    replacement = basis[[30, 0, 31]]
    things.name(OWNER, 'CHOSEN', ['bag'], replacement, thumbnail_crops(replacement))
    np.testing.assert_array_equal(things.descriptors(object_id(things, OWNER, 'Chosen')),
                                  add_vectors(expected, replacement))
    assert things.score(basis[0], object_id(things, OWNER, 'Chosen'))[1] >= settings.match
    assert things.named(OWNER, 'chosen', [])["labels"] == ["bag", "phone", "wallet"]
    assert (
        things.forget(object_id(things, OWNER, "chosen")) == [17, 19]
        and things.named(OWNER, "chosen", []) is None
    )
    assert things.named(OWNER, 'Separate', []) and not things.preferences()
    things.shard.close()



def test_track_this_asks_for_the_name_in_the_next_line(robot):
    r = robot
    r.last_line = time.time()  # the conversation window runs from the last answer
    asking = "What should I call it?"
    frame_of(r)
    assert ask(r, "Track this.")[0] == "I don't see an object held up. Hold it up and say " \
        "it again." and r.teaching is None
    hold(r, CENTER)
    for line in ("as my phone.", "it's my phone", "call it phone", "my phone", "phone"):
        assert ask(r, "Remember that")[0] == asking and r.teaching is not None
        said, turn = ask(r, line)
        assert said == "Got it, that is your phone. Turn it slowly so I can see all sides."
        assert r.teaching is None
        assert turn.named == object_id(r.things, r.conversation_visitor, 'phone'), line

    assert ask(r, "Track this")[0] == asking
    assert ask(r, "Where is my phone?")[0] == "Yes, your phone is here now."
    assert ask(r, "as my wallet")[0] is None and not r.things.named(
        r.conversation_visitor, "wallet", []
    ), "a question instead drops the capture"
    assert ask(r, "Track this")[0] == asking
    assert ask(r, "This is my wallet.")[0].startswith("Got it, that is your wallet"), \
        "a different command runs as itself"
    assert ask(r, "my cup")[0] is None, "the capture is used once"

    assert ask(r, "Track this")[0] == asking
    r.last_line = time.time() - main.CONVERSATION_S - 5
    assert ask(r, "my cup")[0] is None, "expired with the follow-up window"
    r.last_line = time.time()

    assert ask(r, "Track this")[0] == asking
    r.teaching = None  # a visitor change or "forget me" clears it
    assert ask(r, "my cup")[0] is None

    frame_of(r)  # a fresh source: on a slow machine the first frame is older than PREVIEW_TTL
    hold(r, CENTER)
    assert ask(r, "Track this.")[0] == asking  # a pause splits the line
    assert ask(r, "as my phone.")[0].startswith("Got it")


def test_pinned_object_gone_or_turned_person_is_never_replaced_or_bound(robot):
    r = robot
    r.last_line = time.time()
    show(r, [(GOLD, CENTER), (BLACK, RIGHT)])
    hold(r, CENTER)
    pinned = r.focus.focus
    assert ask(r, "Track this")[0] == "What should I call it?"
    show(r, [], LOST + 1)  # the pinned object is taken away, another one stays
    show(r, [(BLACK, RIGHT)])
    hold(r, RIGHT)
    said, turn = ask(r, "my phone")
    assert said.startswith("I don't see") and not turn.named, "never the other object"
    assert r.focus.focus != pinned

    track = r.focus.focus  # a captured track whose label turns into a person
    r.teaching = track, r.focus.epoch(track)
    frame, boxes = r.view
    r.view, r.views = (frame, {track: ("person", boxes[track][1])}), deque(maxlen=SHOTS)
    said, turn = ask(r, "my phone")
    assert said.startswith("I only track objects") and not turn.named


def test_pin_that_left_and_returned_has_a_new_epoch(robot):
    r = robot
    r.last_line = time.time()
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "Track this")[0] == "What should I call it?"
    track, epoch = r.teaching
    r.focus.update(r.view_taken + .5, [], [])  # the track drops out of the frame
    frame_of(r)
    assert track in r.focus.visible and r.focus.epoch(track) != epoch, "same id, new epoch"
    said, turn = ask(r, "my phone")
    assert said.startswith("Sorry, I lost sight") and not turn.named


def test_status_says_hey_edgy_once_the_window_lapses(robot, monkeypatch):
    r = robot
    r.wake_word = True
    frame_of(r)
    monkeypatch.setattr(r.speaker, "playing", lambda: False)
    r.last_line = time.time()
    assert r._shown(False)[1].status == "Listening"
    r.last_line = time.time() - main.CONVERSATION_S - 1
    assert r._shown(False)[1].status == "Say 'Hey Edgy'"


def test_only_object_views_of_a_track_that_was_a_person_reach_the_embedder(robot):
    r = robot
    r.last_line = time.time()
    frame_of(r)
    hold(r, CENTER)
    track = r.focus.focus
    taken, frame, view = r.view_taken, *r.view
    person = {track: ("person", view[track][1])}
    r.focus.seen[track].continuous = 0  # the earlier views are of this same continuous track
    r.views.extend([(taken - .2, frame, person), (taken - .1, frame, view)])
    shots = []
    r.recognition.crops = staticmethod(lambda crops: shots.append(len(crops)) or stub_crops(crops))
    assert ask(r, "This is my phone.")[0].startswith("Got it")
    assert shots == [2], "the current view and one earlier object view; the person view is out"


def test_other_commands_drop_the_pending_name(robot):
    r = robot
    r.last_line = time.time()
    frame_of(r)
    hold(r, CENTER)
    for line in ("Forget everything.", "Remember me.", "Do you remember me?"):
        assert ask(r, "Track this")[0] == "What should I call it?"
        ask(r, line)
        assert r.teaching is None and not r.things.named(
            r.conversation_visitor, "everything", []
        ), line
        assert name_slot(line, r.vocab) is None, line


def test_ignore_offer_outlives_the_focus_moving_on(robot):
    r = robot
    show(r, [(GOLD, CENTER), (BLACK, RIGHT)])
    first, second = sorted(r.view[1])
    r.focus.focus = first
    assert [t["track"] for t in r._shown(False)[1].control["targets"]] == [first]
    r.focus.focus = second  # the focus jumps; the first item is still in view
    assert sorted(t["track"] for t in r._shown(False)[1].control["targets"]) == [first, second]


def test_spoken_ignore_that_acts_like_the_camera_card(robot, monkeypatch):
    r = robot
    frame_of(r)
    assert ask(r, "Ignore that")[0] == main.NOTHING_HELD, "nothing held up"
    hold(r, CENTER)
    assert not r.offers, "no viewer has polled the card"
    clock = time.time()
    monkeypatch.setattr(main.time, "time", lambda: clock + main.OFFER_HOLD_S + 1)
    assert ask(r, "Ignore that")[0] == "I lost it. Hold it up and say it again."
    monkeypatch.undo()
    said, turn = ask(r, "Ignore that.")
    assert said == "Okay, I will ignore that phone." and not turn.keep
    assert [p["title"] for p in r.things.preferences()] == ["Phone"] and not r.offers
    assert r.things.excluded(stub_crops([np.full((10, 10, 3), GOLD)])[0]), "the item is ignored"


def test_only_a_voice_deletion_clears_the_live_chat(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my phone.")[0].startswith("Got it")
    r.turns = queue.Queue()
    earlier = Turn(question="Hello", answer="Hi there", line=1)
    r.ui_turns.append(earlier)
    for text in ("Ignore that.", "Forget my phone."):  # a command and a question, neither deletes
        turn = ask(r, text)[1]
        r.ui_turn = turn
        r.ui_turns.append(turn)
        r._log(turn)
        assert earlier in r.ui_turns and r._shown(False)[1].transcript[0]["answer"] == "Hi there"
    r.deleting = None  # the question is left unanswered
    assert ask(r, "Forget my phone.")[0].startswith("Should I forget")
    reply = Turn(question="Yes.", speech_start=time.time() + 1, visitor=r.conversation_visitor,
                 told=["My phone is gold"], memories=[1])  # retrieved before the deletion ran
    r.ui_turn = reply
    r.ui_turns.append(reply)
    assert r._deletion_answer(reply) == "Done. I have forgotten your phone."
    r._log(reply)
    assert list(r.ui_turns) == [reply]
    shown = r._shown(False)[1]
    assert [t["id"] for t in shown.transcript] == [str(reply.line)]
    assert shown.evidence["statements"] == [] and shown.evidence["memory_ids"] == []
    assert shown.evidence["deleted"] and shown.evidence["turn_id"] == str(reply.line)


def test_live_latency_uses_current_turn_milestones(robot):
    frame_of(robot)
    robot.ui_turn = Turn(speech_end=100, first_token=100.1234, first_audio=101.2345)
    timing = robot._shown(False)[1].evidence["timing"]
    assert timing == {"first_text_ms": 123.4, "speech_ready_ms": 1234.5}
    robot.ui_turn = Turn(speech_end=200)
    assert robot._shown(False)[1].evidence["timing"] == {
        "first_text_ms": None, "speech_ready_ms": None}
    robot.ui_turn = Turn(first_token=100, first_audio=101)
    assert all(value is None for value in robot._shown(False)[1].evidence["timing"].values())


def test_transcript_keeps_supplied_sources_and_applies_deletion(robot):
    frame_of(robot)
    earlier = Turn(line=1, answer="A reply", facts=["A fact"], told=["A statement"],
                   memories=[42], ui_evidence=[{"label": "Generated caption", "text": "A cup"}])
    robot.ui_turns.append(earlier)
    robot.ui_turn = Turn(line=2, answer="Code reply", verbatim=True,
                         facts=["Other fact"], told=["Unused statement"])
    state = robot._shown(False)[1]
    assert state.transcript[0]["evidence"]["memories"] == earlier.ui_evidence
    assert state.transcript[0]["evidence"]["statements"] == earlier.told
    assert state.transcript[1]["evidence"] == state.evidence
    assert state.evidence["knowledge"] == state.evidence["statements"] == []
    earlier.deleted = True
    sources = robot._shown(False)[1].transcript[0]["evidence"]
    assert all(sources[name] == []
               for name in ("knowledge", "statements", "memory_ids", "memories"))
    robot.hiding = (None, time.time())
    state = robot._shown(False)[1]
    assert len(state.transcript) == 1 and state.evidence["deleted"]


def test_detection_metadata_uses_fresh_admitted_categories(robot):
    frame_of(robot, people=True)
    state = robot._shown(False)[1].control
    assert len(state["detections"]) == 1
    detection = state["detections"][0]
    assert detection["label"] == "phone" and detection["score"] == .9
    track = detection["track"]
    source = next(t for t in robot.tracker.tracks if t.id == track)
    source.det = Detection("cup", .73, source.det.box)
    detection = robot._shown(False)[1].control["detections"][0]
    assert detection["label"] == "cup" and detection["score"] == .73
    assert source.label == "phone", "the detector score must not use the majority category"
    source.det = Detection("phone", .9, source.det.box)
    robot.focus.checking.add(track)
    assert not robot._shown(False)[1].control["detections"]
    robot.focus.checking.clear()
    robot.focus.excluded[track] = "ignored"
    assert not robot._shown(False)[1].control["detections"]
    robot.focus.excluded.clear()
    robot.focus.ignored.add("phone")
    assert not robot._shown(False)[1].control["detections"]
    robot.focus.ignored.clear()
    robot.view_taken -= 1
    assert not robot._shown(False)[1].control["detections"]
    frame_of(robot)
    robot._track(robot.view[0], [], time.time())
    assert not robot._shown(False)[1].control["detections"], "carried boxes have no fresh detection"


def test_conversation_window_runs_from_the_end_of_the_last_answer(robot):
    robot.last_line = 1000.0
    for gap, goes_on in ((main.CONVERSATION_S, True), (main.CONVERSATION_S + 1, False)):
        robot.face = None
        assert robot._converse(Turn(speech_start=1000.0 + gap), None, None) is not goes_on


def converse_after_miss(r, *, face=1, track=7, now_track=7, gap=1.0):
    """A conversation held with face 0 on person track 7; the next line shows `face` (None:
    missed) while `now_track` is the largest person track. Returns (new, told, visitor)."""
    faces = np.eye(FACE_DIM, dtype=np.float32)
    r.conversation_started, r.face, r.face_track = True, faces[0], track
    r.told, r.last_line = ("Ana", False), 1000.0
    visitor = r.conversation_visitor
    seen = None if face is None else (faces[face], None)
    new = r._converse(Turn(speech_start=1000.0 + gap), seen, now_track)
    return new, r.told, visitor


def test_missed_face_goes_on_with_the_same_person_track(robot):
    r = robot
    new, told, visitor = converse_after_miss(r, face=None)
    assert not new and told == ("Ana", False) and r.conversation_visitor == visitor
    assert r.face is not None and r.face_track == 7, "the held face survives the miss"
    faces = np.eye(FACE_DIM, dtype=np.float32)
    assert not r._converse(Turn(speech_start=1002.0), (faces[0], None), 7), "the face links again"


def test_a_different_face_ends_the_conversation(robot):
    new, told, _ = converse_after_miss(robot, face=1)
    assert new and told is None


@pytest.mark.parametrize("now_track", [8, None])
def test_missed_face_on_another_or_no_person_track_starts_a_new_conversation(robot, now_track):
    new, told, visitor = converse_after_miss(robot, face=None, now_track=now_track)
    assert new and told is None and robot.conversation_visitor != visitor
    assert robot.face is None


def test_missed_face_after_the_window_starts_a_new_conversation(robot):
    new, told, _ = converse_after_miss(robot, face=None, gap=main.CONVERSATION_S + 1)
    assert new and told is None and robot.face is None


def test_naming_uses_the_focus_from_speech_start(robot, monkeypatch):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    track = r.focus.focus
    r.camera = SimpleNamespace(latest=lambda: (None, 0.0))
    r._heard_start()
    assert r.start_target == track, "the focus as the line begins"
    monkeypatch.setattr(r.focus, "target", lambda tracks, **kw: None)  # lost before the line
    turn = Turn(question="This is my phone.", speech_start=time.time() + 1,
                target=track, visitor=r.conversation_visitor)
    assert r._things(turn).startswith("Got it, that is your phone")
    r.focus.focus = None
    r.focus.visible = set()  # gone now: no fresh view to bind
    assert r._things(Turn(question="This is my cup.", target=track)).startswith("I don't see")


@pytest.mark.parametrize("two_lines", [False, True])
@pytest.mark.parametrize("input_kind", ["typed", "audio"])
def test_phone_then_cat_names_the_orange_focus_at_speech_start(robot, two_lines, input_kind,
                                                             monkeypatch):
    r = robot
    show(r, [(GOLD, CENTER), (BLACK, RIGHT)])
    hold(r, CENTER)
    assert ask(r, "This is my phone.")[0].startswith("Got it")
    phone_id = r.things.named(OWNER, "phone", [])["id"]
    hold(r, RIGHT)
    cat_track = r.focus.focus
    r.focus.held = [(300, 0, 1000, 720)]  # only the known phone overlaps the person
    tracks = [Track(*t) for t in r.tracker.scored()]
    assert next(box for box in r.focus.boxes(tracks, r.focus.held)
                if box[5] == "focus")[:4] == RIGHT
    r.camera = SimpleNamespace(latest=lambda: (r.view[0], r.view_taken))
    r.ready = None
    r.asked = 0
    text = "Track this" if two_lines else "This is my cat"
    if input_kind == "typed":
        monkeypatch.setattr(r, "check_health", lambda: None)
        r.ask(text)
    else:
        r.scribe = lambda speech: text
        r._heard_start()
        r._heard_line(np.zeros(160, np.float32), time.time())
        r._line(r.lines.get_nowait())
    queued = []
    while not r.jobs.empty():
        queued.append(r.jobs.get_nowait())
    turn = next(job[1] for job in queued if job[0] == "turn")
    turn.visitor = OWNER
    assert turn.teaching_target == cat_track and turn.target != cat_track
    hold(r, CENTER)  # processing must keep the selection captured when speech began
    if two_lines:
        assert r._things(turn) == "What should I call it?"
        r.last_line = time.time()
        answer, turn = ask(r, "my cat")
    else:
        answer = r._things(turn)
    assert answer.startswith("Got it, that is your cat")
    cat = r.things.named(OWNER, "cat", [])
    assert cat["id"] != phone_id
    for ident, color in ((cat["id"], BLACK), (phone_id, GOLD)):
        row = r.things.shard.retrieve([ident], False, True)[0]
        assert np.argmax(row.vector["crops"], axis=1).tolist() == [color]
    assert r.focus.name(cat_track) == cat["id"]


@pytest.mark.parametrize("blocked", [None, "duplicate", "pending", "stale", "category", "weak",
                                     "small", "ignored"])
def test_exact_name_reteach_without_held_or_unknown_focus(robot, blocked):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my Dylan's smartphone")[0].startswith("Got it")
    frame_of(r)
    r.focus.focus = None
    track = next(iter(r.view[1]))
    if blocked == "duplicate":
        show(r, [(GOLD, CENTER), (GOLD, LEFT)])
        r.focus.bind(
            next(t for t in r.focus.visible if t != track),
            object_id(r.things, r.conversation_visitor, "Dylan's smartphone"),
        )
        r.focus.focus = None
    elif blocked == "pending":
        r.focus.checking.add(track)
    elif blocked == "stale":
        r.focus.named[track].refreshed -= main.PREVIEW_TTL + 1
    elif blocked == "weak":
        tracks = [Track(*t) for t in r.tracker.scored()]
        r.focus.update(
            r.view_taken,
            tracks,
            [],
            recognized={
                track: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), 0.797)
            },
        )
        assert r.focus.names()[track][1], "display continuity is still green"
    elif blocked == "small":
        frame_of(r, box=(540, 300, 620, 600))
        r.focus.focus = None
    elif blocked == "ignored":
        r.ignored = r.focus.ignored = {"phone"}
    name = "Spare smartphone" if blocked == "category" else "DYLAN'S SMARTPHONE"
    answer, turn = ask(r, f"This is my {name}")
    if blocked:
        assert answer.startswith("I am ignoring" if blocked == "ignored" else "I don't see")
        assert not turn.named
    else:
        assert answer.startswith("Got it") and turn.named == object_id(
            r.things, r.conversation_visitor, "Dylan's smartphone"
        )
        assert len(r.things.named(r.conversation_visitor, name, [])["turns"]) == 2


def test_same_track_guess_replacement_never_writes_or_claims_after_bound(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my phone")[0].startswith("Got it")
    before = r.memory.shard.count(CountRequest())
    base = np.eye(DIM, dtype=np.float32)
    vector = .797 * base[GOLD] + np.sqrt(1 - .797**2) * base[BLACK]
    r.recognition.crops = lambda crops: np.asarray([vector for _ in crops])
    track = next(iter(r.view[1]))
    for i in range(100):
        frame_of(r, BLACK)
        preview(r)
        assert r.focus.name(track) == object_id(r.things, r.conversation_visitor, 'phone')
        if i >= 2:
            assert all(b[5] != "known" for b in r._shown()[1].boxes)
    assert r.memory.shard.count(CountRequest()) == before
    assert ask(r, "Where is my phone?")[0] == "I see a phone, but I am not sure it is yours."


@pytest.mark.parametrize("competitor", ["strong", "weak", "hidden", "ignored-kind"])
def test_weak_preference_rechecks_global_once_with_same_crop(robot, monkeypatch, competitor):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my A")[0].startswith("Got it")
    track = next(iter(r.view[1]))
    basis = np.eye(DIM, dtype=np.float32)
    vector = .797 * basis[GOLD] + np.sqrt(1 - .797**2) * basis[BLACK]
    other = vector if competitor != "weak" else basis[BLACK]
    r.things.name(
        r.conversation_visitor,
        "B",
        ["wallet" if competitor == "ignored-kind" else "phone"],
        other[None],
        thumbnail_crops(other[None]),
    )
    if competitor == "hidden":
        r.things.ignore_item("B", other[None])
    elif competitor == "ignored-kind":
        r.ignored = r.focus.ignored = {"wallet"}
    r.named = r.things.labels()
    calls, crops = [], []
    score = r.things.score
    monkeypatch.setattr(r.things, "score",
                        lambda v, name=None: calls.append(name) or score(v, name))
    r.recognition.crops = lambda images: crops.append(len(images)) or vector[None]
    frame_of(r, BLACK)
    assert next(iter(r.view[1])) == track, "the replacement retains the original IoU track"
    before = r.memory.shard.count(CountRequest())
    preview(r)
    assert calls == [object_id(r.things, r.conversation_visitor, 'A'), None] and crops == [1]
    if competitor == "strong":
        assert not r.focus.names(), "the first conflicting strong result abstains"
        assert not r._shown(False)[1].control["targets"], "no accepted named action during conflict"
    elif competitor == "hidden":
        assert track in r.focus.excluded and not r.focus.names()
    else:
        assert r.focus.names() == {
            track: (object_id(r.things, r.conversation_visitor, "A"), True)
        }, "ineligible hits keep weak continuity"
    preview(r, clear=False)
    if competitor == "strong":
        assert r.focus.names() == {
            track: (object_id(r.things, r.conversation_visitor, "B"), True)
        }, "the second agreeing query confirms B"
    preview(r, clear=False)
    assert crops == [1, 1, 1] and len(r.crop_times) == 3
    expected = {
        "strong": [
            object_id(r.things, r.conversation_visitor, "A"),
            None,
            None,
            object_id(r.things, r.conversation_visitor, "B"),
        ],
        "hidden": [object_id(r.things, r.conversation_visitor, "A"), None, None, None],
    }
    assert calls == expected.get(
        competitor, [object_id(r.things, r.conversation_visitor, "A"), None] * 3
    )
    previous_calls = list(calls)
    preview(r, clear=False)
    assert calls == previous_calls and crops == [1, 1, 1], "the crop budget bounds fallback queries"
    if competitor == "strong":
        assert r.focus.names() == {track: (object_id(r.things, r.conversation_visitor, 'B'), True)}
        assert r.memory.sightings(time.time() + 1)[0]["named"] == object_id(
            r.things, r.conversation_visitor, "B"
        )
    else:
        assert r.memory.shard.count(CountRequest()) == before, "weak/excluded evidence cannot write"
        assert all(b[5] != "known" for b in r._shown()[1].boxes)


@pytest.mark.parametrize("invalid", ["source", "gallery", "session", "gap"])
def test_global_reacquisition_rejects_invalidated_source(robot, monkeypatch, invalid):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my A")[0].startswith("Got it")
    track = next(iter(r.view[1]))
    basis = np.eye(DIM, dtype=np.float32)
    vector = .797 * basis[GOLD] + np.sqrt(1 - .797**2) * basis[BLACK]
    r.things.name(
        r.conversation_visitor, "B", ["phone"], vector[None], thumbnail_crops(vector[None])
    )
    r.named = r.things.labels()
    frame_of(r, BLACK)
    taken = r.view_taken
    r.recognition.crops = lambda images: vector[None]
    calls, score = [], r.things.score
    def changed(v, name=None):
        calls.append(name)
        result = score(v, name)
        if name is None:
            if invalid == "source":
                monkeypatch.setattr(main.time, "time", lambda: taken + main.PREVIEW_TTL + 1)
            elif invalid == "gallery":
                r.recognition.epoch += 1
            elif invalid == "session":
                r.session_id = "new-session"
            else:
                r.focus.update(taken + .01, [], [])
        return result
    monkeypatch.setattr(r.things, "score", changed)
    before = r.memory.shard.count(CountRequest())
    preview(r)
    assert calls == [object_id(r.things, r.conversation_visitor, 'A'), None]
    assert (
        r.focus.name(track) != object_id(r.things, r.conversation_visitor, "B")
        and not r.matches_pending
    )
    assert r.memory.shard.count(CountRequest()) == before
    assert all(
        row.get("named") != object_id(r.things, r.conversation_visitor, "B")
        for row in r.memory.sightings(time.time() + 1)
    )


def test_robot_reteach_appends_buffered_and_new_object_views(robot, monkeypatch):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my phone")[0].startswith("Got it")
    track, taken = next(iter(r.view[1])), r.view_taken
    # Initial buffer predates confirmation. Record a later source with real track geometry.
    monkeypatch.setattr(main.time, "time", lambda: taken + main.VIEW_S + .05)
    frame_of(r)
    assert any(track in view and np.isclose(f[300:600, 540:740].mean(), GOLD)
               for _, f, view in r.views)
    monkeypatch.setattr(main.time, "time", lambda: taken + main.VIEW_S + .15)
    frame_of(r, BLACK)
    assert next(iter(r.view[1])) == track
    embedded = []
    r.recognition.crops = lambda crops: embedded.append([float(c.mean()) for c in crops]) or \
        stub_crops(crops)
    hold(r, CENTER)
    assert ask(r, "This is my phone")[0].startswith("Got it")
    assert embedded == [[BLACK, GOLD]], "the real teaching route passes the current and old crops"
    np.testing.assert_array_equal(
        r.things.descriptors(object_id(r.things, r.conversation_visitor, "phone")),
        stub_crops([np.full((4, 4, 3), GOLD), np.full((4, 4, 3), BLACK)]),
    )
    assert (
        r.things.score(
            stub_crops([np.full((4, 4, 3), GOLD)])[0],
            object_id(r.things, r.conversation_visitor, "phone"),
        )[1]
        >= settings.match
    )
    assert len(r.things.named(r.conversation_visitor, 'phone', [])["turns"]) == 2
    assert forget(r, "Forget my phone")[0].startswith("Done")
    assert r.memory.shard.count(CountRequest()) == 0 and not list(r.memory.frames.iterdir())


def test_robot_ignore_copies_all_verified_gallery_views_and_forget_deletes_links(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my phone")[0].startswith("Got it")
    basis = np.eye(DIM, dtype=np.float32)
    for indices in ([GOLD, 11, 12], [GOLD, 13, 14], [GOLD, 15, 16]):
        r.recognition.call(
            lambda f, c, indices=indices: r.things.name(
                r.conversation_visitor,
                "phone",
                ["phone"],
                basis[indices],
                thumbnail_crops(basis[indices]),
            ),
            mutate=True,
        )
    saved = r.things.descriptors(object_id(r.things, r.conversation_visitor, 'phone'))
    assert len(saved) == 7
    preview(r)
    state = r._shown(False)[1].control
    [target] = state["targets"]
    assert r._item_control("ignore", {**state, **target}).startswith("Okay")
    assert all(r.things.excluded(v) for v in saved), "actual current-crop action copies every view"
    [preference] = r.things.preferences()
    assert r._item_control("restore", {"id": preference["id"], "session": r.session_id,
                                       "gallery": r.recognition.epoch}).startswith("I will notice")
    assert all(r.things.excluded(v) is None for v in saved)
    assert forget(r, "Forget my phone")[0].startswith("Done")
    assert r.memory.shard.count(CountRequest()) == 0 and not list(r.memory.frames.iterdir())


@pytest.mark.parametrize("change", ["gallery", "session", "gap", "source"])
def test_naming_crop_work_rejects_changed_authority(robot, monkeypatch, change):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    owner_call = r.recognition.call
    taken = r.view_taken
    def call(action, mutate=False):
        result = owner_call(action, mutate)
        if not mutate:
            if change == "gallery":
                r.recognition.epoch += 1
            elif change == "session":
                r.session_id = "replacement-session"
            elif change == "gap":
                r.focus.update(taken + .01, [], [])
            else:
                monkeypatch.setattr(main.time, "time", lambda: taken + main.PREVIEW_TTL + 1)
        return result
    r.recognition.call = call
    answer, turn = ask(r, "This is my phone")
    assert answer.startswith("Sorry, I lost sight") and not turn.named
    assert (
        r.things.named(r.conversation_visitor, "phone", []) is None
        and r.memory.shard.count(CountRequest()) == 0
    )
    assert not list(r.memory.frames.iterdir())


def test_chosen_name_reverified_after_display_expiry_and_wrong_instance(robot, monkeypatch):
    monkeypatch.setitem(settings.values, "window_s", 0)
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    ask(r, "This is my phone")
    ask(r, "Track this as my Dylan's smartphone")
    crop = r.recognition.crops([main.cut(r.view[0], r.view[1][track][1])])[0]
    assert r.things.score(crop)[0] == object_id(r.things, r.conversation_visitor, "phone"), (
        "the old identical alias wins unrestricted search"
    )
    calls = []
    score = r.things.score
    monkeypatch.setattr(r.things, "score",
                        lambda v, name=None: calls.append(name) or score(v, name))
    preview(r)
    assert r.focus.names() == {
        track: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), True)
    }
    original = time.time()
    monkeypatch.setattr(main.time, "time", lambda: original + 3)
    newest = frame_of(r)
    assert r._shown()[0] is newest and r.focus.names(), "continuous names survive skipped work"
    assert r.focus.name(track) == object_id(
        r.things, r.conversation_visitor, "Dylan's smartphone"
    ), "continuous track keeps a query preference"
    preview(r)
    assert r.focus.names() == {
        track: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), True)
    }
    assert calls == [object_id(r.things, r.conversation_visitor, "Dylan's smartphone")] * 2
    # A different instance on an uninterrupted ID must escape the preference after real misses.
    frame_of(r, BLACK)
    preview(r)
    assert r.focus.names() == {
        track: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), True)
    }
    preview(r)
    preview(r)
    assert r.focus.name(track) is None
    preview(r)
    assert calls[-7:] == [
        object_id(r.things, r.conversation_visitor, "Dylan's smartphone"),
        None,
    ] * 3 + [None]
    # A gap clears the accepted preference even when the tracker later reuses the ID.
    r.focus.bind(
        track, object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), r.view_taken
    )
    r._track(r.view[0], [], r.view_taken + .21)
    assert r.focus.name(track) is None
    frame_of(r)
    preview(r)
    assert calls[-1] is None
    r.focus.bind(
        next(iter(r.view[1])),
        object_id(r.things, r.conversation_visitor, "Dylan's smartphone"),
        r.view_taken,
    )
    forget(r, "Forget my Dylan's smartphone")
    assert not r.focus.names()
    assert all(
        n.name != object_id(r.things, r.conversation_visitor, "Dylan's smartphone")
        for n in r.focus.named.values()
    )


def test_face_gap_during_generation_rejects_old_preview(robot, monkeypatch):
    r = robot
    v = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [v, v], time.time())
    source = frame_of(r, people=True)
    source_time, epoch = r.view_taken, r.recognition.epoch
    tracks = [Track(*t) for t in r.tracker.scored()]
    epochs = {i: r.focus.epoch(i) for i in r.focus.visible}
    monkeypatch.setattr(main, "located_faces",
                        lambda faces, frame: [(v, 100, (500, 100, 600, 200))])
    preview(r)
    r.ui_thinking = True
    frame_of(r, people=False)
    frame_of(r, people=True)
    r.verified = None
    r._preview(source, source_time, tracks, epochs, r.session_id, [], epoch)
    assert r.verified is None, "in-flight source cannot publish across a detected gap"


def drain_matches(r):
    retained = []
    while not r.jobs.empty():
        job = r.jobs.get_nowait()
        if job[0] == "matches":
            _, frame, taken, tracks, hits, person, epochs, session, gallery = job
            r.matches_pending = False
            r._remember_matches(frame, taken, tracks, hits, person)
        else:
            retained.append(job)
        r.jobs.task_done()
    for job in retained:
        r.jobs.put(job)


def test_item_ignore_learning_aliases_other_instance_restart_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "located_faces", lambda f, image: [])
    r = open_robot(tmp_path)
    try:
        frame_of(r)
        track = next(iter(r.view[1]))
        r.focus.focus = track
        ask(r, "This is my phone")
        ask(r, "Track this as my Dylan's smartphone")
        data = r._shown(False)[1].control
        selected = next(t for t in data["targets"] if t["track"] == track)
        before = len(list(r.memory.frames.iterdir()))
        assert r._item_control("ignore", {**data, **selected}).startswith("Okay")
        assert len(list(r.memory.frames.iterdir())) == before, "preference stores descriptors only"
        assert r.things.hidden_ids() == {
            object_id(r.things, r.conversation_visitor, "phone"),
            object_id(r.things, r.conversation_visitor, "Dylan's smartphone"),
        }
        assert r.things.score(stub_crops([np.full((4, 4, 3), GOLD)])[0]) is None
        assert r.things.visual_links() == {} and not r._shown()[1].boxes
        # Same detector kind, a genuinely different descriptor remains eligible.
        show(r, [(GOLD, LEFT), (BLACK, RIGHT)])
        for _ in range(4):
            preview(r)
        gold = next(i for i, (_, b) in r.view[1].items() if b == LEFT)
        black = next(i for i, (_, b) in r.view[1].items() if b == RIGHT)
        assert gold in r.focus.excluded and black not in r.focus.excluded
        assert r.things.excluded(stub_crops([np.full((4, 4, 3), BLACK)])[0]) is None
        assert forget(r, "Forget my Dylan's smartphone")[0].startswith("Done")
        assert not r.things.preferences(), "deletion removes copied descriptors and title"
    finally:
        close_robot(r)
    fresh = open_robot(tmp_path)
    try:
        frame_of(fresh)
        assert not fresh.things.preferences()
        preview(fresh)
        assert not fresh.focus.excluded
        assert fresh.things.named(fresh.conversation_visitor, "phone", [])
    finally:
        close_robot(fresh)


def test_unknown_item_ignore_empty_named_gallery_and_stale_action(robot, monkeypatch):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    data = r._shown(False)[1].control
    selected = next(t for t in data["targets"] if t["track"] == track)
    data = {**data, **selected}
    offered = time.time()
    assert r._control("ignore", {**data, "session": "old"}) is False
    assert r._control("ignore", data)
    with monkeypatch.context() as late:
        late.setattr(main.time, "time", lambda: offered + main.OFFER_HOLD_S + 1)
        assert r._item_control("ignore", data).startswith("That selection expired")
    assert not r.things.preferences()
    frame_of(r)
    r.focus.focus = track
    state = r._shown(False)[1].control
    data = {**state, **state["targets"][0]}
    assert r._item_control("ignore", data).startswith("Okay")
    assert r.things.labels() == set() and r.things.preferences()
    embeddings, exclusions = [], []
    excluded = r.things.excluded
    monkeypatch.setattr(r.recognition, "crops",
                        lambda shots: embeddings.append(len(shots)) or stub_crops(shots))
    monkeypatch.setattr(r.things, "excluded", lambda v: exclusions.append(1) or excluded(v))
    frame_of(r, BLACK)
    for miss in (1, 2, 3):
        preview(r)
        assert embeddings == [1] * miss and len(exclusions) == miss
        assert (track in r.focus.excluded) is (miss < 3)
        assert bool(r.focus.boxes([Track(*t) for t in r.tracker.scored()], [])) is (miss == 3)
        if miss < 3:
            assert not r._shown()[1].boxes
    assert not r.focus.excluded, "third real miss releases a distinct same-track item"
    # Completed geometry precedes crop results. The next source can draw the released item.
    r.crop_times.extend([time.monotonic()] * 3)
    frame_of(r, BLACK)
    preview(r, clear=False)
    assert r._shown()[1].boxes and embeddings == [1] * 3 and len(exclusions) == 3


def test_offer_is_held_after_the_track_leaves_then_expires_and_restores(robot, monkeypatch):
    r = robot
    frame = frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    offered = time.time()
    assert [t["track"] for t in r._shown(False)[1].control["targets"]] == [track]
    r._track(frame, [], r.view_taken + .01)  # the object leaves the view
    assert track not in r.view[1]

    def control(ago):
        monkeypatch.setattr(main.time, "time", lambda: offered + ago)
        state = r._shown(False)[1].control
        return state, [{**state, **t} for t in state["targets"]]

    state, held = control(main.OFFER_HOLD_S - 1)
    assert [d["track"] for d in held] == [track], "still offered after it left the view"
    assert r._item_control("ignore", held[0]).startswith("Okay")
    assert [p["title"] for p in r.things.preferences()] == ["Phone"]
    assert control(0)[1] == [], "an ignored item is no longer offered"
    state = control(0)[0]
    restore = {"session": state["session"], "gallery": state["gallery"],
               "id": r.things.preferences()[0]["id"]}
    assert r._item_control("restore", restore) == "I will notice that item again."
    assert r.things.preferences() == []

    r.offers.clear()
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    state, [data] = control(0)
    r._track(frame, [], r.view_taken + .01)
    monkeypatch.setattr(main.time, "time", lambda: offered + main.OFFER_HOLD_S + 1)
    assert r._shown(False)[1].control["targets"] == [], "gone after the hold time"
    assert r._item_control("ignore", data).startswith("That selection expired")


def state_of(r):
    state = r._shown(False)[1].control
    return {**state, **(state["targets"] or [{}])[0]}


def test_offer_crop_owns_memory_and_stalled_source_expires(robot, monkeypatch):
    r = robot
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    offered = time.time()
    [target] = r._shown(False)[1].control["targets"]
    assert r.offers[target["track"]].shot.base is None, "the crop must not keep the camera frame"
    monkeypatch.setattr(main.time, "time", lambda: offered + main.OFFER_HOLD_S + 1)
    assert r._shown(False)[1].control["targets"] == [], "a stalled source stops refreshing"
    monkeypatch.setattr(main.time, "time", lambda: offered - 5)
    assert not r._valid_item({**state_of(r), "track": target["track"]}), "negative age"


def test_people_are_never_offered(robot):
    r = robot
    frame_of(r, people=True)
    person = next(i for i, (label, _) in r.view[1].items() if label == "person")
    r.focus.focus = person
    assert person not in [t["track"] for t in r._shown(False)[1].control["targets"]]


def test_replaced_offer_does_not_persist(robot, monkeypatch):
    r = robot
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    state = r._shown(False)[1].control
    data = {**state, **state["targets"][0]}
    vectors = r._ignore_vectors

    def replaced(crops, shot, chosen, gallery):
        r.offers[data["track"]] = dataclasses.replace(r.offers[data["track"]])
        return vectors(crops, shot, chosen, gallery)

    monkeypatch.setattr(r, "_ignore_vectors", replaced)
    assert r._item_control("ignore", data).startswith("That selection expired")
    assert r.things.preferences() == []


@pytest.mark.parametrize("refresh", [True, False])
def test_offer_refresh_during_embedding_decides_persistence(robot, monkeypatch, refresh):
    r = robot
    frame = frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    data = state_of(r)
    vectors = r._ignore_vectors

    def embedding(crops, shot, chosen, gallery):
        if refresh:  # a newer source arrives while the crop is embedded
            r._track(frame, [Detection("phone", 0.9, CENTER)], r.view_taken + main.OFFER_REFRESH_S)
            r._shown(False)
        return vectors(crops, shot, chosen, gallery)

    monkeypatch.setattr(r, "_ignore_vectors", embedding)
    reply = r._item_control("ignore", data)
    assert reply.startswith("That selection expired" if refresh else "Okay")
    assert bool(r.things.preferences()) is not refresh


def test_unrelated_ignore_short_dropout_preserves_chosen_name_with_full_budget(robot, monkeypatch):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    ask(r, "This is my phone")
    ask(r, "Track this as my Dylan's smartphone")
    r.things.ignore_item("Other phone", stub_crops([np.full((4, 4, 3), BLACK)]))
    preview(r)
    assert r.things.score(stub_crops([np.full((4, 4, 3), GOLD)])[0])[0] == object_id(
        r.things, r.conversation_visitor, "phone"
    )
    old_epoch, source = r.focus.epoch(track), r.view_taken
    r.crop_times.extend([time.monotonic()] * (3 - len(r.crop_times)))
    before = r.memory.sightings(time.time() + 1)
    r._track(r.view[0], [], source + .05)
    assert not r.focus.boxes([], [], source + .05), "departed pixels cannot retain an outline"
    monkeypatch.setattr(main.time, "time", lambda: source + .10)
    moved = tuple(v + (20 if i % 2 == 0 else 0) for i, v in enumerate(CENTER))
    frame_of(r, box=moved)
    assert track in r.focus.checking and r.focus.epoch(track) > old_epoch
    preview(r, clear=False)
    monkeypatch.setattr(main.time, "time", lambda: source + .15)
    frame_of(r, box=moved)
    assert r.focus.name(track) == object_id(r.things, r.conversation_visitor, "Dylan's smartphone")
    assert r.focus.seen[track].shown == moved, "a real gap starts new drawing history"
    assert not r._shown()[1].boxes, "returning Ignore checks cannot borrow old admission"
    assert not r._shown(False)[1].control["targets"], "cached display cannot authorize actions"
    assert r.memory.sightings(source + 1) == before, "no query means no new sighting writes"
    preview(r)
    assert track not in r.focus.checking
    assert r.focus.names() == {
        track: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), True)
    }


def test_named_confidence_dip_reverifies_and_admitted_unknown_stays_grey(robot, monkeypatch):
    r = robot
    show(r, [(GOLD, CENTER), (BLACK, LEFT)])
    hold(r, CENTER)
    ask(r, "This is my phone")
    ask(r, "Track this as my Dylan's smartphone")
    chosen = next(i for i, (_, b) in r.view[1].items() if b == CENTER)
    other = next(i for i in r.view[1] if i != chosen)
    calls, original = [], r.things.score
    monkeypatch.setattr(r.things, "score",
                        lambda v, name=None: calls.append(name) or original(v, name))
    moved = (560, 300, 760, 600)
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[300:600, 560:760], frame[300:600, 100:300] = GOLD, BLACK
    dets = [Detection("phone", .21, moved), Detection("phone", .21, LEFT)]
    r._track(frame, dets)
    assert r.focus.name(chosen) == object_id(r.things, r.conversation_visitor, "Dylan's smartphone")
    assert r.focus.seen[chosen].shown != moved, "the confidence dip preserves smoothing"
    assert r.focus.names() == {
        chosen: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), True)
    }
    assert not r.focus.eligible(Track(*next(t for t in r.tracker.scored() if t[0] == other)))
    assert [b[4:] for b in r._shown()[1].boxes] == [
        ("Guest 1's Dylan's smartphone", "known"),
        ("", "other"),
    ]
    r.crop_due.clear()
    preview(r)
    assert calls == [object_id(r.things, r.conversation_visitor, "Dylan's smartphone")], (
        "a low-confidence chosen track still gets a crop query"
    )
    assert r.focus.names() == {
        chosen: (object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), True)
    }
    frame[300:600, 560:760] = BLACK
    r._track(frame, dets)
    preview(r)
    assert calls[-2:] == [object_id(r.things, r.conversation_visitor, "Dylan's smartphone"), None]
    assert not r.focus.names(), "two weak current signals hide the retained association"
    assert all(b[4:] == ("", "other") for b in r._shown()[1].boxes)
    assert [t["track"] for t in r._shown(False)[1].control["targets"]] == [chosen], \
        "the held offer keeps its last eligible crop; retained labels authorize nothing new"
    preview(r)
    preview(r)
    assert r.focus.name(chosen) is None, "three fresh misses clear the low-confidence preference"


def test_named_size_dip_hides_actions_queries_and_writes_then_regrows(robot, monkeypatch):
    r = robot
    frame_of(r, label="book")
    track = next(iter(r.view[1]))
    r.focus.focus = track
    ask(r, "Track this as my chosen item")
    preview(r)
    preview(r, clear=False)
    preview(r, clear=False)  # Spend the existing crop budget before the size dip.
    source = r.view_taken
    before = r.memory.sightings(source + 1)
    points = r.memory.shard.count(CountRequest())
    calls = []
    r.recognition.crops = lambda crops: calls.append(1) or stub_crops(crops)
    monkeypatch.setattr(main.time, "time", lambda: source + .05)
    frame_of(r, label="book", box=(540, 300, 659, 600))
    assert next(iter(r.view[1])) == track
    assert r.focus.name(track) == object_id(r.things, r.conversation_visitor, 'chosen item')
    assert r._shown()[1].boxes[0][4:] == ("", "other")
    assert not r._shown(False)[1].control["targets"]
    tracks = [Track(*t) for t in r.tracker.scored()]
    assert r.focus.target(tracks) is None
    selection = {"track": track, "epoch": r.focus.epoch(track),
                 "session": r.session_id, "gallery": r.recognition.epoch,
                 "source": r.view_taken}
    assert not r._control("ignore", selection)
    preview(r, clear=False)
    assert not calls and r.memory.sightings(source + 1) == before
    assert r.memory.shard.count(CountRequest()) == points
    monkeypatch.setattr(main.time, "time", lambda: source + .1)
    frame_of(r, label="book")
    assert r.focus.names() == {
        track: (object_id(r.things, r.conversation_visitor, "chosen item"), True)
    }
    preview(r, clear=False)  # Complete regrown face/source geometry without a spare crop query.
    assert r._shown()[1].boxes[0][4:] == ("Guest 1's chosen item", "known")
    assert not calls, "regrowth restores display without a fresh query or write"
    assert r.memory.sightings(source + 1) == before


def test_detector_frames_admit_without_second_timer_and_preserve_bounded_owner(robot, monkeypatch):
    from robot.recognition import Recognition
    r = robot
    r.things.name(
        r.conversation_visitor,
        "Chosen",
        ["phone"],
        stub_crops([np.full((4, 4, 3), GOLD)]),
        thumbnail_crops(stub_crops([np.full((4, 4, 3), GOLD)])),
    )
    r.named = r.things.labels()
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    observed, crops, submitted = [], [], []
    def priority(faces, embed):
        observed.append("priority")
        entered.set()
        assert release.wait(2)
    def background(*job):
        observed.append(job[1])
        r._preview(*job)
        completed.set()
    owner = Recognition(background, faces=object(),
        crops=lambda shots: crops.append(len(shots)) or stub_crops(shots))
    r.recognition = owner
    original_submit = owner.submit
    def submit(job):
        submitted.append(job)
        return original_submit(job)
    monkeypatch.setattr(owner, "submit", submit)
    base, clock = time.time(), {"offset": 0}
    monkeypatch.setattr(main.time, "time", lambda: base + clock["offset"])
    monkeypatch.setattr(main.time, "monotonic", lambda: 1000 + clock["offset"])
    caller = threading.Thread(target=lambda: owner.call(priority))
    caller.start()
    try:
        assert entered.wait(2)
        jitter = (.003, -.002, .006, 0)
        for index in range(12):
            clock["offset"] = index / 15 + jitter[index % len(jitter)]
            frame = np.zeros((720, 1280, 3), np.uint8)
            frame[300:600, 540:740] = GOLD
            taken = base + clock["offset"]
            r._track(frame, [Detection("phone", .9, CENTER)], taken)
            assert submitted[-1][0] is frame and submitted[-1][1] == taken
            with owner.condition:
                assert owner.latest[0] is frame and owner.latest[1] == taken
                assert not owner.requests, "background frames occupy one latest slot"
        assert len({job[1] for job in submitted}) == 12, "every unique 15 Hz source is admitted"
        assert observed == ["priority"] and not crops, "priority owns the models first"
        latest = submitted[-1]
        assert latest[4] == r.session_id
        assert latest[3] == {i: r.focus.epoch(i) for i in r.focus.visible}
        release.set()
        caller.join(2)
        assert not caller.is_alive() and completed.wait(2)
        assert observed == ["priority", latest[1]], "only the newest waiting source executes"
    finally:
        release.set()
        caller.join(2)
        owner.close()
    assert r.verified[1] is latest[0] and r.verified[0] == latest[1]
    assert r.verified[2] == owner.epoch and r.verified[5] == r.session_id
    for _ in range(8):
        preview(r, clear=False)
    assert crops == [1, 1, 1], "more face admission preserves the three-per-second crop budget"


def test_recognition_runs_during_generation_oldest_due_fairness(robot, monkeypatch):
    r = robot
    r.things.name(
        r.conversation_visitor,
        "Chosen",
        ["phone"],
        stub_crops([np.full((4, 4, 3), GOLD)]),
        thumbnail_crops(stub_crops([np.full((4, 4, 3), GOLD)])),
    )
    r.named = r.things.labels()
    r.ui_thinking = True
    show(r, [(GOLD, LEFT), (BLACK, CENTER), (90, RIGHT)])
    queries = []
    original = r.recognition.crops
    r.recognition.crops = lambda crops: queries.append(round(crops[0].mean())) or original(crops)
    r.crop_due.clear()
    for _ in range(3):
        preview(r)
    assert set(queries) == {GOLD, BLACK, 90}, "oldest due visits each track during generation"
    assert any(b[4] == "Guest 1's Chosen" for b in r._shown()[1].boxes)


@pytest.mark.parametrize("named", [False, True])
def test_item_ignore_preserves_selection_interval_or_unrelated_focus(robot, monkeypatch, named):
    r = robot
    start = time.time()
    monkeypatch.setattr(main.time, "time", lambda: start)
    show(r, [(GOLD, CENTER), (BLACK, RIGHT)])
    frame = r.view[0]
    dets = [Detection("phone", .9, box) for box in (CENTER, RIGHT)]
    monkeypatch.setattr(main.time, "time", lambda: start + 1.1)
    r._track(frame, dets, start + 1.1)
    chosen = next(i for i, (_, box) in r.view[1].items() if box == CENTER)
    other = next(i for i, (_, box) in r.view[1].items() if box == RIGHT)
    assert r.focus.focus == chosen
    if named:
        r.things.name(
            r.conversation_visitor,
            "Other",
            ["phone"],
            stub_crops([np.full((4, 4, 3), BLACK)]),
            thumbnail_crops(stub_crops([np.full((4, 4, 3), BLACK)])),
        )
        r.named = r.things.labels()
        r.focus.bind(other, object_id(r.things, r.conversation_visitor, "Other"))
    state = r._shown(False)[1].control
    target = next(t for t in state["targets"] if t["track"] == (other if named else chosen))
    assert r._item_control("ignore", {**state, **target}).startswith("Okay")
    assert r.focus.focus == (chosen if named else None)
    for offset in (1.2, 2.5, 4.09):
        monkeypatch.setattr(main.time, "time", lambda offset=offset: start + offset)
        r._track(frame, dets, start + offset)
        preview(r)
        assert r.focus.focus == (chosen if named else None)
    monkeypatch.setattr(main.time, "time", lambda: start + 4.2)
    r._track(frame, dets, start + 4.2)
    preview(r)
    assert r.focus.focus == (chosen if named else other)


def test_duplicate_accepted_name_blocks_fresh_write_after_one_weak_query(robot, monkeypatch):
    r = robot
    show(r, [(GOLD, CENTER), (BLACK, RIGHT)])
    r.things.name(
        r.conversation_visitor,
        "Chosen",
        ["phone"],
        stub_crops([np.full((4, 4, 3), GOLD)]),
        thumbnail_crops(stub_crops([np.full((4, 4, 3), GOLD)])),
    )
    r.named = r.things.labels()
    tracks = list(r.focus.visible)
    for track in tracks:
        r.focus.bind(track, object_id(r.things, r.conversation_visitor, 'Chosen'))
    monkeypatch.setattr(r.things, "score", lambda v, name=None: (None, 0))
    preview(r)
    monkeypatch.setattr(r.things, "score", lambda v, name=None: ("Chosen", .99))
    preview(r)
    assert not r.focus.names()
    assert r.memory.sightings(time.time() + 1) == [], \
        "a fresh score cannot override a competing accepted claim"



def test_retained_name_cannot_ignore_saved_object_after_same_track_replacement(robot):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    answer, turn = ask(r, "This is my wallet")
    assert answer.startswith("Got it")
    saved = r.things.descriptors(object_id(r.things, r.conversation_visitor, 'wallet')).copy()
    # The new physical object retains the same track and normal detector confidence.
    frame_of(r, BLACK)
    preview(r)
    assert r.focus.named[track].score == 0
    assert r.focus.names() == {track: (object_id(r.things, r.conversation_visitor, 'wallet'), True)}
    state = r._shown(False)[1].control
    data = {**state, **next(t for t in state["targets"] if t["track"] == track)}
    assert r._valid_item(data), "the display selection alone is not a fresh identity match"
    calls = []
    r.recognition.crops = lambda shots: calls.append(shots[0].copy()) or stub_crops(shots)
    gallery = r.recognition.epoch
    assert r._item_control("ignore", data).startswith("That selection expired")
    assert len(calls) == 1 and calls[0].mean() == BLACK
    assert r.recognition.epoch == gallery and not r.things.preferences()
    assert not r.focus.excluded and not r.things.hidden_ids()
    np.testing.assert_array_equal(
        r.things.descriptors(object_id(r.things, r.conversation_visitor, "wallet")), saved
    )
    assert r.memory.points(turn.memories)[0]["named"] == object_id(
        r.things, r.conversation_visitor, "wallet"
    )
    assert forget(r, "Forget my wallet")[0].startswith("Done")
    assert not r.memory.points(turn.memories)
    assert r.things.named(r.conversation_visitor, 'wallet', []) is None


def test_unknown_ignore_embeds_only_current_crop_after_same_track_replacement(robot):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    frame_of(r, BLACK)
    assert any(image[CENTER[1]:CENTER[3], CENTER[0]:CENTER[2]].mean() == GOLD
               for _, image, _ in r.views), "old buffered source belongs to the other item"
    state = r._shown(False)[1].control
    data = {**state, **next(t for t in state["targets"] if t["track"] == track)}
    calls = []
    r.recognition.crops = lambda shots: calls.extend(shots) or stub_crops(shots)
    assert r._item_control("ignore", data).startswith("Okay")
    assert len(calls) == 1 and calls[0].mean() == BLACK
    assert r.things.excluded(stub_crops([np.full((4, 4, 3), BLACK)])[0])
    assert not r.things.excluded(stub_crops([np.full((4, 4, 3), GOLD)])[0])



def test_persisted_preference_restores_before_first_focus_frame(tmp_path):
    r = open_robot(tmp_path)
    vectors = stub_crops([np.full((4, 4, 3), GOLD)])
    ident = r.things.ignore_item("Phone", vectors)
    close_robot(r)
    r = open_robot(tmp_path)
    try:
        assert r.focus is None and len(r.things.preferences()) == 1
        state = {"session": r.session_id, "gallery": r.recognition.epoch, "id": ident}
        for stale in ({"session": "old"}, {"gallery": state["gallery"] + 1}, {"id": "missing"}):
            assert not r._control("restore", {**state, **stale})
            assert r.jobs.empty() and not r.control_message
            if "id" in stale:
                continue
            assert r._item_control("restore", {**state, **stale}).startswith("That selection")
            assert len(r.things.preferences()) == 1 and r.recognition.epoch == state["gallery"]
        r.verified = object()  # A successful Restore must clear saved display state too.
        assert r._control("restore", state), "Restore admission does not require a camera frame"
        assert r.jobs.empty() and r.control_message == "I will notice that item again."
        assert r.focus is None and not r.things.preferences() and r.verified is None
        assert r.recognition.epoch == state["gallery"] + 1
    finally:
        close_robot(r)
    reopened = Things(tmp_path)
    try:
        assert not reopened.preferences() and reopened.excluded(vectors[0]) is None
    finally:
        reopened.shard.close()


def test_restore_bypasses_blocked_full_conversation_queue_on_real_owner(robot, monkeypatch):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    state = r._shown(False)[1].control
    assert r._item_control("ignore", {**state, **state["targets"][0]}).startswith("Okay")
    track, ident = next(iter(r.focus.excluded.items()))
    r.focus.exclude(track, None)
    r.verified = object()
    started, release = threading.Event(), threading.Event()
    def blocked_look(shot):
        started.set()
        assert release.wait(2)
    monkeypatch.setattr(r, "_look", blocked_look)
    def unexpected(*args):
        pytest.fail("Restore must not embed a crop or query a vector")
    owner = r.recognition = Recognition(r._preview, faces=object(), crops=unexpected)
    monkeypatch.setattr(r.things, "excluded", unexpected)
    monkeypatch.setattr(r.things, "score", unexpected)
    worker = threading.Thread(target=r._work, daemon=True)
    r.jobs.put(("look", None))
    worker.start()
    try:
        assert started.wait(2)
        for _ in range(8):
            r.jobs.put(("look", None))
        data = {"session": r.session_id, "gallery": owner.epoch, "id": ident}
        assert r._control("restore", data)
        assert r.jobs.qsize() == 8 and not release.is_set()
        assert not r.things.preferences() and not r.focus.excluded and r.verified is None
        assert r.focus.seen[track].exclude_misses == 0
        assert r.control_message == "I will notice that item again."
        r.focus.focus = track
        state = r._shown(False)[1].control
        selected = next(t for t in state["targets"] if t["track"] == track)
        assert not r._control("ignore", {**state, **selected}), "Ignore stays queue-bounded"
        r.jobs.get_nowait()
        r.jobs.task_done()
        assert r._control("ignore", {**state, **selected})
        with r.jobs.mutex:
            assert r.jobs.queue[-1] == ("control", "ignore", {**state, **selected})
    finally:
        while not r.jobs.empty():
            r.jobs.get_nowait()
            r.jobs.task_done()
        r.jobs.put(None)
        release.set()
        worker.join(2)
        owner.close()
    assert not worker.is_alive()


@pytest.mark.parametrize("change", ["session", "gallery", "id"])
def test_direct_restore_revalidates_on_blocked_owner(robot, change):
    r = robot
    frame_of(r)
    vectors = stub_crops([np.full((4, 4, 3), GOLD)])
    ident = r.things.ignore_item("Phone", vectors)
    track = next(iter(r.view[1]))
    r.focus.exclude(track, ident)
    r.focus.exclude(track, None)
    record = r.verified = object()
    started, release = threading.Event(), threading.Event()
    owner = r.recognition = Recognition(r._preview, faces=object(), crops=stub_crops)
    def blocked(faces, crops):
        started.set()
        assert release.wait(2)
        if change == "id":
            assert r.things.restore_item(ident)
    blocker = threading.Thread(target=lambda: owner.call(blocked), daemon=True)
    blocker.start()
    result = []
    data = {"session": r.session_id, "gallery": owner.epoch, "id": ident}
    action = threading.Thread(target=lambda: result.append(r._control("restore", data)),
                              daemon=True)
    competitor = None
    try:
        assert started.wait(2)
        action.start()
        with owner.condition:
            assert owner.condition.wait_for(lambda: len(owner.requests) == 1, timeout=2)
        if change == "session":
            with r.detecting:
                r.session_id, r.control_message = "new session", "New session message"
        elif change == "gallery":
            competitor = threading.Thread(target=lambda: owner.call(lambda f, c: None,
                                                                     mutate=True), daemon=True)
            competitor.start()
            with owner.condition:
                assert owner.condition.wait_for(lambda: len(owner.requests) == 2, timeout=2)
        release.set()
        action.join(2)
        assert result == [False]
        assert r.focus.excluded[track] == ident and r.focus.seen[track].exclude_misses == 1
        assert r.verified is record
        assert bool(r.things.preferences()) == (change != "id")
        assert r.control_message == ("New session message" if change == "session" else
                                     "That selection expired.")
    finally:
        release.set()
        blocker.join(2)
        if action.ident:
            action.join(2)
        if competitor:
            competitor.join(2)
        owner.close()


@pytest.mark.parametrize("unavailable", ["closed", "full"])
def test_direct_restore_rejects_unavailable_owner(robot, unavailable):
    r = robot
    ident = r.things.ignore_item("Phone", stub_crops([np.full((4, 4, 3), GOLD)]))
    owner = r.recognition = Recognition(r._preview, faces=object(), crops=stub_crops)
    data = {"session": r.session_id, "gallery": owner.epoch, "id": ident}
    started, release = threading.Event(), threading.Event()
    def blocked(faces, crops):
        started.set()
        assert release.wait(2)
    blocker = None
    try:
        if unavailable == "closed":
            owner.close()
        else:
            blocker = threading.Thread(target=lambda: owner.call(blocked), daemon=True)
            blocker.start()
            assert started.wait(2)
            with owner.condition:
                owner.requests.extend((lambda f, c: None, Future()) for _ in range(8))
        assert not r._control("restore", data)
        assert r.things.preferences() and owner.epoch == data["gallery"]
        assert r.control_message == "That selection expired. Select it again."
        assert r.jobs.empty()
    finally:
        release.set()
        if blocker:
            blocker.join(2)
        owner.close()


def test_item_exclusion_match_skip_restore_and_explicit_ignore_reset_counter(robot):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    hold(r, CENTER)
    state = r._shown(False)[1].control
    selected = next(t for t in state['targets'] if t['track'] == track)
    assert r._item_control('ignore', {**state, **selected}).startswith('Okay')
    ident = r.focus.excluded[track]
    frame_of(r, BLACK)
    preview(r)
    preview(r)
    assert r.focus.seen[track].exclude_misses == 2
    r.crop_times.extend([time.monotonic()] * 3)
    preview(r, clear=False)
    assert r.focus.seen[track].exclude_misses == 2, 'budget skips do not consume a miss'
    frame_of(r)
    preview(r)
    assert r.focus.excluded[track] == ident and r.focus.seen[track].exclude_misses == 0
    frame_of(r, BLACK)
    preview(r)
    preview(r)
    assert r.focus.seen[track].exclude_misses == 2
    assert r._item_control('restore', {'session': r.session_id,
        'gallery': r.recognition.epoch, 'id': ident}).startswith('I will notice')
    assert not r.focus.excluded and r.focus.seen[track].exclude_misses == 0
    preview(r)
    hold(r, CENTER)
    state = r._shown(False)[1].control
    selected = next(t for t in state['targets'] if t['track'] == track)
    assert r._item_control('ignore', {**state, **selected}).startswith('Okay')
    assert r.focus.excluded[track] != ident and r.focus.seen[track].exclude_misses == 0
    preview(r)
    assert r.focus.seen[track].exclude_misses == 0, 'new explicitly ignored BLACK matches itself'


@pytest.mark.parametrize('invalid', ['age', 'session', 'gallery', 'epoch'])
def test_item_exclusion_stale_preview_does_not_consume_a_miss(robot, invalid):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    state = r._shown(False)[1].control
    assert r._item_control('ignore', {**state, **state['targets'][0]}).startswith('Okay')
    frame_of(r, BLACK)
    preview(r)
    track = next(iter(r.view[1]))
    assert r.focus.seen[track].exclude_misses == 1
    epochs = {i: r.focus.epoch(i) for i in r.focus.visible}
    source, session, gallery = r.view_taken, r.session_id, r.recognition.epoch
    if invalid == 'age':
        source = time.time() - main.PREVIEW_TTL - .1
    elif invalid == 'session':
        session = 'old session'
    elif invalid == 'gallery':
        gallery -= 1
    else:
        epochs[track] -= 1
    r.crop_times.clear()
    r._preview(r.view[0], source, [Track(*t) for t in r.tracker.scored()], epochs,
               session, r.focus.geometry([Track(*t) for t in r.tracker.scored()]), gallery)
    assert r.focus.excluded and r.focus.seen[track].exclude_misses == 1


def test_tracker_merge_starts_with_new_raw_drawing_geometry(robot):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    assert r.focus.seen[track].shown == CENTER
    smaller = (580, 390, 700, 510)
    frame_of(r, BLACK, box=smaller)
    assert track in r.tracker.merged and next(iter(r.view[1])) == track
    assert r.focus.seen[track].shown == smaller, "merged IDs cannot retain the old object's outline"


def test_item_exclusion_tracker_merge_has_no_counter_or_preference_transfer(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    state = r._shown(False)[1].control
    assert r._item_control('ignore', {**state, **state['targets'][0]}).startswith('Okay')
    track = next(iter(r.view[1]))
    frame_of(r, BLACK)
    preview(r)
    preview(r)
    assert r.focus.seen[track].exclude_misses == 2
    # A much smaller centered detection starts another track, then the real tracker merges it.
    frame_of(r, BLACK, box=(580, 390, 700, 510))
    assert track in r.tracker.merged and next(iter(r.view[1])) == track
    assert not r.focus.excluded and r.focus.seen[track].exclude_misses == 0
    assert r.focus.seen[track].shown == (580, 390, 700, 510)
    assert track not in r.focus.geometry([Track(*t) for t in r.tracker.scored()])
    preview(r)
    assert not r.focus.excluded and r.focus.seen[track].exclude_misses == 0
    frame_of(r, BLACK, box=(580, 390, 700, 510))
    preview(r)
    assert r._shown()[1].boxes, 'a distinct merged object needs its own strong Ignore match'


@pytest.mark.parametrize('known', [False, True])
def test_face_drawing_filters_exact_source_without_identity_carry(robot, monkeypatch, known):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll('Ana', [vector, vector], time.time())
    origin = time.time()
    clock = [origin]
    monkeypatch.setattr(main.time, 'time', lambda: clock[0])
    raw = [(500, 100, 600, 200)]
    received = []
    descriptor = [vector if known else np.eye(FACE_DIM, dtype=np.float32)[1]]
    def locate(faces, frame):
        received.append(frame)
        return [(descriptor[0], 100, raw[0])]
    monkeypatch.setattr(main, "located_faces", locate)
    first = frame_of(r, people=True)
    preview(r)
    before = r.verified[3][1]
    clock[0] += .067
    raw[0] = (498, 98, 608, 208)
    second = frame_of(r, BLACK, people=True)
    clock[0] += .15
    assert not r._completed_valid(r.verified), "old geometry is expired for publication"
    preview(r)
    outline = r.verified[3][1]
    assert outline[:4] == pytest.approx(tuple(a + SMOOTH * (b - a)
                                             for a, b in zip(before[:4], raw[0], strict=True)))
    assert outline[4:] == (('Ana', 'known') if known else ('', 'other'))
    assert r.verified[3][2] == raw[0], 'source matching keeps the raw face rectangle'
    assert received == [first, second], 'face inference receives the original source pixels'
    frame, screen = r._shown()
    assert frame is second and outline in screen.boxes and screen.valid()
    # A changed identity uses this source's geometry and cannot borrow a prior green name.
    clock[0] += .067
    descriptor[0] = np.eye(FACE_DIM, dtype=np.float32)[1] if known else vector
    raw[0] = (510, 105, 630, 225)
    frame_of(r, people=True)
    preview(r)
    assert r.verified[3][1][:4] == raw[0]
    assert r.verified[3][1][4:] == (('', 'other') if known else ('Ana', 'known'))
    # A fresh negative completion clears the filter, including anonymous history.
    clock[0] += .067
    monkeypatch.setattr(main, "located_faces", lambda *a: [])
    frame_of(r, people=True)
    preview(r)
    assert r.verified[3][1:] == (None, None)
    clock[0] += .067
    monkeypatch.setattr(main, "located_faces", locate)
    raw[0] = (490, 90, 620, 220)
    frame_of(r, people=True)
    preview(r)
    assert r.verified[3][1][:4] == raw[0]


def test_completed_object_geometry_keeps_source_admission_without_size_leak(robot, monkeypatch):
    r = robot
    origin = time.time()
    clock = [origin]
    monkeypatch.setattr(main.time, 'time', lambda: clock[0])
    source = frame_of(r, label='book')
    preview(r)
    track = next(iter(r.view[1]))
    old = r.verified
    clock[0] += .05
    frame_of(r, label='book', box=(540, 300, 659, 600))
    frame, screen = r._shown()
    assert frame is source and screen.boxes[0][:4] == CENTER and screen.valid()
    assert not r._shown(False)[1].control['targets'], 'old draw admission grants no current action'
    preview(r)
    assert r.verified is not old and r._shown()[1].boxes[0][4:] == ('', 'other')
    clock[0] += .16
    frame_of(r, label='book', box=(540, 300, 659, 600))
    preview(r)
    assert not r._shown()[1].boxes, 'repeated small raw sources exhaust bounded size grace'
    clock[0] += .01
    frame_of(r, label='book')
    assert not r._shown()[1].boxes, 'regrowth cannot invent drawing on the older small source'
    preview(r)
    assert r._shown()[1].boxes
    r._track(r.view[0], [], clock[0] + .01)
    assert not r.focus.boxes([], []), 'missing tracks never enter source geometry'
    assert r._shown()[1].boxes[0][4:] == ('', 'other'), 'drawing alone bridges the short gap'
    assert not r.focus.accepts(track, clock[0])
    clock[0] += .21
    assert not r._shown()[1].boxes, 'wall time also expires carried drawing'


@pytest.mark.parametrize('reset', ['gallery', 'session', 'gap', 'large-motion'])
def test_face_drawing_history_resets_on_changed_source_authority(robot, monkeypatch, reset):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll('Ana', [vector, vector], time.time())
    clock = [time.time()]
    monkeypatch.setattr(main.time, 'time', lambda: clock[0])
    raw = [(500, 100, 600, 200)]
    monkeypatch.setattr(main, "located_faces", lambda *a: [(vector, 100, raw[0])])
    frame_of(r, people=True)
    preview(r)
    assert r.verified[3][1][4:] == ('Ana', 'known')
    clock[0] += .067
    if reset == 'gallery':
        r.recognition.epoch += 1
    elif reset == 'session':
        r.session_id = 'different-session'
    elif reset == 'gap':
        r._track(r.view[0], [], clock[0])
        clock[0] += .01
    raw[0] = (620, 100, 720, 200) if reset == 'large-motion' else (498, 98, 608, 208)
    source = frame_of(r, people=True)
    preview(r)
    frame, screen = r._shown()
    assert frame is source and screen.valid()
    assert r.verified[3][1] == (*raw[0], 'Ana', 'known')


def test_settings_write_failure_keeps_active_values(tmp_path, monkeypatch):
    local = Settings(tmp_path / "settings.json")
    monkeypatch.setattr(main, "settings", local)
    def full_disk(*args, **kwargs):
        raise OSError("No space left on device")
    monkeypatch.setattr("robot.settings.os.replace", full_disk)
    robot = Robot.__new__(Robot)
    assert not robot._control("settings", {"name": "match", "value": .9})
    assert local.snapshot() == DEFAULTS
    assert not list(tmp_path.glob("*.tmp"))


def test_settings_validation_and_persistence(tmp_path):
    path = tmp_path / "settings.json"
    config = Settings(path)
    assert config.snapshot() == DEFAULTS
    for data in ({"name": "match", "value": .59}, {"name": "views_cap", "value": 3.5},
                 {"name": "match", "value": True}, {"name": "match", "value": float("nan")},
                 {"name": "unknown", "value": 1}, {"name": [], "value": 1},
                 {"reset": False}, [], {"name": "match", "value": "0.9"}):
        with pytest.raises(ValueError):
            config.change(data)
        assert config.snapshot() == DEFAULTS and not path.exists()
    config.change({"name": "match", "value": .9})
    assert config.match == .9 and Settings(path).snapshot() == config.snapshot()
    assert json.loads(path.read_text()) == {"match": .9}, "only changes: new defaults apply"
    config.change({"reset": True})
    assert Settings(path).snapshot() == DEFAULTS


def test_view_retention_keeps_first_drops_oldest_and_skips_duplicates(tmp_path, monkeypatch):
    monkeypatch.setitem(settings.values, "views_cap", 3)
    basis = np.eye(DIM, dtype=np.float32)
    np.testing.assert_array_equal(add_vectors(basis[:3], basis[2:5]), basis[[0, 3, 4]])
    things = Things(tmp_path)
    try:
        things.name(OWNER, 'cup', ['cup'], basis[:3], thumbnail_crops(basis[:3]))
        assert not things.add_view(
            object_id(things, OWNER, "cup"), basis[0], np.full((12, 20, 3), 90, np.uint8)
        )
        assert things.add_view(
            object_id(things, OWNER, "cup"), basis[3], np.full((12, 20, 3), 90, np.uint8)
        )
        np.testing.assert_array_equal(
            things.descriptors(object_id(things, OWNER, "cup")), basis[[0, 2, 3]]
        )
        assert not things.add_view(
            object_id(things, OWNER, "missing"), basis[3], np.full((12, 20, 3), 90, np.uint8)
        )
    finally:
        things.shard.close()


@pytest.mark.parametrize("stop", ["leave", "epoch", "time", "forget"])
def test_teaching_window_admits_at_gap_and_stops_permanently(robot, monkeypatch, stop):
    r = robot
    clock = [time.time()]
    monkeypatch.setattr(main.time, "time", lambda: clock[0])
    frame_of(r)
    hold(r, CENTER)
    assert "Turn it slowly" in ask(r, "This is my cup")[0]
    track = r.window["track"]
    epoch = r.recognition.epoch
    basis = np.eye(DIM, dtype=np.float32)
    vector = .8 * basis[GOLD] + .6 * basis[17]
    r.recognition.crops = lambda crops: np.asarray([vector])
    def query():
        r.view_taken = clock[0]
        r.crop_times.clear()
        tracks = [Track(*t) for t in r.tracker.scored()]
        r._query_objects(r.view[0], tracks, {t.id: r.focus.name(t.id) for t in tracks})
    clock[0] += .9
    query()
    assert r.window["admitted"] == 0
    clock[0] += .1
    query()
    assert (
        r.window["admitted"] == 1
        and len(r.things.descriptors(object_id(r.things, r.conversation_visitor, "cup"))) == 2
    )
    assert r.recognition.epoch == epoch
    assert '"event": "teaching_view"' in (r.out / "turns.jsonl").read_text()
    if stop == "leave":
        r._track(r.view[0], [])
    elif stop == "epoch":
        r.focus.seen[track].epoch += 1
    elif stop == "time":
        clock[0] += 6
    else:
        delete_thing(r, r.conversation_visitor, "cup")
    query()
    assert not r.window
    frame_of(r)
    query()
    assert not r.window


@pytest.mark.parametrize("block", ["ignore", "floor", "epoch", "crowded"])
def test_teaching_window_rechecks_admission_authority(robot, monkeypatch, block):
    r = robot
    clock = [time.time()]
    monkeypatch.setattr(main.time, "time", lambda: clock[0])
    frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my cup")
    window = r.window
    clock[0] += 1
    frame_of(r)
    if block == "crowded":  # an overlapping lookalike makes the taught crop impure
        x1, y1, x2, y2 = CENTER
        dets = [Detection("phone", .9, CENTER), Detection("phone", .8, (x1 + 90, y1, x2 + 90, y2))]
        for _ in range(CONFIRM):
            r._sight(r._track(r.view[0], dets, clock[0]))
    tracks = [Track(*t) for t in r.tracker.scored()]
    assert len(tracks) == (2 if block == "crowded" else 1)
    epochs = {t.id: r.focus.epoch(t.id) for t in tracks}
    source = (clock[0], epochs)
    basis = np.eye(DIM, dtype=np.float32)
    vector = .8 * basis[GOLD] + .6 * basis[17]
    if block == "floor":
        monkeypatch.setitem(settings.values, "window_floor", .9)
    elif block == "ignore":
        r.things.ignore_item("Ignored", vector[None])
    def embed(crops):
        if block == "epoch":
            r.focus.seen[window["track"]].epoch += 1
        return vector[None]
    r.recognition.crops = embed
    r.crop_times.clear()
    r._query_objects(r.view[0], tracks, {t.id: r.focus.name(t.id) for t in tracks}, source)
    assert (
        window["admitted"] == 0
        and len(r.things.descriptors(object_id(r.things, r.conversation_visitor, "cup"))) == 1
    )


def test_zero_window_keeps_the_short_naming_answer(robot, monkeypatch):
    monkeypatch.setitem(settings.values, "window_s", 0)
    frame_of(robot)
    hold(robot, CENTER)
    assert ask(robot, "This is my cup")[0] == "Got it, that is your cup. I will remember it."
    assert not robot.window


def test_duplicate_view_with_lowered_cap_is_not_an_admission(tmp_path, monkeypatch):
    things = Things(tmp_path)
    basis = np.eye(DIM, dtype=np.float32)
    try:
        things.name(OWNER, 'cup', ['cup'], basis[:3], thumbnail_crops(basis[:3]))
        assert things.add_view(
            object_id(things, OWNER, "cup"), basis[3], np.full((12, 20, 3), 90, np.uint8)
        )
        monkeypatch.setitem(settings.values, "views_cap", 3)
        assert not things.add_view(
            object_id(things, OWNER, "cup"), basis[0], np.full((12, 20, 3), 90, np.uint8)
        )
        np.testing.assert_array_equal(
            things.descriptors(object_id(things, OWNER, "cup")), basis[[0, 2, 3]]
        )
    finally:
        things.shard.close()


def test_teaching_window_prioritizes_only_the_taught_track_at_the_gap(robot, monkeypatch):
    r = robot
    clock = [time.time()]
    monkeypatch.setattr(main.time, "time", lambda: clock[0])
    show(r, [(GOLD, CENTER), (BLACK, RIGHT)])
    hold(r, CENTER)
    ask(r, "This is my cup")
    taught = r.window["track"]
    other = next(i for i in r.focus.visible if i != taught)
    basis = np.eye(DIM, dtype=np.float32)
    vector = .8 * basis[GOLD] + .6 * basis[17]
    r.recognition.crops = lambda crops: vector[None] if crops[0].mean() == GOLD else basis[[BLACK]]
    tracks = [Track(*t) for t in r.tracker.scored()]
    preferences = {t.id: r.focus.name(t.id) for t in tracks}
    r.crop_due = {taught: 100, other: 0}
    clock[0] += .9
    r.view_taken = clock[0]
    r.crop_times.clear()
    recognized, _ = r._query_objects(r.view[0], tracks, preferences)
    assert set(recognized) == {other} and r.window["admitted"] == 0
    clock[0] += .1
    r.view_taken = clock[0]
    r.crop_times.clear()
    recognized, _ = r._query_objects(r.view[0], tracks, preferences)
    assert set(recognized) == {taught} and r.window["admitted"] == 1
    np.testing.assert_array_equal(
        r.things.descriptors(object_id(r.things, r.conversation_visitor, "cup")),
        [basis[GOLD], vector],
    )


def test_forget_me_ends_the_teaching_window(robot):
    frame_of(robot)
    hold(robot, CENTER)
    ask(robot, "This is my cup")
    assert robot.window
    assert robot._forget(None, "Nobody", np.ones(512, np.float32), robot.conversation_visitor)
    assert not robot.window


def test_owner_contract_two_visitors_and_reteaching(robot):
    r = robot
    r.vocab.add("mouse")
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my mouse")[0].startswith("Got it")
    first = object_id(r.things, r.conversation_visitor, "mouse")
    assert r.things.label(first) == "Guest 1's mouse"
    frame_of(r, BLACK)
    hold(r, CENTER)
    assert ask(r, "This is my mouse")[0].startswith("Got it")
    assert object_id(r.things, r.conversation_visitor, "mouse") == first
    assert len(r.things.descriptors(first)) == 2
    r.conversation_visitor = r.things.new_visitor()
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my mouse")[0].startswith("Got it")
    second = object_id(r.things, r.conversation_visitor, "mouse")
    assert first != second and r.things.label(second) == "Guest 2's mouse"


def test_owner_promotion_and_restart(tmp_path):
    people = People(tmp_path)
    things = Things(tmp_path, people)
    owner = things.new_visitor()
    vectors = np.eye(DIM, dtype=np.float32)[:2]
    ident = things.name(owner, "mouse", ["mouse"], vectors, thumbnail_crops(vectors))
    things.tell(owner, "Ana")
    assert things.label(ident) == "Ana's mouse"
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    assert people.enroll("Ana", [face, face], 1.0, owner)
    things.tell(owner, "Other")
    assert things.label(ident) == "Ana's mouse"
    payload = things.named(owner, "mouse", [])
    files = {v["thumbnail"] for v in payload["views"]}
    assert files == {f.name for f in things.thumbs.glob("*.jpg")}
    for file in things.thumbs.glob("*.jpg"):
        assert max(cv2.imread(str(file)).shape[:2]) == 160
    things.shard.close()
    people.shard.close()
    people = People(tmp_path)
    things = Things(tmp_path, people)
    try:
        assert things.label(ident) == "Ana's mouse"
        assert things.named(owner, "mouse", []) == payload
        np.testing.assert_array_equal(things.descriptors(ident), vectors)
        assert files == {f.name for f in things.thumbs.glob("*.jpg")}
    finally:
        things.shard.close()
        people.shard.close()


def test_unknown_possessive_does_not_answer_from_sightings(robot):
    r = robot
    r.vocab.add("mouse")
    r.memory.sighting("mouse", "center", time.time())
    for text in ("Where is Ana's mouse?", "Have you seen Ana's mouse?"):
        assert ask(r, text)[0] == "I don't know which mouse is Ana's."


def test_owner_category_fallback_stays_with_requested_owner(robot):
    r = robot
    r.vocab.add("mouse")
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    other = r.things.new_visitor()
    r.things.name(other, "gaming mouse", ["mouse"], vectors, thumbnail_crops(vectors))
    assert r.things.named(r.conversation_visitor, "mouse", ["mouse"]) is None
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    assert r.people.enroll("Ana", [face, face], 1.0, other)
    assert ask(r, "Do you remember Ana's mouse?")[0].startswith(
        "Yes, I remember Ana's gaming mouse"
    )


def test_guest_forget_me_deletes_objects_record_and_window(robot, monkeypatch):
    r = robot
    frame = frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my phone")
    ask(r, "This is my cup")
    owner = r.conversation_visitor
    r.things.tell(owner, "Ana")
    r.told = "Ana", False
    assert r.window and r.things.visitor(owner)
    monkeypatch.setattr(r, "_whois", lambda frame, turn=None: None)
    turn = Turn(question="Forget me", visitor=owner)
    r.turn_seen = None
    assert r._identity(turn, frame, None) == "Should I forget everything about you? Say yes or no."
    assert r.things.objects(owner) and not turn.keep, "nothing is deleted before the yes"
    yes = Turn(question="Yes.", visitor=owner)
    assert r._deletion_answer(yes) == "Done. I have forgotten you." and not yes.keep
    assert not r.window and not r.told and not r.teaching
    assert not r.things.objects(owner) and r.things.visitor(owner) is None
    assert not list(r.things.thumbs.glob("*.jpg"))
    assert not r.memory.sightings(time.time() + 1, 99)
    assert r.memory.shard.count(CountRequest()) == 0


def test_faceless_forget_me_with_a_held_face_deletes_nothing(robot):
    r = robot
    frame = frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my phone")
    owner = r.conversation_visitor
    r.face, r.turn_seen = np.eye(FACE_DIM, dtype=np.float32)[0], None
    turn = Turn(question="Forget me", visitor=owner)
    assert r._identity(turn, frame, None) == NOT_YOU
    assert r.deleting is None and r.things.objects(owner)


def test_voice_deletion_asks_first(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my phone")
    owner = r.conversation_visitor
    named = r.things.named(owner, "phone", ["phone"])

    def said(text: str, visitor: str = owner) -> str | None:
        return r._deletion_answer(Turn(question=text, speech_start=time.time() + 1,
                                       visitor=visitor))

    assert ask(r, "Forget my phone")[0] == "Should I forget your phone? Say yes or no."
    assert r.things.named(owner, "phone", ["phone"]), "the request deletes nothing"
    assert said("No, keep it.") == "Okay, I will keep it."
    assert r.things.named(owner, "phone", ["phone"]) and r.deleting is None, "no keeps it"
    ask(r, "Forget my phone")
    assert said("What do you see?") is None and r.deleting is None, "any other line drops it"
    assert said("Yes.") is None and r.things.named(owner, "phone", ["phone"]), "once only"
    ask(r, "Forget my phone")
    assert said("Yes.", visitor="someone else") is None, "another visitor's yes"
    assert r.things.named(owner, "phone", ["phone"]) and r.deleting is None
    ask(r, "Forget my phone")
    r.deleting = r.deleting[0], time.time() - 1, r.deleting[2]
    assert said("Yes.") is None and r.things.named(owner, "phone", ["phone"]), "late yes"
    ask(r, "Forget my phone")
    r._clear_confirmation()  # a new conversation
    assert r.deleting is None
    said_ok, turn = ask(r, "Forget my phone? No, do not delete it.")
    assert said_ok.startswith("Should I forget") and not turn.keep
    assert said("No, do not delete it.") == "Okay, I will keep it."
    assert r.things.named(owner, "phone", ["phone"]) == named
    assert forget(r, "Forget my phone")[0] == "Done. I have forgotten your phone."
    assert r.things.named(owner, "phone", ["phone"]) is None
    assert ask(r, "Forget my phone")[0] == "I don't know your phone, so there is nothing to forget."
    assert r.deleting is None


def test_startup_sweeps_orphan_thumbnails(tmp_path):
    things = Things(tmp_path)
    orphan = things.thumbs / "orphan.jpg"
    orphan.write_bytes(b"orphan")
    things.shard.close()
    things = Things(tmp_path)
    try:
        assert not orphan.exists()
    finally:
        things.shard.close()


def test_old_schema_deleted_and_existing_people_visitors(tmp_path):
    from qdrant_edge import (
        EdgeConfig,
        EdgeShard,
        EdgeVectorParams,
        Distance,
        Point,
        UpdateOperation,
    )
    path = tmp_path / "things"
    path.mkdir()
    old = EdgeShard.create(str(path), EdgeConfig(vectors={"crops": EdgeVectorParams(
        size=DIM, distance=Distance.Cosine)}))
    old.update(UpdateOperation.upsert_points([Point(1, {}, {"name": "old mouse"})]))
    old.flush()
    old.close()
    people = People(tmp_path)
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    assert people.enroll("Ana", [face, face], 1.0)
    from robot.people import _id
    people.shard.update(UpdateOperation.delete_payload([_id("Ana")], ["visitor"]))
    things = Things(tmp_path, people)
    try:
        assert people.person("Ana")["visitor"]
        assert not things.objects() and not things.shard.retrieve([1], False, False)
        assert [p.name for p in tmp_path.iterdir() if p.name.startswith("things")] == ["things"]
    finally:
        things.shard.close()
        people.shard.close()


def test_dinov2_shard_keeps_only_records_without_vectors(tmp_path):
    from qdrant_edge import Point, UpdateOperation
    from robot.things import _id
    visitor = "00000000-0000-4000-8000-0000000000aa"
    things = Things(tmp_path)
    things.name(visitor, "phone", ["phone"], np.eye(DIM, dtype=np.float32)[:1],
                thumbnail_crops([0]), display="Ana")
    things.ignore_item("phone", np.eye(DIM, dtype=np.float32)[:1])
    things.ignore(["chair"], True)
    guest = things._guest_number()
    thumb, = things.thumbs.glob("*.jpg")
    marker, old_marker = _id("schema:dinov3"), _id("schema:owners")
    things.shard.update(UpdateOperation.delete_points([marker]))  # the shard a DINOv2 robot made
    things.shard.update(UpdateOperation.upsert_points([Point(old_marker, {}, {"schema": 1})]))
    things.shard.flush()
    things.shard.close()
    things = Things(tmp_path)
    try:
        assert not things.objects() and not things.items and not list(things.thumbs.glob("*.jpg"))
        assert things.visitor(visitor)["display"] == "Ana" and things.ignored() == {"chair"}
        assert things._guest_number() == guest + 1, "the guest counter carries over"
        assert things.shard.retrieve([marker], False, False)
        assert not things.shard.retrieve([old_marker], False, False)
        assert not (things.thumbs / thumb.name).exists() and not list(tmp_path.glob("*backup*"))
    finally:
        things.shard.close()


def test_forget_object_removes_thumbnails_and_ignore_exclusions(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my phone")
    ident = object_id(r.things, r.conversation_visitor, "phone")
    vectors = r.things.descriptors(ident)
    rule = r.things.ignore_item("phone", vectors)
    assert ident in r.things.hidden_ids()
    assert r.things.score(vectors[0]) is None
    assert forget(r, "Forget my phone")[0].startswith("Done")
    assert not r.window and not list(r.things.thumbs.glob("*.jpg"))
    assert not r.things.add_view(ident, vectors[0], thumbnail_crops(vectors)[0])
    assert ident not in r.things.hidden_ids()
    assert not r.things.shard.retrieve([rule], True, True)


def test_visitor_resolution_allocates_once_per_turn(robot, monkeypatch):
    r = robot
    calls = []
    allocate = r.things.new_visitor
    monkeypatch.setattr(r.things, "new_visitor", lambda: calls.append(1) or allocate())
    monkeypatch.setattr(r, "_whois", lambda frame, turn=None: None)
    r.conversation_started = False
    first = Turn(question="Hello", speech_start=time.time())
    assert not r._resolve_visitor(first, np.zeros((9, 9, 3), np.uint8))
    assert first.visitor == r.conversation_visitor and not calls
    r.last_line = time.time()
    second = Turn(question="I'm Ana", speech_start=r.last_line + main.CONVERSATION_S + 1)
    assert r._resolve_visitor(second, np.zeros((9, 9, 3), np.uint8))
    r._resolve_visitor(second, np.zeros((9, 9, 3), np.uint8))
    r._hear_name(second)
    assert calls == [1] and second.visitor != first.visitor


def test_spoken_name_then_enrollment_preserves_guest_objects(robot, monkeypatch):
    r = robot
    frame = frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my mouse")
    owner = r.conversation_visitor
    ident = object_id(r.things, owner, "mouse")
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    monkeypatch.setattr(r, "_whois", lambda frame, turn=None: (face, None))
    r.face, r.last_line = face, time.time()
    told = Turn(question="I'm Ana", speech_start=r.last_line + 1)
    assert "remember your face" in r._identity(told, frame, None)
    assert r.things.label(ident) == "Ana's mouse"
    yes = Turn(question="Yes", speech_start=r.last_line + 2)
    assert r._identity(yes, frame, None) == "Thank you, Ana. I will remember your face."
    assert r.people.person("Ana")["visitor"] == owner
    assert object_id(r.things, owner, "mouse") == ident
    r.turn_seen = np.eye(FACE_DIM, dtype=np.float32)[1], None
    stranger = Turn(question="Remember me, I'm Ana", visitor=owner)
    assert r._identity(stranger, frame, None) == "I already know someone called Ana."


def test_restart_sweeps_thumbnails_left_by_visitor_deletion(tmp_path, monkeypatch):
    things = Things(tmp_path)
    owner = things.new_visitor()
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    ident = things.name(owner, "mouse", ["mouse"], vectors, thumbnail_crops(vectors))
    _, _, thumbnails = things.forget_visitor(owner)
    things.shard.close()
    things = Things(tmp_path)
    try:
        assert things.visitor(owner) is None and not things.objects(owner)
        assert not things.shard.retrieve([ident], True, False)
        assert thumbnails and not list(things.thumbs.glob("*.jpg"))
    finally:
        things.shard.close()


@pytest.mark.parametrize("shard_name, fail_at", [
    ("memory", 1), ("memory", 2), ("memory", 3), ("memory", 4),
    ("people", 1), ("things", 1)])
def test_forget_visitor_retry_after_store_interruption(robot, shard_name, fail_at):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my phone")
    owner = r.conversation_visitor
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    assert r.people.enroll("Ana", [face, face], 1.0, owner)
    pid = r.memory.add(np.zeros((12, 12, 3), np.uint8), "I like tea", visitor=owner,
                       caption="A personal frame")
    r.people.link("Ana", [pid])
    ident = object_id(r.things, owner, "phone")
    rule = r.things.ignore_item("Ana's phone", r.things.descriptors(ident))
    r.things.ignore(["chair"], True)
    r.history = [{"role": "user", "content": "I like tea"}]
    r.ready = object()
    store = getattr(r, shard_name)
    original = store.shard

    class Interrupted:
        calls = 0

        def __getattr__(self, key):
            return getattr(original, key)

        def update(self, operation):
            self.calls += 1
            if self.calls == fail_at:
                raise RuntimeError("Interrupted before shard deletion")
            return original.update(operation)

    store.shard = Interrupted()
    assert not r._forget(None, "Ana", face, owner)
    if shard_name == "people":  # people go last: objects are gone, the face still finds `owner`
        assert not r.things.objects(owner) and r.people.person("Ana")["visitor"] == owner
    else:
        assert r.things.objects(owner) and r.things.visitor(owner)
    store.shard = original
    assert r._forget(None, "Ana", face, owner)
    assert not r.things.objects(owner) and not r.things.visitor(owner)
    assert r.people.person("Ana") is None
    assert not r.memory.points([pid])
    assert not r.memory.shard.count(CountRequest())
    assert not list(r.memory.frames.glob("*.jpg"))
    assert not list(r.things.thumbs.glob("*.jpg"))
    assert not r.things.shard.retrieve([rule], True, True)
    assert r.things.ignored() == {"chair"}
    assert not r.history and not r.looked and r.ready is None


@pytest.mark.parametrize("shard_name, fail_at", [("memory", 1), ("memory", 2), ("things", 1)])
def test_forget_object_retry_after_store_interruption(robot, shard_name, fail_at):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    ask(r, "This is my phone")
    owner = r.conversation_visitor
    store = getattr(r, shard_name)
    original = store.shard

    class Interrupted:
        calls = 0

        def __getattr__(self, key):
            return getattr(original, key)

        def update(self, operation):
            self.calls += 1
            if self.calls == fail_at:
                raise RuntimeError("Interrupted before shard deletion")
            return original.update(operation)

    store.shard = Interrupted()
    with pytest.raises(RuntimeError):
        forget(r, "Forget my phone")
    assert r.things.objects(owner)
    store.shard = original
    assert forget(r, "Forget my phone")[0].startswith("Done")
    assert not r.things.objects(owner)
    assert not r.memory.shard.count(CountRequest())
    assert not list(r.things.thumbs.glob("*.jpg"))


def test_other_owner_naming_stores_nothing(robot):
    robot.vocab.add("mouse")
    frame_of(robot)
    hold(robot, CENTER)
    answer, turn = ask(robot, "This is Ana's mouse")
    assert answer == "I can only learn things that are yours. Say: this is my mouse."
    assert not robot.things.objects() and not turn.keep
    assert store(robot, turn) == 0


def test_normalized_object_key_and_duplicate_no_write(tmp_path):
    things = Things(tmp_path)
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    try:
        ident = things.name(OWNER, "Gaming  Mouse", ["mouse"], vectors, thumbnail_crops(vectors))
        assert things.named(OWNER, "gaming mouse", [])["id"] == ident
        original = things.shard

        class NoWrites:
            def __getattr__(self, key):
                return getattr(original, key)

            def update(self, _operation):
                pytest.fail("An unchanged view must not write")

        things.shard = NoWrites()
        assert not things.add_view(ident, vectors[0], thumbnail_crops(vectors)[0])
        things.shard = original
    finally:
        things.shard.close()


def test_startup_thumbnail_sweep_keeps_objects_after_first_page(tmp_path):
    import uuid
    from qdrant_edge import Point, UpdateOperation

    things = Things(tmp_path)
    rows = [Point(str(uuid.uuid4()), {}, {"type": "object", "owner": OWNER,
             "views": [{"thumbnail": f"{i}.jpg"}]}) for i in range(1001)]
    things.shard.update(UpdateOperation.upsert_points(rows))
    things.shard.flush()
    for i in range(1001):
        (things.thumbs / f"{i}.jpg").write_bytes(b"thumbnail")
    things.shard.close()
    things = Things(tmp_path)
    try:
        assert len(things.objects()) == 1001
        assert len(list(things.thumbs.glob("*.jpg"))) == 1001
    finally:
        things.shard.close()


def test_stored_guest_statement_uses_visitor_and_forget_clears_it(robot, monkeypatch):
    monkeypatch.setattr(robot, "_whois", lambda frame: None)
    turn = Turn(question="I like tea", visitor=robot.conversation_visitor)
    assert store(robot, turn) == 1
    assert robot.memory.points([turn.frame_id])[0]["visitor"] == turn.visitor
    assert robot._forget(None, None, None, turn.visitor)
    assert not robot.memory.points([turn.frame_id])


def test_screen_reuses_label_map_without_per_box_lookup(robot, monkeypatch):
    frame_of(robot)
    hold(robot, CENTER)
    ask(robot, "This is my phone")
    monkeypatch.setattr(robot.things, "label", lambda ident: pytest.fail("Per-box lookup"))
    assert robot._shown(False)[1].control["targets"][0]["title"] == "Guest 1's phone"


def test_third_person_answer_preserves_object_name(robot, monkeypatch):
    monkeypatch.setattr(robot, "named_evidence", lambda *args: ([], 1, {1: 0.9}, ""))
    assert robot._mine(Turn(), "remember", {"name": "your mouse"}, "Ana's") == (
        "Yes, I remember Ana's your mouse. Yes, Ana's your mouse is here now.")


def test_interrupted_forget_me_keeps_the_face_to_visitor_link_for_a_retry(robot, monkeypatch):
    r = robot
    face = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [face, face], time.time())
    visitor = r.people.person("Ana")["visitor"]
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    r.things.name(visitor, "mouse", ["mouse"], vectors, thumbnail_crops(vectors))
    real = r.things.forget_visitor
    monkeypatch.setattr(r.things, "forget_visitor", lambda owner: (_ for _ in ()).throw(OSError))
    assert not r._forget(None, "Ana", face, visitor)
    assert r.people.person("Ana")["visitor"] == visitor, "the face still finds the same visitor"
    monkeypatch.setattr(r.things, "forget_visitor", real)
    assert r._forget(None, "Ana", face, r.people.person("Ana")["visitor"])
    assert not r.things.objects(visitor) and r.people.person("Ana") is None


def test_memory_list_keeps_visitors_with_the_same_name_distinct(robot):
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    visitors = [OWNER, "00000000-0000-4000-8000-000000000002"]
    for visitor in visitors:
        robot.things.name(visitor, "mouse", ["mouse"], vectors, thumbnail_crops(vectors), "Sam")
    listed = robot._memory_list()
    assert {item["owner"] for item in listed} == set(visitors)
    assert [item["owner_label"] for item in listed] == ["Sam", "Sam"]


def test_remove_view_vector_metadata_file_and_final_object(tmp_path):
    things = Things(tmp_path)
    try:
        vectors = np.eye(DIM, dtype=np.float32)[:3]
        ident = things.name(OWNER, "mouse", ["mouse"], vectors, thumbnail_crops(vectors))
        views = things.named(OWNER, "mouse", [])["views"]
        assert not things.remove_view(ident, "unknown")
        assert things.remove_view(ident, views[1]["id"])
        row = things.shard.retrieve([ident], True, True)[0]
        assert row.payload["views"] == [views[0], views[2]]
        np.testing.assert_array_equal(row.vector["crops"], vectors[[0, 2]])
        assert not (things.thumbs / views[1]["thumbnail"]).exists()
        assert things.remove_view(ident, views[0]["id"])
        assert things.remove_view(ident, views[2]["id"])
        assert not things.objects() and not list(things.thumbs.glob("*.jpg"))
        assert not things.remove_view(ident, views[2]["id"])
    finally:
        things.shard.close()


@pytest.mark.parametrize("action", ["forget_object", "remove_view"])
def test_memory_controls_delete_evidence_like_speech(robot, action):
    r = robot
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    ident = r.things.name(OWNER, "mouse", ["mouse"], vectors, thumbnail_crops(vectors), "Ana")
    sighting = r.memory.sighting("mouse", "center", 10, named=ident)
    r.points = {1: sighting}
    r.window = {"name": ident}
    r.things.ignore_item("mouse", vectors)
    listed = r._memory_list()
    assert listed[0]["label"] == "Ana's mouse"
    assert listed[0]["owner_label"] == "Ana"
    assert listed[0]["owner"] == OWNER
    assert listed[0]["sightings"] == 1 and listed[0]["last_seen"] == 10
    view = listed[0]["views"][0]["id"]
    assert r._thumbnail(view).startswith(b"\xff\xd8")
    assert r._thumbnail("unknown") is None
    assert not r._control(action, {"object": "../path", "view": view})
    if action == "remove_view":
        assert not r._control(action, {"object": ident, "view": "../path"})
    def worker():  # the conversation worker: the same queue that writes sightings
        job = r.jobs.get_nowait()
        assert job[0] == "memory" and r.jobs.empty()
        return r._memory_job(*job[1:])

    assert r._control(action, {"object": ident, "view": view})
    assert r.things.objects(), "queued behind earlier evidence writes, not run at once"
    assert worker() == "Done."
    assert not r.things.objects() and not r.memory.points([sighting])
    assert not r.points and not r.window and not r.things.hidden_ids()
    assert not list(r.things.thumbs.glob("*.jpg"))
    assert r._control(action, {"object": ident, "view": view})
    assert worker() == "That memory no longer exists."


@pytest.mark.parametrize('answer', ['yes', 'no', 'Where is my cup?', 'expired', 'visitor'])
def test_near_confirmation_reply(robot, monkeypatch, answer):
    r = robot
    clock = [time.time()]
    monkeypatch.setattr(main.time, 'time', lambda: clock[0])
    frame_of(r)
    hold(r, CENTER)
    ask(r, 'This is my cup')
    r.window = None
    r.jobs = queue.Queue()  # naming queued a caption; these tests exercise idle confirmation
    ident = object_id(r.things, OWNER, 'cup')
    track = r.focus.focus
    basis = np.eye(DIM, dtype=np.float32)
    vector = .8 * basis[GOLD] + .6 * basis[17]
    r.last_line = clock[0] - 5
    played = []
    r.voice = SimpleNamespace(say=lambda text: played.append(text) or np.zeros(1))
    r.speaker.play = lambda pcm: None
    def near(score=.8):
        r._near_match(Track(track, CENTER, 'cup', .9), (ident, score), vector,
                      r.view[0], (clock[0], {track: r.focus.epoch(track)}))
    near()
    assert r.jobs.empty()
    clock[0] += 3
    near()
    job = r.jobs.get_nowait()
    r._confirm(job[1])
    assert played == ['Is this your cup?'] and r.confirming
    near()
    assert r.jobs.empty()
    before = len(r.things.descriptors(ident))
    text = answer
    visitor = OWNER
    if answer == 'expired':
        clock[0] += main.CONVERSATION_S + 1
        text = 'yes'
    elif answer == 'visitor':
        visitor, text = 'other', 'yes'
    turn = Turn(question=text, visitor=visitor, speech_start=clock[0])
    result = r._confirmation_answer(turn)
    assert not r.confirming
    assert len(r.things.descriptors(ident)) == before + (answer == 'yes')
    if answer == 'yes':
        assert result == 'Thanks, I will remember it from this side too.'
        row = r.things.shard.retrieve([ident], True, False)[0]
        assert row.payload['views'][-1]['source'] == 'confirmed'
    elif answer == 'no':
        assert result == 'Okay.'
        near()
        assert r.jobs.empty()
    else:
        assert result is None
        if answer == 'Where is my cup?':
            assert ask(r, text)[0], 'the unrelated question follows the normal object answer path'


@pytest.mark.parametrize('block', ['match', 'turn', 'teaching', 'rate', 'max', 'off',
                                   'blank', 'speech', 'identity', 'job'])
def test_near_confirmation_cancellation_and_limits(robot, monkeypatch, block):
    r = robot
    clock = [time.time()]
    monkeypatch.setattr(main.time, 'time', lambda: clock[0])
    frame_of(r)
    hold(r, CENTER)
    ask(r, 'This is my cup')
    r.window = None
    r.jobs = queue.Queue()  # naming queued a caption; these tests exercise idle confirmation
    ident = object_id(r.things, OWNER, 'cup')
    track = r.focus.focus
    def near(score=.8):
        r._near_match(Track(track, CENTER, 'cup', .9), (ident, score),
                      np.eye(DIM, dtype=np.float32)[GOLD], r.view[0],
                      (clock[0], {track: r.focus.epoch(track)}))
    r.last_line = clock[0] - 5
    near()
    if block == 'match':
        clock[0] += 1
        near(settings.match)
        assert r.candidate is None and r.jobs.empty()
        return
    clock[0] += 3
    if block == 'off':
        monkeypatch.setitem(settings.values, 'ask_max', 0)
    near()
    if block == 'off':
        assert r.jobs.empty()
        return
    changes = {'turn': ('ui_thinking', True),
               'teaching': ('teaching', (track, r.focus.epoch(track))),
               'rate': ('confirm_last', clock[0] - 59),
               'max': ('confirm_count', settings.ask_max),
               'blank': ('last_line', clock[0] - 1),
               'speech': ('speaking', True), 'identity': ('asking', ('Ana', 1, []))}
    if block in changes:
        name, value = changes[block]
        setattr(r, name, value)
    job = r.jobs.get_nowait()
    if block == 'job':
        r.jobs.put(('look', None))
    r._confirm(job[1])
    assert r.confirming is None and r.candidate is None


def test_readable_evidence_uses_stored_links_and_stays_out_of_logs(robot):
    import json
    r = robot
    ident = r.things.name(OWNER, "camera", ["camera"], np.eye(DIM, dtype=np.float32)[:1],
                          thumbnail_crops([1]), "Ana")
    pid = r.memory.sighting("camera", "center", 10, ident)
    statement = r.memory.add(None, "I like photography", ts=12)
    caption = r.memory.add(None, "", ts=13, caption="A black camera on a desk")
    turn = Turn(memories=[pid, statement, caption, 999])
    turn.ui_evidence = r._evidence(turn)
    assert len(turn.ui_evidence) == 3
    obj, said, generated = turn.ui_evidence
    assert obj["id"] == pid and obj["label"] == "Ana's camera"
    assert obj["object"] == ident and r._thumbnail(obj["view"]).startswith(b"\xff\xd8")
    assert obj["source"] == "Observed object" and obj["time"] == 10
    assert said["text"] == "I like photography" and "object" not in said
    assert generated["source"] == "Stored caption"
    r.turns = queue.Queue()
    r._log(turn)
    record = json.loads((r.out / "turns.jsonl").read_text())
    assert "ui_evidence" not in record and record["memories"] == turn.memories
    r.things.thumbs.joinpath(r.things.objects()[0].payload["views"][0]["thumbnail"]).unlink()
    assert r._evidence(turn)[0]["view"] is None
    r.things.forget(ident)
    assert all("object" not in item for item in r._evidence(turn))


def test_readable_evidence_expires_with_its_source(robot):
    from robot.memory import RETAIN_S
    r = robot
    pid = r.memory.add(None, "An old observation", ts=1)
    r.ui_turn = Turn(memories=[pid], ui_evidence=r._evidence(Turn(memories=[pid])))
    r.ui_turns.append(r.ui_turn)
    assert r.ui_turn.ui_evidence
    r._retain(RETAIN_S + 2)
    assert not r.ui_turn.ui_evidence


def test_retention_keeps_named_object_evidence_until_forgotten(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    said, turn = ask(r, "This is my phone.")
    assert said.startswith("Got it")
    ident = object_id(r.things, OWNER, "phone")
    [naming] = turn.memories
    [newest] = [s["id"] for s in r.memory.sightings(float("inf"), 1, named=[ident])]
    older = r.memory.sighting("phone", "left", 5, ident)
    unnamed = r.memory.sighting("chair", "left", 6)
    show(r, [], LOST + 1)  # taken away, and 30 hours go by
    later = time.time() + 30 * 3600
    r._retain(later)
    assert {p["id"] for p in r.memory.points([naming, newest, older, unnamed])} == {naming, newest}
    turn = Turn(question="When did you last see my phone?", speech_start=later, visitor=OWNER)
    assert r._things(turn) == "I last saw your phone 30 hours ago; I don't see it now."
    delete_thing(r, OWNER, "phone")
    assert not r.memory.points([naming, newest])


@pytest.mark.parametrize("action", ["speech", "forget_object", "remove_view", "visitor"])
def test_readable_evidence_clears_on_deletion(robot, action):
    r = robot
    ident = r.things.name(OWNER, "mouse", ["mouse"], np.eye(DIM, dtype=np.float32)[:1],
                          thumbnail_crops([1]), "Ana")
    pid = r.memory.sighting("mouse", "center", 10, ident)
    r.ui_turn = Turn(memories=[pid], ui_evidence=r._evidence(Turn(memories=[pid])))
    r.ui_turns.append(r.ui_turn)
    view = r.ui_turn.ui_evidence[0]["view"]
    if action == "speech":
        delete_thing(r, OWNER, "mouse")
    elif action == "visitor":
        assert r._forget(None, None, None, OWNER)
    else:
        assert r._memory_job(action, {"object": ident, "view": view}) == "Done."
    assert not r.ui_turn.ui_evidence
    assert not r.memory.points([pid]) and r._thumbnail(view) is None


def test_readable_evidence_resolves_linked_teaching_statements(robot):
    r = robot
    ident = r.things.name(OWNER, "camera", ["camera"], np.eye(DIM, dtype=np.float32)[:1],
                          thumbnail_crops([1]), "Ana")
    pid = r.memory.add(None, "Track this as my camera", ts=10)
    r.things.link(ident, pid)
    r.ui_turn = Turn(memories=[pid], ui_evidence=r._evidence(Turn(memories=[pid])))
    r.ui_turns.append(r.ui_turn)
    assert r.ui_turn.ui_evidence[0]["object"] == ident
    assert r.ui_turn.ui_evidence[0]["label"] == "Ana's camera"
    delete_thing(r, OWNER, "camera")
    assert not r.ui_turn.ui_evidence and not r.memory.points([pid])


def test_state_poll_does_not_resolve_evidence_again(robot, monkeypatch):
    r = robot
    frame_of(r)
    pid = r.memory.add(None, "I enjoy photography", ts=12)
    r.ui_turn = Turn(memories=[pid], ui_evidence=r._evidence(Turn(memories=[pid])))
    def unexpected(*args):
        raise AssertionError("State polling must not resolve evidence")
    monkeypatch.setattr(r, "_evidence", unexpected)
    monkeypatch.setattr(r.memory, "points", unexpected)
    for _ in range(3):
        assert r._shown(False)[1].evidence["memories"][0]["text"] == "I enjoy photography"


@pytest.mark.parametrize('change', ['expiry', 'ignore', 'forget', 'replacement', 'return'])
def test_carried_preview_rechecks_validity_at_publication(robot, monkeypatch, change):
    r = robot
    clock = [time.time()]
    monkeypatch.setattr(main.time, 'time', lambda: clock[0])
    frame = frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.bind(track, 'Known object')
    clock[0] += .05
    r._track(frame.copy(), [], clock[0])
    _, screen = r._shown()
    assert screen.boxes[0][4:] == ('Known object', 'known') and screen.valid()
    assert not r.focus.target([]) and not r.focus.accepts(track, clock[0] - .05)
    if change == 'expiry':
        clock[0] += .16
    elif change == 'ignore':
        r.focus.ignored.add('phone')
    elif change == 'forget':
        r.focus.forget('Known object')
    elif change == 'replacement':
        # One frame, still unconfirmed: it already suppresses the old label at that position.
        r._track(frame, [Detection('book', .9, (580, 380, 700, 500))], clock[0] + .01)
    else:
        frame_of(r)
    assert not screen.valid(), 'an encoded held overlay cannot outlive its display authority'


def test_memory_map_uses_stored_ids_and_bounded_payloads(robot):
    vectors = np.eye(DIM, dtype=np.float32)[:2]
    ident = robot.things.name(OWNER, 'clock', ['clock'], vectors, thumbnail_crops(vectors))
    created = robot.things.shard.retrieve([ident], True, False)[0].payload['created']
    old = robot.memory.add(None, 'An earlier statement', ts=1, named=ident)
    for i in range(135):
        robot.memory.add(None, f'Statement {i}', ts=10+i)
    for i in range(70):
        robot.memory.sighting('clock', 'center', 10+i, named=ident)
    robot.ui_turn = Turn(line=1000, retrieved=1001, ui_recalled=[old])
    snapshot = robot._memory_map()
    nodes = {p['id']: p for p in snapshot['nodes']}
    assert snapshot['total'] == 207 and len(nodes) == 194
    assert f'seen:{old}' in nodes and nodes[f'seen:{old}']['created'] > 1
    assert nodes[f'seen:{old}']['object'] == f'things:{ident}'
    assert snapshot['recall']['ids'] == sorted([f'seen:{old}', f'things:{ident}'])
    assert all(set(p) <= {'id', 'kind', 'label', 'created', 'object'} for p in nodes.values())
    delayed = robot.memory.add(None, 'Delayed storage', ts=1)
    robot.ui_turn = Turn(frame_id=delayed)
    assert f'seen:{delayed}' in {p['id'] for p in robot._memory_map()['nodes']}
    assert not robot._memory_map()['recall']['ids'], 'Storing a point does not recall it'
    robot.ui_turn = Turn(line=1000, retrieved=1001, ui_recalled=[old])
    view = robot.things.shard.retrieve([ident], True, False)[0].payload['views'][0]['id']
    assert robot.things.remove_view(ident, view)
    assert robot._memory_map()['nodes'][-1]['created'] == created
    # Legacy objects have no reliable creation time. Removing a view cannot invent a birth.
    robot.things.shard.update(UpdateOperation.delete_payload([ident], ['created']))
    assert robot._memory_map()['nodes'][-1]['created'] == 0
    robot.memory.forget([old])
    assert f'seen:{old}' not in {p['id'] for p in robot._memory_map()['nodes']}
    assert not robot._memory_map()['recall']['ids']
    robot.ui_turn.deleted = True
    assert not robot._memory_map()['recall']['ids']


def test_memory_map_survives_reopen_and_forget(tmp_path):
    r = open_robot(tmp_path)
    vectors = np.eye(DIM, dtype=np.float32)[:1]
    try:
        ident = r.things.name(OWNER, 'clock', ['clock'], vectors, thumbnail_crops(vectors))
        pid = r.memory.sighting('clock', 'center', time.time(), named=ident)
        before = r._memory_map()
    finally:
        r.memory.shard.close()
        r.people.shard.close()
        r.things.shard.close()
    r = open_robot(tmp_path)
    try:
        assert r._memory_map()['nodes'] == before['nodes']
        r.memory.forget_named(ident)
        r.things.forget(ident)
        assert r.memory.points([pid]) == []
        assert r._memory_map()['nodes'] == []
    finally:
        r.memory.shard.close()
        r.people.shard.close()
        r.things.shard.close()


def test_pronoun_statement_after_naming_is_forgotten_with_the_object(robot):
    r = robot
    r.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[[0] * len(texts)]
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    start = time.time()
    answer, named = ask(r, "This is my phone")
    assert answer.startswith("Got it")
    named.speech_start = start
    shot = (r.view[0], start)
    assert r._store(named, shot, None, None)
    vec = np.eye(TEXT_DIM, dtype=np.float32)[0]
    # A chain of follow-ups, each under CONVERSATION_S after the one before, but the last more
    # than CONVERSATION_S after the naming; then an unrelated statement, then an object question.
    for text, dt in [("I bought it in Paris.", 50), ("They gave me a discount.", 100),
                     ("I purchased it in Berlin.", 150), ("I live in Lyon.", 160)]:
        said = Turn(question=text, answer="Nice.", speech_start=start + dt, visitor=named.visitor)
        assert r._store(said, shot, vec, None)
    asked = Turn(question="Where is my phone?", speech_start=start + 300, visitor=named.visitor)
    assert r._things(asked, None)
    after = Turn(question="That was a gift.", answer="Lovely.", speech_start=start + 310,
                 visitor=named.visitor)
    assert r._store(after, shot, vec, None)
    assert forget(r, "Forget my phone")[0].startswith("Done")
    root = r.memory.frames.parent
    r.memory.shard.close()
    r.memory = Memory(root)
    left = [m["said"] for m in r.memory.told(vec, start + 999, visitor=named.visitor, n=9)]
    assert left == ["I live in Lyon."], left
    assert r.memory.exchanges(named.visitor, start + 999, 9, vec, "phone Paris gift") == []
