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


def test_earlier_frame(monkeypatch, tmp_path) -> None:
    """Robot._turn on real Edge with a stub brain: a past question about something shown gets
    the frame the robot looked at then, labeled as earlier; a present question never does;
    the retained frames follow the conversation window and every deletion."""
    import queue
    import time
    from types import SimpleNamespace as Stub

    from robot import brain
    from robot.text_embed import DIM as TEXT_DIM

    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    robot = open_robot(tmp_path)
    robot.asking, robot.stream, robot.wake_word, robot.turns = None, None, False, queue.Queue()
    robot.ready, robot.last_frame, robot.exchanges, robot.detections = None, None, 0, 0
    robot.out = tmp_path / "out"
    robot.out.mkdir()
    robot.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[[0] * len(texts)]
    robot.knowledge, robot.route = Stub(search=lambda q: []), lambda q: "sight"
    sent: list = []
    def answer(msgs, **kwargs):
        sent.append(msgs)
        yield "Ok."

    robot.brain = Stub(prefill=lambda m: None, answer=answer)
    robot.voice = Stub(say=lambda text: np.zeros(160, np.float32))
    robot.speaker = Stub(play=lambda pcm: None)
    shot = lambda k: np.full((720, 1280, 3), k, np.uint8)  # noqa: E731
    clock = iter(range(int(time.time()), int(time.time()) + 10_000))

    def ask(text: str, view: int) -> dict:
        """The turn and the content of the last user message the brain got."""
        t = float(next(clock))
        turn = main.Turn(question=text, speech_start=t, line=t, speech_end=t)
        robot._turn(turn, (shot(view), t))
        last = sent[-1][-1]["content"]
        return turn, last

    def image(content, view: int) -> bool:
        return content[0] == brain.jpeg(shot(view))

    stop, clock_view, night = 200, 100, 0
    turn, content = ask("What is this?", stop)
    assert image(content, stop) and turn.supplied == 0.0, "a present question: the present frame"
    first = turn.looked
    ask("And what is this?", clock_view)
    turn, content = ask("What did I just show you?", night)
    assert image(content, clock_view) and turn.supplied > 0
    assert "not the present" in content[-1]["text"]
    assert turn.supplied != first, "the newest differing frame, not the first"
    turn, content = ask("What was the first thing I showed you?", night)
    assert image(content, stop) and turn.supplied == first
    turn, content = ask("What am I holding now?", clock_view)
    assert image(content, clock_view) and turn.supplied == 0.0 and "not the present" not in \
        content[-1]["text"], "never an earlier frame for the present"
    assert len(robot.looked) == main.HISTORY_TURNS, "the window of the conversation"
    robot.looked = [robot.looked[-1]]  # only the present view remains: nothing differs
    turn, content = ask("What did I show you?", clock_view)
    assert image(content, clock_view) and turn.supplied == robot.looked[0].taken, \
        "an unchanged view: the present image, scored against the earlier look of that view"
    assert "not the present" not in content[-1]["text"]
    turn, content = ask("What did I show you yesterday?", night)
    assert len(content) == 1 and turn.supplied == 0.0, "a time the window cannot hold"
    robot.history, robot.looked = [], []
    turn, content = ask("What did I just show you?", night)
    assert len(content) == 1 and turn.supplied == 0.0, "no earlier exchange: no image"
    ask("What is this?", stop)
    assert len(robot.looked) == 2
    assert robot._forget(None, "Ana", np.zeros(DIM, np.float32))
    assert robot.looked == [], "'forget me': the frames may show the visitor"
    ask("What is this?", stop)
    assert robot.looked == [], "nothing is kept while the forgotten visitor may be in view"
    # The hiding times out with no usable face, but the track stays forgotten: still no frame.
    robot.hiding = (np.zeros(DIM, np.float32), time.time() - main.CLEAR_S - 1)
    robot._visitor, robot.visitors = lambda: 7, {7: main.Visitor(forgotten=True)}
    ask("What is this?", stop)
    assert robot.hiding is None and robot.looked == [], "one privacy decision for text and frames"
