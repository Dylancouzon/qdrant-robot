"""Naming, recall by name, forget, and ignore through the robot's own tracking and
answers, on real Edge shards and the real tracker, with a stub crop embedder (one vector per
color), including restarts."""
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
from robot.detect import CONFIRM, LOST, Detection, Tracker
from robot.focus import Track
from robot.main import Robot, Turn
from robot.memory import CountRequest, Memory, ScrollRequest
from robot.people import DIM as FACE_DIM, People
from robot.recognition import Recognition
from robot.text_embed import DIM as TEXT_DIM
from robot.things import DIM, SHOTS, VIEWS, Things, command, diverse

GOLD, BLACK = 200, 30  # the pixel value of each phone: the stub tells them apart by it
LEFT, CENTER, RIGHT = (100, 300, 300, 600), (540, 300, 740, 600), (1000, 300, 1200, 600)


def stub_crops(crops: list[np.ndarray]) -> np.ndarray:
    return np.eye(DIM, dtype=np.float32)[[int(c.mean()) for c in crops]]


def open_robot(root: Path) -> Robot:
    robot = Robot.__new__(Robot)  # no models: real shards, tracker, and a stub crop embedder
    robot.memory, robot.things, robot.people = Memory(root), Things(root), People(root)
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
    robot.view, robot.views = (None, {}), deque(maxlen=SHOTS)
    robot.view_at, robot.view_taken, robot.verified = 0, 0, None
    robot.camera_source = "Live camera"
    robot.shown_taken, robot.session_id, robot.control_message = 0, "test-session", ""
    robot.shown_frame, robot.shown_record = 0, 0
    robot.shown_known = False
    robot.crop_due, robot.crop_times, robot.matches_pending = {}, deque(), False
    robot.item_checked = {}
    robot.detecting, robot.detect_failed, robot.history = threading.Lock(), None, []
    robot.delivery = threading.Condition(robot.detecting)
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
    if robot.named or robot.things.items:
        for _ in range(max(1, len(robot.view[1]))):
            preview(robot)


def hold(robot: Robot, box: tuple) -> None:
    """Select the confirmed fixture track before exercising real naming and action paths."""
    robot.focus.focus = next(t for t, (_, b) in robot.view[1].items() if b == box)


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
        assert robot.things.named("cup", ["cup"])["labels"] == ["bag", "cup", "mug"]
        # Robot.reset also clears the old associations.
        robot.tracker, robot.points, robot.focus = Tracker(), {}, None
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
    assert point["named"] == "wallet" and r._shown()[0] is frame
    assert r._shown()[1].boxes[0][4:] == ("wallet", "known")
    assert r.focus.named[next(iter(r.view[1]))].refreshed == r.view_taken
    assert r.jobs.queue[0][0] == "caption"
    assert ask(r, "Forget my wallet")[0].startswith("Done")
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
    r.things.name("wallet", ["phone"], stub_crops([np.full((10, 10, 3), GOLD)]))
    r.named = r.things.labels()
    frame_of(r)
    calls = []
    r.recognition.crops = lambda crops: calls.append(1) or stub_crops(crops)
    for _ in range(3):
        r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()],
               {i: r.focus.epoch(i) for i in r.focus.visible}, r.session_id,
               r.focus.geometry([Track(*t) for t in r.tracker.scored()]), r.recognition.epoch)
    drain_matches(r)
    assert r._shown()[1].boxes[0][4:] == ("wallet", "known")
    [seen] = r.memory.sightings(time.time() + 1)
    newest = frame_of(r)
    r._preview(r.view[0], r.view_taken, [Track(*t) for t in r.tracker.scored()],
               {i: r.focus.epoch(i) for i in r.focus.visible}, r.session_id,
               r.focus.geometry([Track(*t) for t in r.tracker.scored()]), r.recognition.epoch)
    drain_matches(r)
    assert r._shown()[0] is newest
    assert len(calls) == 3, "idle crop queries are bounded to three per second"
    assert r._shown()[1].boxes[0][4:] == ("wallet", "known"), "skipped query preserves display only"
    assert r.memory.sightings(time.time() + 1)[0]["last_seen"] == seen["last_seen"], \
        "cached display does not authorize a new sighting"
    assert seen["named"] == "wallet"
    frame_of(r, BLACK)
    preview(r)
    assert r._shown()[1].boxes[0][4:] == ("wallet", "known")
    assert r.memory.sightings(time.time() + 1)[0]["last_seen"] == seen["last_seen"]
    preview(r)
    assert r._shown()[1].boxes[0][4:] == ("wallet", "known")
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
    r.focus.focus = next(iter(r.view[1]))
    assert ask(r, "This is my phone")[0].startswith("Got it")
    count = r.memory.shard.count(CountRequest())
    assert ask(r, "Ignore phones")[0].startswith("Okay")
    assert not r.focus.names(), "ignore clears stored-class display immediately"
    frame_of(r, label="bag")  # relabeling cannot bypass the stored object's ignored kind
    preview(r)
    assert r.memory.shard.count(CountRequest()) == count
    assert not r.focus.names(), "detector relabeling cannot restore an ignored name"
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


def test_verified_face_frame_and_anonymous_replacement(robot, monkeypatch):
    r = robot
    v = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [v, v], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (v, 100, (500, 100, 600, 200)))
    preview(r)
    newer = frame_of(r, BLACK, people=True)
    frame, screen = r._shown()
    assert frame is source and (500, 100, 600, 200, "Ana", "known") in screen.boxes
    assert not any(b[5] == "person" for b in r.screen[1].boxes)
    assert any(t[2] == "person" for t in r.tracker.scored()), "person tracking stays internal"
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (np.eye(FACE_DIM)[1], 100,
                                                                  (500, 100, 600, 200)))
    preview(r)
    assert r.verified[1] is newer and r._shown()[0] is newer
    assert r.verified[3][1][4:] == ("", "other"), "unidentified face stays anonymous"
    assert not any(b[5] == "person" for b in r._shown()[1].boxes)
    assert r._forget(None, "Ana", v) and r.verified is None


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
        return vector, 100, (500, 100, 600, 200)
    def crop(*args):
        crop_entered.set()
        assert crop_release.wait(2)
        return {}, {}
    monkeypatch.setattr(main, "located_face", located)
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
    monkeypatch.setattr(main, "located_face", lambda *a: (vector, 100, (500, 100, 600, 200)))
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
    monkeypatch.setattr(main, "located_face", lambda *a: (vector, 100, (500, 100, 600, 200)))
    preview(r)
    frame, screen = r._shown()
    assert frame is source and any(b[4] == "Ana" for b in screen.boxes)
    if invalid == "negative":
        frame_of(r, BLACK, people=True)
        monkeypatch.setattr(main, "located_face", lambda *a: None)
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
    monkeypatch.setattr(main, "located_face", lambda *a: (np.eye(FACE_DIM)[0], 100,
                       (500, 100, 600, 200)) if detected else None)
    frame_of(r, people=False)
    r._preview(source, job[1], weak, *job[3:])
    assert r.verified is None


def test_fresh_two_person_ambiguity_replaces_known_completion(robot, monkeypatch):
    r = robot
    vector = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [vector, vector], time.time())
    source = frame_of(r, people=True)
    monkeypatch.setattr(main, "located_face", lambda *a: (vector, 100, (500, 100, 600, 200)))
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
    monkeypatch.setattr(main, "located_face", lambda *a: (vectors[0], 100, (500, 100, 600, 200)))
    preview(r)
    _, screen = r._shown()
    assert screen.valid() and r.shown_known
    monkeypatch.setattr(main, "located_face", lambda *a: (vectors[1], 100, (500, 100, 600, 200)))
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
    r.things.name("Chosen", ["phone"], stub_crops([np.full((4, 4, 3), GOLD)]))
    r.named = r.things.labels()
    taken = r.view_taken + 1.2
    monkeypatch.setattr(main.time, "time", lambda: taken)
    frame = r.view[0]
    dets = [Detection("phone", .9, b) for b in (LEFT, CENTER, RIGHT)]
    dets.append(Detection("person", .9, (300, 0, 1000, 720)))
    for _ in range(CONFIRM):
        r._track(frame, dets, taken)
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (v, 100, (500, 100, 600, 200)))
    for _ in range(2):
        r.crop_due.clear()
        preview(r)
    chosen = next(i for i, (_, b) in r.view[1].items() if b == LEFT)
    teaching = next(i for i, (_, b) in r.view[1].items() if b == CENTER)
    assert r.focus.names() == {chosen: ("Chosen", True)} and r.focus.focus == teaching
    verified = r.verified
    assert verified is not None
    for source in [None, verified] * 4:
        r.verified = source
        _, screen = r._shown()
        assert r.focus.focus == teaching, "presentation does not change the selected focus"
        assert [b[:4] for b in screen.boxes if b[5] == "focus"] == [CENTER]
        assert any(b[4] == "Chosen" for b in screen.boxes)
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
    assert r.focus.name(chosen) == "Chosen"
    assert not any(b[4] == "Chosen" for b in r._shown(False)[1].boxes)


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
    assert command("Ignore smartphones", vocab) == ("ignore", "phone", ["phone"])
    assert command("Forget my Dylan's smartphone", vocab)[:2] == ("forget", "Dylan's smartphone")
    assert command("Delete my red coffee mug from your memory", vocab)[:2] == (
        "forget", "red coffee mug")
    from robot.things import Things, question
    assert question("Where is my Dylan's smartphone?", vocab)[:2] == ("where", "Dylan's smartphone")
    assert question("Where is Dylan's smartphone?", vocab)[:2] == ("where", "Dylan's smartphone")
    assert question("What's my cat's name?", vocab) is None
    things = Things(tmp_path)
    vectors = stub_crops([np.full((10, 10, 3), GOLD)])
    things.name("Dylan's smartphone", ["phone"], vectors)
    things.link("DYLAN'S SMARTPHONE", 17)
    things.name("red coffee mug", ["cup", "mug"], vectors)
    things.name("Ana's smartphone", ["phone"], vectors)
    asked = question("Where is Dylan's smartphone?", vocab)
    assert things.named(asked[1], asked[2])["name"] == "Dylan's smartphone"
    assert things.named("phone", ["phone"])["name"] == "Dylan's smartphone"
    assert things.named("RED COFFEE MUG", [])["name"] == "red coffee mug"
    assert things.score(vectors[0], "DYLAN'S SMARTPHONE")[0] == "Dylan's smartphone"
    things.shard.close()
    things = Things(tmp_path)
    assert things.named("dylan's smartphone", [])["turns"] == [17]
    things.name("Dylan's Smartphone", ["phone"], vectors)
    assert things.named("DYLAN'S SMARTPHONE", [])["name"] == "Dylan's smartphone"
    assert things.forget("dylan's smartphone") == [17]
    assert things.named("dylan's smartphone", []) is None
    assert things.named("phone", ["phone"])["name"] == "Ana's smartphone"
    assert things.named("red coffee mug", [])["name"] == "red coffee mug"
    things.shard.close()


def test_case_only_reteach_and_forget_all_evidence(robot):
    r = robot
    frame_of(r)
    r.focus.focus = next(iter(r.view[1]))
    assert ask(r, "This is Dylan's smartphone")[0].startswith("Got it")
    answer, turn = ask(r, "Track this as my DYLAN'S SMARTPHONE")
    assert "Dylan's smartphone" in answer and turn.named == "Dylan's smartphone"
    assert r.focus.names() == {next(iter(r.view[1])): ("Dylan's smartphone", True)}
    assert r.memory.points(turn.memories)[0]["named"] == "Dylan's smartphone"
    assert ask(r, "Forget my DYLAN'S SMARTPHONE")[0].startswith("Done")
    assert r.memory.shard.count(CountRequest()) == 0
    assert not r.focus.names() and not list(r.memory.frames.iterdir())


def test_diverse_reteaching_exact_name_replacement_links_and_ignore(tmp_path):
    basis = np.eye(DIM, dtype=np.float32)
    original = basis[:3]
    current = np.asarray([.9 * basis[0] + np.sqrt(1 - .9**2) * basis[3], basis[4], basis[5]],
                         dtype=np.float32)
    things = Things(tmp_path)
    things.name("Chosen", ["phone"], original)
    things.link("chosen", 17)
    things.name("CHOSEN", ["wallet"], current)
    things.link("chosen", 19)
    saved = things.descriptors("Chosen")
    assert len(saved) == VIEWS
    np.testing.assert_array_equal(saved[:2], [original[0], current[0]])
    assert things.named("chosen", []) == {
        "name": "Chosen", "labels": ["phone", "wallet"], "turns": [17, 19]}
    # Equal cosine distances choose the first remaining input deterministically.
    np.testing.assert_array_equal(diverse(basis[:8], 6), basis[[0, 6, 1]])
    next_views = basis[[0, 6, 7]]
    expected = diverse(np.concatenate([saved, next_views]), len(saved))
    things.name("chosen", ["phone"], next_views)
    np.testing.assert_array_equal(things.descriptors("Chosen"), expected)
    assert len(expected) == VIEWS
    things.name("Separate", ["phone"], basis[[12, 12, 12]])
    assert len(things.descriptors("Separate")) == 1
    np.testing.assert_array_equal(things.descriptors("Chosen"), expected)
    things.shard.close()
    things = Things(tmp_path)
    np.testing.assert_array_equal(things.descriptors("chosen"), expected)
    ident = things.ignore_item("Chosen", expected)
    assert all(things.excluded(vector) == ident for vector in expected)
    assert things.excluded(basis[30]) is None and things.score(basis[12])[0] == "Separate"
    things.shard.close()
    things = Things(tmp_path)
    assert all(things.excluded(vector) == ident for vector in expected)
    assert things.restore_item(ident) and all(things.excluded(v) is None for v in expected)
    # A mismatching current crop rejects both the old gallery and buffered old-looking crops.
    replacement = basis[[30, 0, 31]]
    things.name("CHOSEN", ["bag"], replacement)
    np.testing.assert_array_equal(things.descriptors("Chosen"), replacement[:1])
    assert things.score(basis[0], "Chosen")[1] < main.MATCH
    assert things.named("chosen", [])["labels"] == ["bag", "phone", "wallet"]
    assert things.forget("chosen") == [17, 19] and things.named("chosen", []) is None
    assert things.named("Separate", []) and not things.preferences()
    things.shard.close()


@pytest.mark.parametrize("blocked", [None, "duplicate", "pending", "stale", "category", "weak",
                                     "small", "ignored"])
def test_exact_name_reteach_without_held_or_unknown_focus(robot, blocked):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is Dylan's smartphone")[0].startswith("Got it")
    frame_of(r)
    r.focus.focus = None
    track = next(iter(r.view[1]))
    if blocked == "duplicate":
        show(r, [(GOLD, CENTER), (GOLD, LEFT)])
        r.focus.bind(next(t for t in r.focus.visible if t != track), "Dylan's smartphone")
        r.focus.focus = None
    elif blocked == "pending":
        r.focus.checking.add(track)
    elif blocked == "stale":
        r.focus.named[track].refreshed -= main.PREVIEW_TTL + 1
    elif blocked == "weak":
        tracks = [Track(*t) for t in r.tracker.scored()]
        r.focus.update(r.view_taken, tracks, [], recognized={track: ("Dylan's smartphone", .797)})
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
        assert answer.startswith("Got it") and turn.named == "Dylan's smartphone"
        assert len(r.things.named(name, [])["turns"]) == 2


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
        assert r.focus.name(track) == "phone"
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
    r.things.name("B", ["wallet" if competitor == "ignored-kind" else "phone"], other[None])
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
    assert calls == ["A", None] and crops == [1]
    if competitor == "strong":
        assert not r.focus.names(), "the first conflicting strong result abstains"
        assert not r._shown(False)[1].control["targets"], "no accepted named action during conflict"
    elif competitor == "hidden":
        assert track in r.focus.excluded and not r.focus.names()
    else:
        assert r.focus.names() == {track: ("A", True)}, "ineligible hits keep weak continuity"
    preview(r, clear=False)
    if competitor == "strong":
        assert r.focus.names() == {track: ("B", True)}, "the second agreeing query confirms B"
    preview(r, clear=False)
    assert crops == [1, 1, 1] and len(r.crop_times) == 3
    expected = {"strong": ["A", None, None, "B"], "hidden": ["A", None, None, None]}
    assert calls == expected.get(competitor, ["A", None] * 3)
    previous_calls = list(calls)
    preview(r, clear=False)
    assert calls == previous_calls and crops == [1, 1, 1], "the crop budget bounds fallback queries"
    if competitor == "strong":
        assert r.focus.names() == {track: ("B", True)}
        assert r.memory.sightings(time.time() + 1)[0]["named"] == "B"
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
    r.things.name("B", ["phone"], vector[None])
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
    assert calls == ["A", None]
    assert r.focus.name(track) != "B" and not r.matches_pending
    assert r.memory.shard.count(CountRequest()) == before
    assert all(row.get("named") != "B" for row in r.memory.sightings(time.time() + 1))


def test_robot_reteach_replacement_discards_buffered_previous_physical_object(robot, monkeypatch):
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
    np.testing.assert_array_equal(r.things.descriptors("phone"), stub_crops([
        np.full((4, 4, 3), BLACK)]))
    assert r.things.score(stub_crops([np.full((4, 4, 3), GOLD)])[0], "phone")[1] < main.MATCH
    assert len(r.things.named("phone", [])["turns"]) == 2
    assert ask(r, "Forget my phone")[0].startswith("Done")
    assert r.memory.shard.count(CountRequest()) == 0 and not list(r.memory.frames.iterdir())


def test_robot_ignore_copies_all_verified_gallery_views_and_forget_deletes_links(robot):
    r = robot
    frame_of(r)
    hold(r, CENTER)
    assert ask(r, "This is my phone")[0].startswith("Got it")
    basis = np.eye(DIM, dtype=np.float32)
    for indices in ([GOLD, 11, 12], [GOLD, 13, 14], [GOLD, 15, 16]):
        r.recognition.call(lambda f, c, indices=indices: r.things.name("phone", ["phone"],
                                                                    basis[indices]),
                           mutate=True)
    saved = r.things.descriptors("phone")
    assert len(saved) == VIEWS
    preview(r)
    state = r._shown(False)[1].control
    [target] = state["targets"]
    assert r._item_control("ignore", {**state, **target}).startswith("Okay")
    assert all(r.things.excluded(v) for v in saved), "actual current-crop action copies every view"
    [preference] = r.things.preferences()
    assert r._item_control("restore", {"id": preference["id"], "session": r.session_id,
                                       "gallery": r.recognition.epoch}).startswith("I will notice")
    assert all(r.things.excluded(v) is None for v in saved)
    assert ask(r, "Forget my phone")[0].startswith("Done")
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
    assert r.things.named("phone", []) is None and r.memory.shard.count(CountRequest()) == 0
    assert not list(r.memory.frames.iterdir())


def test_chosen_name_reverified_after_display_expiry_and_wrong_instance(robot, monkeypatch):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    ask(r, "This is my phone")
    ask(r, "Track this as my Dylan's smartphone")
    crop = r.recognition.crops([main.cut(r.view[0], r.view[1][track][1])])[0]
    assert r.things.score(crop)[0] == "phone", "the old identical alias wins unrestricted search"
    calls = []
    score = r.things.score
    monkeypatch.setattr(r.things, "score",
                        lambda v, name=None: calls.append(name) or score(v, name))
    preview(r)
    assert r.focus.names() == {track: ("Dylan's smartphone", True)}
    original = time.time()
    monkeypatch.setattr(main.time, "time", lambda: original + 3)
    newest = frame_of(r)
    assert r._shown()[0] is newest and r.focus.names(), "continuous names survive skipped work"
    assert r.focus.name(track) == "Dylan's smartphone", "continuous track keeps a query preference"
    preview(r)
    assert r.focus.names() == {track: ("Dylan's smartphone", True)}
    assert calls == ["Dylan's smartphone", "Dylan's smartphone"]
    # A different instance on an uninterrupted ID must escape the preference after real misses.
    frame_of(r, BLACK)
    preview(r)
    assert r.focus.names() == {track: ("Dylan's smartphone", True)}
    preview(r)
    preview(r)
    assert r.focus.name(track) is None
    preview(r)
    assert calls[-7:] == ["Dylan's smartphone", None] * 3 + [None]
    # A gap clears the accepted preference even when the tracker later reuses the ID.
    r.focus.bind(track, "Dylan's smartphone", r.view_taken)
    r._track(r.view[0], [], r.view_taken + .21)
    assert r.focus.name(track) is None
    frame_of(r)
    preview(r)
    assert calls[-1] is None
    r.focus.bind(next(iter(r.view[1])), "Dylan's smartphone", r.view_taken)
    ask(r, "Forget my Dylan's smartphone")
    assert not r.focus.names()
    assert all(n.name != "Dylan's smartphone" for n in r.focus.named.values())


def test_face_gap_during_generation_rejects_old_preview(robot, monkeypatch):
    r = robot
    v = np.eye(FACE_DIM, dtype=np.float32)[0]
    r.people.enroll("Ana", [v, v], time.time())
    source = frame_of(r, people=True)
    source_time, epoch = r.view_taken, r.recognition.epoch
    tracks = [Track(*t) for t in r.tracker.scored()]
    epochs = {i: r.focus.epoch(i) for i in r.focus.visible}
    monkeypatch.setattr(main, "located_face", lambda faces, frame: (v, 100, (500, 100, 600, 200)))
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
    monkeypatch.setattr(main, "face", lambda f, image: None)
    monkeypatch.setattr(main, "located_face", lambda f, image: None)
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
        assert r.things.hidden_names() == {"phone", "Dylan's smartphone"}
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
        assert ask(r, "Forget my Dylan's smartphone")[0].startswith("Done")
        assert r.things.preferences(), "named deletion preserves independent item preference"
    finally:
        close_robot(r)
    fresh = open_robot(tmp_path)
    try:
        frame_of(fresh)
        assert not fresh._shown()[1].boxes, "return waits for persisted preference qualification"
        assert fresh.focus.checking and not fresh.focus.excluded
        assert fresh._sighted(Turn(question="Where is the phone?",
                                  speech_start=time.time() + 1)) is None
        preview(fresh)
        assert fresh.focus.excluded and not fresh._shown()[1].boxes
        ident = fresh.things.preferences()[0]["id"]
        assert fresh._item_control("restore", {"session": fresh.session_id,
            "gallery": fresh.recognition.epoch, "id": ident}).startswith("I will notice")
        assert fresh.things.preferences() == [] and not fresh.focus.excluded
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
    assert r._control("ignore", {**data, "session": "old"}) is False
    assert r._control("ignore", data)
    r._track(r.view[0], [], r.view_taken + .01)
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


def test_unrelated_ignore_short_dropout_preserves_chosen_name_with_full_budget(robot, monkeypatch):
    r = robot
    frame_of(r)
    track = next(iter(r.view[1]))
    r.focus.focus = track
    ask(r, "This is my phone")
    ask(r, "Track this as my Dylan's smartphone")
    r.things.ignore_item("Other phone", stub_crops([np.full((4, 4, 3), BLACK)]))
    preview(r)
    assert r.things.score(stub_crops([np.full((4, 4, 3), GOLD)])[0])[0] == "phone"
    old_epoch, source = r.focus.epoch(track), r.view_taken
    r.crop_times.extend([time.monotonic()] * (3 - len(r.crop_times)))
    before = r.memory.sightings(time.time() + 1)
    r._track(r.view[0], [], source + .05)
    assert any(b[4] == "Dylan's smartphone" for b in r.focus.boxes([], [], source + .05))
    monkeypatch.setattr(main.time, "time", lambda: source + .10)
    moved = tuple(v + (20 if i % 2 == 0 else 0) for i, v in enumerate(CENTER))
    frame_of(r, box=moved)
    assert track in r.focus.checking and r.focus.epoch(track) > old_epoch
    preview(r, clear=False)
    monkeypatch.setattr(main.time, "time", lambda: source + .15)
    frame_of(r, box=moved)
    assert r.focus.name(track) == "Dylan's smartphone"
    assert r.focus.seen[track].shown != moved, "pending checks preserve box smoothing"
    assert any(b[4] == "Dylan's smartphone" for b in r._shown()[1].boxes)
    assert not r._shown(False)[1].control["targets"], "cached display cannot authorize actions"
    assert r.memory.sightings(source + 1) == before, "no query means no new sighting writes"
    preview(r)
    assert track not in r.focus.checking
    assert r.focus.names() == {track: ("Dylan's smartphone", True)}


def test_named_confidence_dip_reverifies_but_unknown_stays_hidden(robot, monkeypatch):
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
    assert r.focus.name(chosen) == "Dylan's smartphone"
    assert r.focus.seen[chosen].shown != moved, "the confidence dip preserves smoothing"
    assert r.focus.names() == {chosen: ("Dylan's smartphone", True)}
    assert not r.focus.eligible(Track(*next(t for t in r.tracker.scored() if t[0] == other)))
    assert [b[4] for b in r._shown()[1].boxes] == ["Dylan's smartphone"]
    r.crop_due.clear()
    preview(r)
    assert calls == ["Dylan's smartphone"], "a low-confidence chosen track still gets a crop query"
    assert r.focus.names() == {chosen: ("Dylan's smartphone", True)}
    frame[300:600, 560:760] = BLACK
    r._track(frame, dets)
    preview(r)
    assert calls[-2:] == ["Dylan's smartphone", None]
    assert not r.focus.names(), "two weak current signals hide the retained association"
    assert not r._shown()[1].boxes
    assert not r._shown(False)[1].control["targets"], \
        "retained labels cannot authorize low-confidence actions"
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
    assert r.focus.name(track) == "chosen item"
    assert not r._shown()[1].boxes and not r._shown(False)[1].control["targets"]
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
    assert r.focus.names() == {track: ("chosen item", True)}
    preview(r, clear=False)  # Complete regrown face/source geometry without a spare crop query.
    assert r._shown()[1].boxes[0][4:] == ("chosen item", "known")
    assert not calls, "regrowth restores display without a fresh query or write"
    assert r.memory.sightings(source + 1) == before


def test_detector_frames_admit_without_second_timer_and_preserve_bounded_owner(robot, monkeypatch):
    from robot.recognition import Recognition
    r = robot
    r.things.name("Chosen", ["phone"], stub_crops([np.full((4, 4, 3), GOLD)]))
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
    r.things.name("Chosen", ["phone"], stub_crops([np.full((4, 4, 3), GOLD)]))
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
    assert any(b[4] == "Chosen" for b in r._shown()[1].boxes)


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
        r.things.name("Other", ["phone"], stub_crops([np.full((4, 4, 3), BLACK)]))
        r.named = r.things.labels()
        r.focus.bind(other, "Other")
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
    r.things.name("Chosen", ["phone"], stub_crops([np.full((4, 4, 3), GOLD)]))
    r.named = r.things.labels()
    tracks = list(r.focus.visible)
    for track in tracks:
        r.focus.bind(track, "Chosen")
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
    saved = r.things.descriptors("wallet").copy()
    # The new physical object retains the same track and normal detector confidence.
    frame_of(r, BLACK)
    preview(r)
    assert r.focus.named[track].score == 0
    assert r.focus.names() == {track: ("wallet", True)}
    state = r._shown(False)[1].control
    data = {**state, **next(t for t in state["targets"] if t["track"] == track)}
    assert r._valid_item(data), "the display selection alone is not a fresh identity match"
    calls = []
    r.recognition.crops = lambda shots: calls.append(shots[0].copy()) or stub_crops(shots)
    gallery = r.recognition.epoch
    assert r._item_control("ignore", data).startswith("That selection expired")
    assert len(calls) == 1 and calls[0].mean() == BLACK
    assert r.recognition.epoch == gallery and not r.things.preferences()
    assert not r.focus.excluded and not r.things.hidden_names()
    np.testing.assert_array_equal(r.things.descriptors("wallet"), saved)
    assert r.memory.points(turn.memories)[0]["named"] == "wallet"
    assert ask(r, "Forget my wallet")[0].startswith("Done")
    assert not r.memory.points(turn.memories)
    assert r.things.named("wallet", []) is None


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
    preview(r)
    assert not r.focus.excluded and r.focus.seen[track].exclude_misses == 0
    assert r._shown()[1].boxes, 'a distinct merged object needs its own strong Ignore match'
