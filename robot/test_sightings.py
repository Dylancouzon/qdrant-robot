"""Fresh named-track sightings and recall use real Tracker and Edge; unknown tracks stay in RAM."""
import tempfile
from pathlib import Path

import numpy as np

from robot import main, memory
from robot.detect import CONFIRM, LOST, MAX_MISSED, Detection, Tracker
from robot.focus import Track
from robot.main import Robot, Turn
from robot.test_things import close_robot, open_robot
from robot.things import DIM



def fresh_sightings(robot, frame, now):
    """Supply explicit fixture names and fresh model results through the real write route."""
    tracks = [Track(*row) for row in robot.tracker.scored()]
    recognized = {}
    for track in tracks:
        assert robot.focus.eligible(track)
        name = f"{track.label} {track.id}"
        if robot.things.named(name, []) is None:
            robot.things.name(name, [track.label], np.eye(DIM, dtype=np.float32)[[track.id]])
        recognized[track.id] = name, .99
    robot.named = robot.things.labels()
    robot.focus.update(now, tracks, [], recognized=recognized, recognized_at=now)
    robot._remember_matches(frame, now, tracks, recognized, None)

def test_sightings(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        frame = np.zeros((720, 1280, 3), np.uint8)
        clock = Detection("clock", 0.9, (1000, 100, 1200, 300))
        bottle = Detection("bottle", 0.9, (100, 100, 240, 300))

        def step(dets: list[Detection], now: float, selected=True) -> None:
            monkeypatch.setattr(main.time, "time", lambda: now)
            robot._sight(robot._track(frame, dets, now))
            if selected:
                fresh_sightings(robot, frame, now)

        for k in range(CONFIRM):
            step([clock, bottle], 10.0 + k, selected=False)
        assert robot.memory.sightings(before=99) == [] and not robot.points
        assert not list(robot.memory.frames.iterdir()), "unknown repeated tracks save no images"
        fresh_sightings(robot, frame, 12.0)
        [c, b] = robot.memory.sightings(before=99.0)
        assert {(c["label"], c["region"]), (b["label"], b["region"])} == {
            ("clock", "right"), ("bottle", "left")}
        for k in range(LOST + 1):  # the clock is taken away and ends; the bottle stays
            step([bottle], 20.0 + k)
        assert len(robot.points) == 1, "a gone track leaves the live map"
        clock_row = next(s for s in robot.memory.sightings(before=99.0) if s["label"] == "clock")
        assert (clock_row["first_seen"], clock_row["last_seen"]) == (12.0, 12.0)
        others = [Detection(f"thing{k}", 0.9, (300 + 150 * k, 400, 440 + 150 * k, 550))
                  for k in range(4)]  # four newer objects, still in view, must not crowd it out
        for k in range(CONFIRM):
            step([bottle, *others], 40.0 + k)
        _, lines = robot._recall(Turn(speech_start=72.0), frame)
        assert lines == ["60 seconds ago: you saw a clock; it is not in view now"], \
            "the rest is in view now; no sides (D61)"
        robot.vocab, robot.history = {"clock", "bottle", "thing0"}, []
        turn = Turn(question="Did the clock leave, or is it still around?", speech_start=72.0)
        assert robot._sighted(turn) == "I saw a clock on my right, 60 seconds ago; " \
            "I do not see it now." and turn.memories == [clock_row["id"]]
        turn = Turn(question="Can you see a bottle anywhere now?", speech_start=72.0)
        assert robot._sighted(turn) is None, "a question about now goes to the brain"
        turn = Turn(question="Have you ever spotted a bottle?", speech_start=72.0)
        assert robot._sighted(turn) == "I see a bottle on my left now.", "in view: Edge ids"
        assert robot._sighted(Turn(question="What is the capital of Peru?")) is None
        moved = Detection("bottle", 0.9, (1000, 400, 1140, 600))  # jumps right: a new track
        for k in range(LOST + 1):
            step([moved, *others], 80.0 + k)
        turn = Turn(question="Earlier, what did you spot on your left side?", speech_start=99.0)
        assert robot._sighted(turn) == "I saw a bottle on my left, 57 seconds ago. I see a " \
            "bottle on my right now; I cannot tell if it is the same one.", turn.answer
        close_robot(robot)


def test_return_and_turnover(monkeypatch) -> None:
    """A cup that leaves and comes back is in view again; cups coming and going on the other
    side never push the point count over the cap, and never evict the cup in view."""
    monkeypatch.setattr(memory, "MAX_POINTS", 3)
    with tempfile.TemporaryDirectory() as tmp:
        robot = open_robot(Path(tmp))
        robot.vocab, robot.history = {"cup"}, []
        clock = iter(range(10_000))
        frame = np.zeros((720, 1280, 3), np.uint8)

        def step(dets: list[Detection], selected=True) -> None:
            now = float(next(clock))
            monkeypatch.setattr(main.time, "time", lambda: now)
            robot._sight(robot._track(frame, dets, now))
            if selected:
                fresh_sightings(robot, frame, now)
            assert robot.memory.shard.count(memory.CountRequest()) <= memory.MAX_POINTS

        cup = Detection("cup", 0.9, (100, 100, 240, 250))
        for _ in range(CONFIRM):
            step([cup], selected=False)
        assert not robot.points and robot.memory.shard.count(memory.CountRequest()) == 0
        assert not list(robot.memory.frames.iterdir())
        step([cup])
        for _ in range(MAX_MISSED + 1):  # taken away: gone
            step([])
        back = Detection("cup", 0.9, (150, 130, 290, 280))  # put back nearby: the same track
        for _ in range(CONFIRM):
            step([back])
        [pid] = robot.points.values()
        turn = Turn(question="Is the cup still there?", speech_start=float(next(clock)))
        assert robot._sighted(turn) == "I see a cup on my left now.", turn.answer
        for k in range(6):  # other cups come and go on the right while earlier ones are gone
            x, y = 860 + 200 * (k % 2), 50 + 220 * (k // 2)  # apart: none continues another
            for _ in range(CONFIRM):
                step([back, Detection("cup", 0.9, (x, y, x + 140, y + 150))])
            for _ in range(MAX_MISSED + 1):
                step([back])
        for _ in range(LOST):
            step([back])
        assert robot.memory.points([pid]) and robot.points[1] == pid, "the cup in view stays"
        close_robot(robot)


def test_detector_failure(monkeypatch) -> None:
    """A failing detector is reloaded DETECT_RESTARTS times, then detection stops and says so."""
    import threading

    loads = []

    class Broken:
        def __init__(self):
            loads.append(1)

        def __call__(self, frame):
            raise RuntimeError("CUDA error 700")

        def close(self):
            pass

    monkeypatch.setattr(main, "Detector", Broken)
    monkeypatch.setattr(main, "DETECT_FPS", 1000)
    robot = Robot.__new__(Robot)
    robot.camera = type("Cam", (), {"latest": lambda self: (np.zeros((9, 9, 3), np.uint8), 0)})()
    robot.detect, robot.tracker, robot.detecting = Broken(), Tracker(), threading.Lock()
    robot.closing, robot.detect_failed = threading.Event(), None
    robot._detect()  # returns once detection stops
    assert isinstance(robot.detect_failed, RuntimeError) and robot.detect is None
    assert len(loads) == 1 + main.DETECT_RESTARTS, "the first load plus one per restart"
    turn = main.Turn(question="What was on your left?")
    assert robot._sighted(turn) is None, "no sighting answer once detection has stopped"
