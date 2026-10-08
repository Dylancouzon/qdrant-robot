"""Tracks to sighting points and back into a past question's Memories, without models: the
robot's sighting writes and recall on a real Edge shard, fed by the real tracker."""
import tempfile
import threading
from pathlib import Path

import numpy as np

from robot.detect import CONFIRM, MAX_MISSED, Detection, Tracker
from robot.main import Robot, Turn
from robot.memory import Memory


def test_sightings() -> None:
    robot = Robot.__new__(Robot)  # no models: only the memory and the tracker
    with tempfile.TemporaryDirectory() as tmp:
        robot.memory, robot.tracker, robot.points = Memory(Path(tmp)), Tracker(), {}
        robot.detecting = threading.Lock()
        frame = np.zeros((720, 1280, 3), np.uint8)
        clock = Detection("clock", 0.9, (1000, 100, 1200, 300))
        bottle = Detection("bottle", 0.9, (100, 100, 200, 300))

        def step(dets: list[Detection], now: float) -> None:
            if found := robot.tracker.update(dets, 1280, now):
                robot._sight(found, frame)

        for k in range(CONFIRM):
            step([clock, bottle], 10.0 + k)
        [c, b] = robot.memory.sightings(before=99.0)
        assert {(c["label"], c["region"]), (b["label"], b["region"])} == {
            ("clock", "right"), ("bottle", "left")}
        for k in range(MAX_MISSED + 1):  # the clock is taken away; the bottle stays
            step([bottle], 20.0 + k)
        assert len(robot.points) == 1, "a gone track leaves the live map"
        clock_row = next(s for s in robot.memory.sightings(before=99.0) if s["label"] == "clock")
        assert (clock_row["first_seen"], clock_row["last_seen"]) == (12.0, 12.0)
        others = [Detection(f"thing{k}", 0.9, (300 + 150 * k, 400, 400 + 150 * k, 500))
                  for k in range(4)]  # four newer objects, still in view, must not crowd it out
        for k in range(CONFIRM):
            step([bottle, *others], 40.0 + k)
        _, lines = robot._recall(Turn(speech_start=72.0), frame)
        assert lines == ["1. 60 seconds ago: clock on your right"], "the rest is in view now"


def test_detector_failure(monkeypatch) -> None:
    """A failing detector is reloaded DETECT_RESTARTS times, then detection stops and says so."""
    from robot import main

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
