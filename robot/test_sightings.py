"""Fresh named-track sightings and recall use real Tracker and Edge; unknown tracks stay in RAM."""
import tempfile
from pathlib import Path

import numpy as np

from robot import main, memory
from robot.detect import CONFIRM, LOST, MAX_MISSED, Detection, Tracker
from robot.focus import Track
from robot.main import Robot, Turn
from robot.test_things import close_robot, open_robot
from robot.test_things import thumbnail_crops, object_id
from robot.things import DIM



def fresh_sightings(robot, frame, now):
    """Supply explicit fixture names and fresh model results through the real write route."""
    tracks = [Track(*row) for row in robot.tracker.scored()]
    recognized = {}
    for track in tracks:
        assert robot.focus.eligible(track)
        name = f"{track.label} {track.id}"
        if robot.things.named(robot.conversation_visitor, name, []) is None:
            robot.things.name(
                robot.conversation_visitor,
                name,
                [track.label],
                np.eye(DIM, dtype=np.float32)[[track.id]],
                thumbnail_crops(np.eye(DIM, dtype=np.float32)[[track.id]]),
            )
        recognized[track.id] = object_id(robot.things, robot.conversation_visitor, name), .99
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
    """Robot._turn on real Edge with a stub brain: a past question about something shown is
    answered in code from the caption of the look it selects (made on demand once, then
    ready), never another look's; a comparison gets that caption as one Memories line beside
    the present image; a failed caption is an explicit unavailable answer; a present question
    selects nothing; the looks and their pending captions follow the window and every
    deletion."""
    import queue
    import time
    from types import SimpleNamespace as Stub

    from robot import brain
    from robot.memory import UNAVAILABLE
    from robot.text_embed import DIM as TEXT_DIM

    monkeypatch.setattr(main, "face", lambda faces, frame: None)
    robot = open_robot(tmp_path)
    robot.asking, robot.stream, robot.wake_word, robot.turns = None, None, False, queue.Queue()
    robot.ready, robot.last_frame, robot.exchanges, robot.detections = None, None, 0, 0
    robot.out = tmp_path / "out"
    robot.out.mkdir()
    robot.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[[0] * len(texts)]
    robot.knowledge, robot.route = Stub(search=lambda q: []), lambda q: "sight"
    shot = lambda k: np.full((720, 1280, 3), k, np.uint8)  # noqa: E731
    url = lambda image: image["image_url"]["url"]  # noqa: E731
    things = {url(brain.jpeg(shot(k))): name for k, name in
              ((200, "a stop sign"), (100, "a clock"), (0, "an empty room"))}
    sent: list = []  # the prompts the brain answered
    captioned: list[str] = []  # the things it captioned, in order
    broken = []  # a non-empty list makes captioning fail

    def answer(msgs, **kwargs):
        sent.append(msgs)
        yield "Ok."

    def caption(image, stop):
        captioned.append(things[url(image)])
        return None if broken else f"Main object: {things[url(image)]}. Around it: a wall."

    robot.brain = Stub(prefill=lambda m: None, answer=answer, caption=caption)
    robot.voice = Stub(say=lambda text: np.zeros(160, np.float32))
    robot.speaker = Stub(play=lambda pcm: None)
    clock = iter(range(int(time.time()), int(time.time()) + 10_000))

    def ask(text: str, view: int) -> main.Turn:
        t = float(next(clock))
        turn = main.Turn(question=text, speech_start=t, line=t, speech_end=t)
        robot._turn(turn, (shot(view), t))
        return turn

    stop, clock_view, night = 200, 100, 0
    first = ask("What is this?", stop)
    ask("And what is this?", clock_view)
    spoken = len(sent)
    assert captioned == [], "the answers need no caption"
    turn = ask("What did I just show you?", night)
    assert turn.answer.startswith("You showed me a clock, ") and turn.verbatim
    assert (turn.caption, captioned) == ("demand", ["a clock"]), "made now, for this look only"
    assert turn.delivered
    assert turn.selected == robot.looked[1].taken and len(sent) == spoken, "code, not the brain"
    turn = ask("Which thing did I show you a moment ago?", night)
    assert turn.answer.startswith("You showed me a clock") and turn.caption == "ready"
    assert captioned == ["a clock"], "ready: not captioned again"
    turn = ask("What was the first thing I showed you?", night)
    assert turn.answer.startswith("You showed me a stop sign") and turn.selected == first.looked
    assert captioned == ["a clock", "a stop sign"], "each look has its own caption"
    turn = ask("What am I holding now?", clock_view)
    assert turn.selected == 0.0 and turn.caption == "", "a present question selects nothing"
    assert len(robot.looked) == main.HISTORY_TURNS, "the window of the conversation"
    n = len(sent)
    turn = ask("Is this the same as what I showed you before?", night)
    assert len(sent) > n and not turn.verbatim, "the brain answers a comparison"
    prompt = sent[-1][-1]["content"]
    assert prompt[0] == brain.jpeg(shot(night)), "beside the present image"
    assert "Memories:\n- " in prompt[-1]["text"] and "you showed me a clock" in prompt[-1]["text"]
    assert turn.caption == "demand" and turn.selected > 0, "the newest look of another view"
    assert turn.delivered, "its line is in the request the brain answered"
    turn = ask("Was it the same as what I showed you before?", night)
    assert sent[-1][-1]["content"][0] == brain.jpeg(shot(night)), "a comparison sees the present"
    robot.looked = [robot.looked[-1]]  # only the present view remains
    robot.looked[0].caption = None
    turn = ask("Is this the same as what I showed you before?", night)
    assert turn.selected == 0.0, "nothing earlier to compare: no look"
    turn = ask("What did I show you yesterday?", night)
    assert turn.selected == 0.0, "a time the window cannot hold"
    robot.history, robot.looked = [], []
    turn = ask("What did I just show you?", night)
    assert turn.selected == 0.0 and not turn.verbatim, "no earlier exchange: today's path"
    ask("What is this?", stop)
    ask("And this?", clock_view)
    broken.append(1)
    before = list(captioned)
    turn = ask("What did I just show you?", night)
    assert turn.answer == UNAVAILABLE and turn.caption == "failed" and not turn.delivered
    assert captioned == [*before, "a clock"], "no other look's caption was borrowed or tried"
    assert robot.looked[1].caption is None
    # An idle caption is made once per view run, for its newest look, and the foreground comes
    # first: speech or queued work skips it. The prefilled prefix is invalid afterwards.
    del broken[:]
    robot.history, robot.looked = [], []
    ask("What is this?", stop)
    ask("And this?", clock_view)
    ask("And this one?", clock_view)
    a, b, c = robot.looked
    assert robot._undescribed() is a and b.caption is None, "the first view run"
    robot.speaking = True
    robot._describe_idle(a)
    robot.speaking = False
    robot.jobs.put(("look", None))
    robot._describe_idle(a)
    robot.jobs.get()
    assert a.caption is None, "foreground work first"
    robot.ready = a
    robot._describe_idle(a)
    assert a.caption and robot.ready is None, "the next _look prefills again"
    assert robot._undescribed() is c, "the duplicate look of a run is not captioned"
    robot._describe_idle(c)
    made = list(captioned)
    ask("Once more?", clock_view)
    assert robot.looked[-1].caption == c.caption, "an unchanged look shares its run's caption"
    assert robot._undescribed() is None and captioned == made, "no second caption"
    # A caption pending when the conversation ends is dropped by the worker, not made.
    robot.looked[-1].caption = None
    pending = robot._undescribed()
    assert pending is robot.looked[-1]
    # A comparison answered by a fact never sends its Memories line: no delivery credit.
    robot.knowledge = Stub(search=lambda q: [(1.0, "Qdrant is a vector search engine.")])
    turn = ask("Is this the same as what I showed you before?", night)
    assert turn.verbatim and turn.selected > 0 and not turn.delivered
    robot.knowledge = Stub(search=lambda q: [])
    pending.caption = None
    assert robot._forget(None, "Ana", np.zeros(DIM, np.float32), robot.conversation_visitor)
    before = list(captioned)
    robot._describe_idle(pending)
    assert captioned == before and pending.caption is None, "'forget me' drops it"
    assert robot.looked == [], "'forget me': the looks may show the visitor"
    ask("What is this?", stop)
    assert robot.looked == [], "nothing is kept while the forgotten visitor may be in view"
    # The hiding times out with no usable face, but the track stays forgotten: still no look.
    robot.hiding = (np.zeros(DIM, np.float32), time.time() - main.CLEAR_S - 1)
    robot._visitor, robot.visitors = lambda: 7, {7: main.Visitor(forgotten=True)}
    ask("What is this?", stop)
    assert robot.hiding is None and robot.looked == [], "one privacy decision for text and looks"
