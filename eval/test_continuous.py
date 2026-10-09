"""Continuous scheduling and process supervision, using invented input only."""

import dataclasses
import json
import queue
import subprocess
import sys
import wave
from types import SimpleNamespace

import pytest

from eval import continuous as c


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def time(self):
        return 1000.0 + self.now

    def sleep(self, seconds):
        self.now += seconds


@dataclasses.dataclass
class Turn:
    question: str
    answer: str
    speech_start: float
    speech_end: float
    memories: list = dataclasses.field(default_factory=lambda: [7])
    frame_id: int = 8
    told: list = dataclasses.field(default_factory=list)
    prompt: list = dataclasses.field(default_factory=list)
    wav: str = "answer.wav"
    retrieved: float = 0.0
    done: float = 0.0


class FakeRobot:
    constructions = 0

    def __init__(self, clock, replies=()):
        FakeRobot.constructions += 1
        self.clock, self.replies = clock, list(replies)
        import numpy as np

        self.camera = SimpleNamespace(
            show=lambda path: None, latest=lambda: (np.zeros((2, 2, 3), np.uint8), 1000.0)
        )
        self.lines, self.jobs, self.turns = queue.Queue(), queue.Queue(), queue.Queue()
        self.speaker = SimpleNamespace(q=queue.Queue())
        self.threads = [
            SimpleNamespace(name=name, is_alive=lambda: True)
            for name in ("_watch", "_detect", "_transcribe", "_work")
        ]
        self.brain = SimpleNamespace(proc=SimpleNamespace(poll=lambda: None))
        self.memory = SimpleNamespace(
            points=lambda ids: [{"id": 7, "ts": 1000.1, "said": "invented"}]
        )
        self.asked, self.detections, self.speaking, self.detect_failed = 0, 0, False, None
        self.history, self.chunks = [], []

    def hear(self, chunk):
        self.detections += 1
        self.chunks.append((self.clock.now, chunk.copy()))
        while self.replies and self.clock.now >= self.replies[0][0]:
            _, turn = self.replies.pop(0)
            self.asked += 1
            self.turns.put(turn)


def write_fixture(tmp_path):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"invented source; fake camera only")
    audio = tmp_path / "audio"
    audio.mkdir()
    visits = []
    for vid, start in (("visitor-a", 0), ("visitor-b", 4)):
        visits.append(
            {
                "id": vid,
                "start_at_s": start,
                "duration_s": 4 if start == 0 else 5,
                "continuous_process": True,
                "restart": False,
                "steps": [],
            }
        )
    for visit, sid, at, size in (
        (0, "a", 0.4, 2560),
        (0, "b", 2.2, 1600),
        (1, "d", 4.3, 2560),
        (1, "e", 6.3, 1600),
    ):
        visits[visit]["steps"].append(
            {"id": sid, "at_s": at, "say": "Invented local statement.", "scored": sid in ("b", "e")}
        )
        with wave.open(str(audio / f"{sid}.wav"), "wb") as f:
            f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            f.writeframes(b"\x01\x01" * size)
    for visit, start, until in ((0, 0, 4), (1, 4, 9)):
        visits[visit]["steps"].insert(
            0,
            {
                "id": f"source-{visit}",
                "at_s": start,
                "show": "source.jpg",
                "source_id": f"invented-{visit}",
                "scored": False,
                "hold_final_frame_until_s": until,
            },
        )
    cases = tmp_path / "visits.jsonl"
    cases.write_text("".join(json.dumps(v) + "\n" for v in visits))
    return cases, audio


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def replay(tmp_path, replies=(), change=None):
    cases, audio = write_fixture(tmp_path)
    visits, steps, wavs, duration = c.preflight(cases, audio)
    clock, output = Clock(), tmp_path / "output.jsonl"
    robot = FakeRobot(clock, replies)
    if change:
        change(robot)
    result = c.evaluate(visits, steps, wavs, duration, robot, robot.camera, output, clock)
    return result, robot, rows(output)


def test_absolute_audio_and_association_across_visits(tmp_path):
    FakeRobot.constructions = 0
    replies = [
        (2.0, Turn("invented", "yes", 1000.42, 1000.55)),
        (3.0, Turn("split one", "one", 1002.21, 1002.24)),
        (3.1, Turn("split two", "two", 1002.25, 1002.29)),
        (6.0, Turn("", "", 1004.31, 1004.45)),
        (7.0, Turn("last invented", "last", 1006.31, 1006.39)),
    ]
    result, robot, log = replay(tmp_path, replies)
    assert FakeRobot.constructions == 1
    assert result["elapsed_s"] == 9
    assert result["failed_steps"] == 2
    events = [r for r in log if r["type"] == "event"]
    assert [r["actual_s"] for r in events] == [0, 0.4, 2.2, 4, 4.3, 6.3]
    utterances = [r for r in log if r["type"] == "utterance"]
    assert [(r["id"], r["split"], r["ok"]) for r in utterances] == [
        ("a", 1, True),
        ("b", 2, False),
        ("d", 1, False),
        ("e", 1, True),
    ]
    first = next(r for r in log if r["type"] == "audio" and r["id"] == "a")
    assert first["due_end_s"] == pytest.approx(0.48)
    assert first["samples"] == 1280
    assert sum(len(chunk) for _, chunk in robot.chunks) == 9 * c.RATE
    assert any(not chunk.any() for _, chunk in robot.chunks)
    turn = next(r for r in log if r["type"] == "turn")
    assert turn["id"] == "a" and turn["payloads"][0]["id"] == 7
    assert turn["source_mappings"][0]["source_ids"] == ["invented-0"]
    assert turn["prompt_tokens"] is None and turn["queues"]


def test_missing_transcript_does_not_shift_next_utterance(tmp_path):
    result, _, log = replay(tmp_path, [(3.0, Turn("second", "yes", 1002.21, 1002.29))])
    assert result["failed_steps"] == 3
    utterances = [r for r in log if r["type"] == "utterance"]
    assert utterances[0]["heard"] == "" and utterances[1]["heard"] == "second"


@pytest.mark.parametrize("failure", ["thread", "llama", "detector", "pending", "unmatched"])
def test_operational_failures_preserve_earlier_rows(tmp_path, failure):
    def change(robot):
        if failure == "thread":
            robot.threads[0].is_alive = lambda: False
        elif failure == "llama":
            robot.brain.proc.poll = lambda: 9
        elif failure == "detector":
            robot.detect_failed = RuntimeError("invented failure")
        elif failure == "pending":
            robot.lines.put("stuck")
        else:
            robot.replies = [(1, Turn("wrong interval", "wrong", 999, 999.1))]

    with pytest.raises(RuntimeError):
        replay(tmp_path, change=change)
    log = rows(tmp_path / "output.jsonl")
    assert log and all(r.get("type") != "completion" for r in log)


def test_detector_stall(tmp_path, monkeypatch):
    monkeypatch.setitem(c.TIMEOUTS, "schedule", 0.5)
    with pytest.raises(RuntimeError, match="detector stalled"):
        replay(tmp_path, change=lambda r: setattr(r, "hear", lambda chunk: None))


@pytest.mark.parametrize("failure", ["absent", "overlap", "format", "duplicate", "path"])
def test_preflight_rejects_before_construction(tmp_path, failure):
    cases, audio = write_fixture(tmp_path)
    visits = [json.loads(line) for line in cases.read_text().splitlines()]
    if failure == "absent":
        (audio / "a.wav").unlink()
    elif failure == "overlap":
        visits[0]["steps"][2]["at_s"] = 0.6
    elif failure == "format":
        with wave.open(str(audio / "a.wav"), "wb") as f:
            f.setparams((2, 2, 16000, 0, "NONE", "not compressed"))
            f.writeframes(b"\x00" * 320)
    elif failure == "duplicate":
        visits[1]["id"] = visits[0]["id"]
    else:
        visits[0]["steps"][0]["show"] = "../outside.jpg"
    cases.write_text("".join(json.dumps(v) + "\n" for v in visits))
    with pytest.raises((ValueError, FileNotFoundError)):
        c.preflight(cases, audio)


def run_supervisor(tmp_path, ending, failed=0):
    output = tmp_path / "supervised.jsonl"
    output.touch()
    child_pid = tmp_path / "child.pid"
    marker = tmp_path / "teardown.marker"
    ready = {
        "type": "completion_ready",
        "counts": {"visits": 1, "show": 0, "scored": 1, "auxiliary": 0},
        "elapsed_s": 1,
        "event_ids": ["invented"],
        "utterance_ids": ["invented"],
        "visit_ids": ["invented-visit"],
        "failed_steps": failed,
        "chunks": 1,
    }
    code = f"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
Path({str(child_pid)!r}).write_text(str(child.pid))
def emit(row):
    with open({str(output)!r}, 'a') as f:
        f.write(json.dumps(row) + '\\n')
        f.flush()
emit({{"type": "event", "id": "invented"}})
emit({{"type": "utterance", "id": "invented", "ok": {failed == 0!r}}})
emit({{"type": "phase", "phase": "cleanup"}})
{ending}
"""
    command = [sys.executable, "-c", code]
    status = c.supervise(
        command,
        output,
        ready["counts"],
        1,
        ["invented"],
        ["invented"],
        ["invented-visit"],
        {key: 0.4 for key in c.TIMEOUTS},
    )
    return status, rows(output), child_pid, marker, ready


@pytest.mark.parametrize(
    "ending",
    [
        "os.kill(os.getpid(), signal.SIGSTOP)",
        "emit(READY); os._exit(7)",
        "time.sleep(60)",
    ],
)
def test_supervisor_stopped_crashed_and_hung_worker(tmp_path, ending):
    ready = {
        "type": "completion_ready",
        "counts": {"visits": 1, "show": 0, "scored": 1, "auxiliary": 0},
        "elapsed_s": 1,
        "event_ids": ["invented"],
        "utterance_ids": ["invented"],
        "visit_ids": ["invented-visit"],
        "failed_steps": 0,
        "chunks": 1,
    }
    status, log, pidfile, _, _ = run_supervisor(tmp_path, ending.replace("READY", repr(ready)))
    assert status != 0
    assert any(r.get("type") == "utterance" for r in log)
    assert any(r.get("supervisor") for r in log)
    assert not any(r.get("completed") for r in log)
    pid = int(pidfile.read_text())
    # Orphan zombies can await init reaping; no child can continue running.
    check = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2
    )
    assert not check.stdout.strip() or check.stdout.strip().startswith("Z")


@pytest.mark.parametrize("failed", [0, 1])
def test_footer_only_after_worker_exit_and_teardown(tmp_path, failed):
    ready = {
        "type": "completion_ready",
        "counts": {"visits": 1, "show": 0, "scored": 1, "auxiliary": 0},
        "elapsed_s": 1,
        "event_ids": ["invented"],
        "utterance_ids": ["invented"],
        "visit_ids": ["invented-visit"],
        "failed_steps": failed,
        "chunks": 1,
    }
    ending = (
        f"emit({ready!r}); child.terminate(); child.wait(); "
        f"Path({str(tmp_path / 'teardown.marker')!r}).write_text('native teardown reached')"
    )
    status, log, _, marker, _ = run_supervisor(tmp_path, ending, failed)
    assert status == failed and marker.exists()
    assert log[-1]["completed"] and log[-1]["worker_exit"] == 0


def test_reject_ready_without_duration_or_all_events(tmp_path):
    ready = {
        "type": "completion_ready",
        "counts": {"visits": 1, "show": 0, "scored": 1, "auxiliary": 0},
        "elapsed_s": 0.1,
        "event_ids": ["invented"],
        "utterance_ids": ["invented"],
        "visit_ids": ["invented-visit"],
        "failed_steps": 0,
        "chunks": 1,
    }
    status, log, _, _, _ = run_supervisor(
        tmp_path, f"emit({ready!r}); child.terminate(); child.wait()"
    )
    assert status != 0 and not any(r.get("completed") for r in log)


@pytest.mark.parametrize("duration", [173.131, 173.131023])
def test_nonbinary_duration_many_chunks_and_final_partial(tmp_path, duration):
    clock, robot = Clock(), None
    robot = FakeRobot(clock)
    visit = {
        "id": "long-invented",
        "start_at_s": 0,
        "duration_s": duration,
        "continuous_process": True,
        "restart": False,
        "steps": [],
    }
    output = tmp_path / "long.jsonl"
    result = c.evaluate([visit], [], {}, duration, robot, robot.camera, output, clock)
    assert result["elapsed_s"] == pytest.approx(duration)
    assert result["samples"] == 2770096
    assert sum(len(chunk) for _, chunk in robot.chunks) == 2770096
    assert len(robot.chunks[-1][1]) < c.CHUNK
    assert all(row["lateness_s"] == 0 for row in rows(output) if row["type"] == "audio")


def test_pending_turn_work_stalls_with_healthy_detector(tmp_path):
    clock = Clock()
    robot = FakeRobot(clock)
    original_hear = robot.hear

    def hear(chunk):
        original_hear(chunk)
        robot.jobs.put("background work must not conceal stalled ASR")
        if clock.now >= 0.5 and not robot.lines.unfinished_tasks:
            robot.lines.put("blocked ASR")

    robot.hear = hear
    visit = {
        "id": "stalled-invented",
        "start_at_s": 0,
        "duration_s": 15,
        "continuous_process": True,
        "restart": False,
        "steps": [],
    }
    with pytest.raises(RuntimeError, match="pending turn work stalled"):
        c.evaluate([visit], [], {}, 15, robot, robot.camera, tmp_path / "stall.jsonl", clock)
    assert robot.detections > 10


def test_final_boundary_thread_death_fails(tmp_path):
    def change(robot):
        original_hear = robot.hear

        def hear(chunk):
            original_hear(chunk)
            if robot.clock.now >= 9:
                robot.threads[0].is_alive = lambda: False

        robot.hear = hear

    with pytest.raises(RuntimeError, match="thread died"):
        replay(tmp_path, change=change)


def test_zero_exit_with_live_descendant_has_no_footer(tmp_path):
    ready = {
        "type": "completion_ready",
        "counts": {"visits": 1, "show": 0, "scored": 1, "auxiliary": 0},
        "elapsed_s": 1,
        "event_ids": ["invented"],
        "utterance_ids": ["invented"],
        "visit_ids": ["invented-visit"],
        "failed_steps": 0,
        "chunks": 1,
    }
    status, log, pidfile, _, _ = run_supervisor(tmp_path, f"emit({ready!r})")
    assert status != 0 and not any(row.get("completed") for row in log)
    assert any("descendants" in row.get("error", "") for row in log)
    check = subprocess.run(
        ["ps", "-o", "stat=", "-p", pidfile.read_text()], capture_output=True, text=True, timeout=2
    )
    assert not check.stdout.strip() or check.stdout.strip().startswith("Z")


def test_killed_worker_reaping_is_bounded(monkeypatch):
    seen = []

    def wait(timeout):
        seen.append(timeout)
        raise subprocess.TimeoutExpired("invented-worker", timeout)

    monkeypatch.setattr(c.os, "killpg", lambda _pid, _sig: None)
    proc = SimpleNamespace(pid=123, wait=wait)
    assert c.kill_group(proc) is False
    assert seen == [10]


def test_worker_constructs_once_and_closes_after_both_visits(tmp_path, monkeypatch):
    cases, audio = write_fixture(tmp_path)
    output, clock, lifecycle = tmp_path / "worker.jsonl", Clock(), []
    robot = FakeRobot(clock)
    camera = robot.camera
    camera.show = lambda path: lifecycle.append(("show", path.name, clock.now))
    camera.close = lambda: lifecycle.append(("camera-close", clock.now))
    robot.close = lambda: lifecycle.append(("robot-close", clock.now))

    def factory(source, out, memory, model, wake_word):
        lifecycle.append(("construct", source is camera, wake_word, memory.name, model))
        assert out.name == "audio"
        return robot

    real_evaluate = c.evaluate
    monkeypatch.setitem(
        sys.modules,
        "robot.brain",
        SimpleNamespace(SYSTEM="invented system", server_args=lambda model: [model]),
    )
    monkeypatch.setitem(sys.modules, "robot.camera", SimpleNamespace(FileCamera=lambda: camera))
    monkeypatch.setitem(sys.modules, "robot.main", SimpleNamespace(Robot=factory))
    monkeypatch.setattr(c, "evaluate", lambda *args: real_evaluate(*args, clock=clock))
    monkeypatch.delenv("ROBOT_SHARED", raising=False)
    assert c.worker(cases, audio, output, "invented-model") == 0
    assert lifecycle == [
        ("construct", True, False, "memory", "invented-model"),
        ("show", "source.jpg", 0),
        ("show", "source.jpg", 4),
        ("robot-close", 9),
        ("camera-close", 9),
    ]
    log = rows(output)
    assert log[-1]["type"] == "completion_ready"
    assert log[-1]["samples"] == 9 * c.RATE
    assert not any(row.get("completed") for row in log)
