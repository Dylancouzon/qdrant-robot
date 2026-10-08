"""Step dispatch of eval/replay.py without models: a fake robot that remembers every turn in its
memory folder, so a restart that kept the folder still finds the turns from before it."""
import queue
import time
from pathlib import Path

from eval import replay
from robot.main import Turn

STORED: dict[Path, list[int]] = {}  # memory folder -> frame ids, survives a restart


class FakeRobot:
    def __init__(self, memory: Path, log: list):
        self.memory, self.log, self.asked, self.turns = memory, log, 0, queue.Queue()
        self.camera = self
        log.append(("start", memory))

    def show(self, path: Path) -> None:
        self.log.append(("show", path.name))

    def reset(self, memory: Path) -> None:
        self.memory = memory

    def ask(self, text: str) -> None:
        frames = STORED.setdefault(self.memory, [])
        frames.append(len(frames) + 1)
        self.asked += 1
        self.turns.put(Turn(question=text, answer=text, frame_id=frames[-1], memories=frames[:-1]))

    def close(self) -> None:
        self.log.append(("close", self.memory))


def test_steps(monkeypatch) -> None:
    monkeypatch.setattr(replay, "REACT_S", 0)
    log: list = []
    say = {"expect_any": ["umbrella"]}
    steps = [{"show": "a.jpg"}, {"id": "s1", "say": "is this an umbrella?", **say}, {"wait": 0.2},
             {"restart": True},
             {"id": "s2", "say": "where is the umbrella?", **say, "evidence": ["s1"]}]
    t = time.time()
    rows = replay.run([{"steps": steps}], lambda m: FakeRobot(m, log), Path("eval/dev/x"),
                      oracle=True, audio="audio")
    assert time.time() - t >= 0.2  # the wait step held the frame with no speech
    assert [r["id"] for r in rows] == ["s1", "s2"] and all(r["ok"] for r in rows)
    assert rows[1]["evidence_ok"] is True  # the turn before the restart is still recalled
    memory = log[2][1]  # the session's folder, set by reset
    assert log[1:] == [("show", "a.jpg"), ("close", memory), ("start", memory),
                       ("close", memory)]


def test_statement_evidence() -> None:
    frames: dict[str, tuple] = {}
    said = Turn(question="My name is Priya.", answer="Hi Priya!", frame_id=1)
    replay.score({"id": "a", "expect_any": [""]}, [said], frames, oracle=True)
    asked = Turn(question="What is my name?", answer="Priya.", frame_id=2,
                 told=["My name is Priya."])
    step = {"id": "b", "expect_any": ["priya"], "evidence": ["a"]}
    assert replay.score(step, [asked], frames, oracle=True)["evidence_ok"] is True
    asked.told, asked.memories = [], [1]  # the frame alone does not prove the statement
    assert replay.score(step, [asked], frames, oracle=True)["evidence_ok"] is False
    shown = {"id": "c", "expect_any": [""], "evidence": ["b"]}  # a question step: its frame
    recall = Turn(question="What did I ask?", answer="Your name.", frame_id=3, memories=[2])
    assert replay.score(shown, [recall], frames, oracle=True)["evidence_ok"] is True
