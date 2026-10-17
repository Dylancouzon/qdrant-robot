"""Worker failures must reach callers and release queued work before shutdown."""
import queue
import threading
import time
from types import SimpleNamespace as Stub

import numpy as np
import pytest

from robot import main
from robot.main import Robot
from robot.head import Head


def bare_robot():
    robot = Robot.__new__(Robot)
    robot.jobs, robot.lines, robot.turns = queue.Queue(), queue.Queue(), queue.Queue()
    robot.closing, robot.detecting = threading.Event(), threading.Lock()
    robot.worker_failed, robot.detect_failed = None, None
    robot.asked = 0
    robot.head, robot.wake_word, robot.last_line, robot.last_input = Head(), False, 0., 0.
    return robot


@pytest.mark.parametrize("worker", ["transcribe", "work"])
def test_failed_worker_drains_and_reports(worker, capsys):
    robot = bare_robot()
    error = RuntimeError("injected worker failure")
    calls = []

    def fail(*args):
        calls.append(args)
        raise error

    if worker == "transcribe":
        pending = robot.lines
        robot.scribe = fail
        item = (np.zeros(160, np.float32), 1.0, 1.0, 1.0, (None, 1.0), None, None)
    else:
        pending = robot.jobs
        robot._look = fail
        item = ("look", (None, 1.0))
    for job in (item, item, None):
        pending.put(job)
    getattr(robot, "_" + worker)()
    assert len(calls) == 1, "queued work must stop after a fatal failure"
    assert pending.unfinished_tasks == 0 and pending.empty()
    assert robot.closing.is_set()
    with pytest.raises(RuntimeError, match="stopped") as raised:
        robot.check_health()
    assert raised.value.__cause__ is error
    assert "injected worker failure" in capsys.readouterr().err


@pytest.mark.parametrize("worker", ["transcribe", "work"])
def test_healthy_worker_drains(worker):
    robot = bare_robot()
    calls = []
    if worker == "transcribe":
        pending = robot.lines
        robot.scribe = lambda speech: "Hey Edgy"
        item = (np.zeros(160, np.float32), 1.0, 1.0, 1.0, (None, 1.0), None, None)
    else:
        pending = robot.jobs
        robot._look = lambda shot: calls.append(shot)
        item = ("look", (None, 1.0))
    for job in (item, item, None):
        pending.put(job)
    getattr(robot, "_" + worker)()
    assert pending.unfinished_tasks == 0 and pending.empty()
    assert robot.worker_failed is None and not robot.closing.is_set()
    assert robot.asked == 2 if worker == "transcribe" else len(calls) == 2


@pytest.mark.parametrize("fault", ["worker", "head"])
def test_close_after_worker_failure(fault):
    robot = bare_robot()
    closed = []

    def resource(name):
        return Stub(close=lambda: closed.append(name))

    robot.video, robot.detect, robot.speaker, robot.brain = [
        resource(name) for name in ("view", "detector", "speaker", "brain")]
    for name in ("memory", "people", "things", "knowledge"):
        setattr(robot, name, Stub(shard=resource(name)))
    robot.recognition = resource("recognition")
    robot.recognition.pause = lambda: closed.append("pause")
    failed = threading.Event()

    def fail(shot):
        failed.set()
        if fault == "head":
            robot.head.error = "injected head fault"
        else:
            raise RuntimeError("injected shutdown failure")

    robot._look, robot.scribe = fail, lambda speech: ""
    robot.threads = [threading.Thread(target=target, daemon=True) for target in (
        robot.closing.wait, robot.closing.wait, robot._transcribe, robot._work)]
    for thread in robot.threads:
        thread.start()
    robot.jobs.put(("look", (None, 1.0)))
    assert failed.wait(2)
    result = queue.Queue()

    def close():
        try:
            robot.close()
        except Exception as error:
            result.put(error)

    closer = threading.Thread(target=close, daemon=True)
    closer.start()
    closer.join(2)
    assert not closer.is_alive(), "shutdown hung after worker failure"
    error = result.get_nowait()
    assert isinstance(error, RuntimeError) and "stopped" in str(error)
    assert all(not thread.is_alive() for thread in robot.threads)
    assert set(closed) == {"view", "detector", "pause", "recognition", "speaker",
                           "memory", "people", "things", "knowledge", "brain"}
    assert robot.jobs.unfinished_tasks == robot.lines.unfinished_tasks == 0


def test_next_turn_stops_waiting_on_failure():
    robot = bare_robot()
    error = RuntimeError("injected answer failure")
    waiting = threading.Event()

    def fail():
        assert waiting.wait(2)
        robot.worker_failed = "_work", error

    thread = threading.Thread(target=fail, daemon=True)
    thread.start()
    started = time.monotonic()
    waiting.set()
    with pytest.raises(RuntimeError, match="_work stopped") as raised:
        robot.next_turn(timeout=60)
    thread.join(2)
    assert raised.value.__cause__ is error and time.monotonic() - started < 2
    robot.worker_failed = None
    robot.turns.put("completed")
    assert robot.next_turn() == "completed"
    with pytest.raises(queue.Empty):
        robot.next_turn(timeout=0.01)


def test_live_failure_closes_resources(monkeypatch):
    from robot import camera

    error = RuntimeError("injected live failure")
    closed = []

    def hear(chunk):
        raise error

    def chunks():
        try:
            yield np.zeros(160, np.float32)
        finally:
            closed.append("microphone")

    robot = Stub(hear=hear, close=lambda: closed.append("robot"))
    monkeypatch.setattr(main, "Robot", lambda *args, **_kwargs: robot)
    monkeypatch.setattr(camera, "Camera", lambda: Stub(close=lambda: closed.append("camera")))
    monkeypatch.setattr(main.audio, "mic", chunks)
    monkeypatch.setattr(main.audio, "set_volume", lambda value: None)
    monkeypatch.setattr(main, "argparse", Stub(ArgumentParser=lambda **_kwargs: Stub(
        add_argument=lambda *args, **_kwargs: None, parse_args=lambda: Stub(
            camera_file=None, servo_calibration=None))))
    with pytest.raises(RuntimeError) as raised:
        main.main()
    assert raised.value is error and closed == ["robot", "microphone", "camera"]


def test_live_model_startup_failure_releases_motor(monkeypatch):
    from robot import camera, servo
    closed, handlers = [], []
    error = RuntimeError("injected model startup failure")
    monkeypatch.setattr(servo.SerialMotor, "open", lambda _path:
                        Stub(close=lambda: closed.append("motor")))
    monkeypatch.setattr(main, "Robot", lambda *args, **kwargs:
                        (_ for _ in ()).throw(error))
    monkeypatch.setattr(camera, "Camera", lambda: Stub(close=lambda: closed.append("camera")))
    monkeypatch.setattr(main.audio, "mic", lambda: Stub(close=lambda: closed.append("microphone")))
    monkeypatch.setattr(main.audio, "set_volume", lambda value: None)
    monkeypatch.setattr(main.signal, "signal", lambda *args: handlers.append(args))
    monkeypatch.setattr(main, "argparse", Stub(ArgumentParser=lambda **kwargs: Stub(
        add_argument=lambda *args, **kwargs: None, parse_args=lambda: Stub(
            camera_file=None, servo_calibration="bench.json"))))
    with pytest.raises(RuntimeError) as raised:
        main.main()
    assert raised.value is error and closed == ["microphone", "camera", "motor"]
    assert handlers == [(main.signal.SIGTERM, main.interrupt)]


def test_head_fault_rejects_input_instead_of_silently_disabling_vision():
    robot = bare_robot()
    robot.head.error = "Torque off is UNCONFIRMED. Disconnect servo power."
    with pytest.raises(RuntimeError, match="head stopped.*UNCONFIRMED"):
        robot.hear(np.zeros(160, np.float32))
    with pytest.raises(RuntimeError, match="head stopped.*UNCONFIRMED"):
        robot.next_turn(timeout=1)


def test_accepted_wake_opens_followup_window_before_answer_finishes():
    robot = bare_robot()
    robot.wake_word, robot.last_line = True, 0.
    woke = main.Turn(question="Hey Edgy, what is this?", speech_start=100., speech_end=101.)
    robot._motion_request(woke)
    followup = main.Turn(question="Look right.", speech_start=102., speech_end=103.)
    robot._motion_request(followup)
    assert robot.last_input == 103. and robot.last_line == 0. and followup.motion > 0
    stop = robot.head.request("stop")
    with pytest.raises(main.Interrupted):
        robot.head.move(45, followup.motion)
    assert robot.head.generation == stop and not robot.head.following


def test_accepted_followup_extends_window_while_previous_answer_is_pending():
    robot = bare_robot()
    robot.wake_word, robot.last_line = True, 100.
    first = main.Turn(question="What is this?", speech_start=150., speech_end=151.)
    robot._motion_request(first)
    second = main.Turn(question="Look left.", speech_start=161., speech_end=162.)
    robot._motion_request(second)
    assert robot.last_input == 162. and robot.last_line == 100. and second.motion > 0
    rejected = main.Turn(question="Look right.", speech_start=223., speech_end=224.)
    robot._motion_request(rejected)
    assert rejected.motion == -1 and robot.last_input == 162. and robot.last_line == 100.
