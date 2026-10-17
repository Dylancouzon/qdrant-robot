"""Head limits, cancellation, and closed-loop camera projection without physical movement."""
import math
import time
import threading

import numpy as np
import pytest

from robot.attention import Candidate, choose
from robot.head import Head, Interrupted, SimMotor, command
from robot.people import DIM


def candidate(index, name=None, box=(400, 100, 520, 220)):
    return Candidate(np.eye(DIM, dtype=np.float32)[index], 120, box,
                     [(name, 1., 1.)] if name else [])


def test_known_and_unknown_introduction_and_explicit_handover():
    known, unknown = candidate(0, "Dylan"), candidate(1)
    assert choose([known, unknown])[0] is known
    assert choose([known, unknown], known.vector, "My name is Sam.")[0] is unknown
    assert choose([known, unknown], known.vector, "My name is Dylan.")[0] is unknown
    assert choose([known, unknown], unknown.vector, "This is my phone.")[0] is unknown
    assert choose([unknown, known], unknown.vector, "Talk to Dylan.")[0] is known
    assert choose([unknown], unknown.vector, "Talk to Dylan.")[0] is None
    assert choose([known], unknown.vector, "This is my phone.")[0] is None
    assert choose([known, unknown, candidate(2)], known.vector, "I am Sam.")[0] is None
    assert choose([known, candidate(0, "Dylan")], known.vector)[0] is None


@pytest.mark.parametrize("text, expected", [
    ("What is on your right?", "right"), ("What's to your left?", "left"),
    ("Look left.", "left"), ("Stop following me!", "stop"),
    ("What was on your right earlier?", None), ("The stop sign is red.", None),
    ("Do not stop following me.", None), ("I left my phone.", None),
])
def test_only_explicit_present_commands_move(text, expected):
    assert command(text) == expected


def drive(head, start=100., seconds=1.):
    for tick in range(round(seconds / .05)):
        head.tick(start + tick * .05)


def test_projected_person_converges_and_holds_at_travel_limit():
    motor = SimMotor()
    head = Head(motor)
    focal = 640 / math.tan(math.radians(35))
    errors = []
    for tick in range(450):
        now = 100 + tick / 15
        head.tick(now)
        bearing = min(25., max(0., (now - 101) * 5))
        center = 640 + focal * math.tan(math.radians(bearing - head.angle))
        head.follow((center - 100, 40, center + 100, 680), 1280, now, now)
        errors.append(abs(center / 1280 - .5))
    assert max(errors[:100]) > .12
    assert max(errors[-50:]) <= .12
    assert motor.goals and all(abs(goal) <= 70 for goal in motor.goals)
    for tick in range(500):
        now = 131 + tick / 15
        head.tick(now)
        head.follow((1000, 50, 1280, 680), 1280, now, now)
    assert head.angle == 70 and max(motor.goals) == 70


def test_stale_sources_stop_playback_and_old_returns():
    motor = SimMotor()
    playing = [False]
    head = Head(motor, blocked=lambda: playing[0])
    drive(head)
    head.follow((1000, 0, 1280, 700), 1280, 99., 101.)
    assert head.goal == 0
    generation = head.request("right")
    head.move(45, generation)
    drive(head, 101., .4)
    assert 0 < head.angle < 45
    playing[0] = True
    drive(head, 101.4, .5)
    held = head.angle
    drive(head, 101.9, .5)
    assert head.angle == held
    head.request("stop")
    playing[0] = False
    drive(head, 102.4, .5)
    with pytest.raises(Interrupted):
        head.move(0, generation)
    with pytest.raises(Interrupted):
        head.resume(generation)
    assert not head.following and head.angle == held


def test_failures_disable_motion_and_invalidate_capture_time():
    motor = SimMotor()
    head = Head(motor)
    drive(head)
    token = head.request("left")
    head.move(-45, token)
    drive(head, 101., 3.)
    assert not head.valid(100.5) and head.valid(104.)
    assert not head.valid(104., view=0)
    motor.angle = float("nan")
    head.tick(104.)
    assert head.error and not head.following
    with pytest.raises(RuntimeError):
        head.wait(token, timeout=.01)


def test_wait_timeout_stops_and_disabled_head_has_no_writes():
    head = Head(SimMotor())
    token = head.request("left")
    head.move(-45, token)
    with pytest.raises(RuntimeError, match="timed out"):
        head.wait(token, timeout=.01)
    assert not head.following
    disabled = Head()
    token = disabled.request("right")
    with pytest.raises(RuntimeError, match="disabled"):
        disabled.move(45, token)
    assert disabled.valid(time.time())


def test_inspection_preserves_stop_until_verified_handover():
    head = Head()
    head.request("stop")
    head.request("right")
    assert not head.following
    token = head.request("handover")
    assert not head.following
    head.activate(token)
    assert head.following


def test_stop_and_turn_cleanup_are_atomic():
    for _ in range(50):
        head = Head()
        token = head.request("right")
        head.paused = True
        ready = threading.Barrier(2)
        def stop(target=head, barrier=ready):
            barrier.wait()
            target.request("stop")
        worker = threading.Thread(target=stop)
        worker.start()
        ready.wait()
        head.finish(token)
        worker.join()
        assert not head.paused and not head.following


def test_repeated_service_signal_cannot_interrupt_cleanup():
    import signal
    import subprocess
    import sys
    code = """
import signal, time
from robot.head import interrupt
signal.signal(signal.SIGTERM, interrupt)
try:
    print('ready', flush=True)
    while True:
        time.sleep(.1)
except KeyboardInterrupt:
    pass
finally:
    print('closing', flush=True)
    time.sleep(.15)
    print('closed', flush=True)
"""
    child = subprocess.Popen([sys.executable, "-u", "-c", code], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        child.send_signal(signal.SIGTERM)
        assert child.stdout.readline().strip() == "closing"
        child.send_signal(signal.SIGTERM)
        output, error = child.communicate(timeout=5)
        assert child.returncode == 0 and output.strip() == "closed" and not error
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()


def test_stop_discards_even_a_small_unsent_goal():
    motor = SimMotor()
    head = Head(motor)
    drive(head)
    token = head.request("right")
    head.move(.05, token)
    head.request("stop")
    head.tick(101.)
    assert head.goal == head.angle == 0 and motor.goals == [0]


@pytest.mark.parametrize("delay", [0., .15, .3])
def test_follow_updates_during_motion_and_expires_without_callbacks(delay):
    motor = SimMotor(speed=10)
    head = Head(motor)
    drive(head)
    edge = (1000, 0, 1280, 700)
    assert head.follow(edge, 1280, 101 - delay, 101) == "goal"
    head.tick(101.)
    head.tick(101.05)
    previous = head.goal
    assert head.moving
    assert head.follow(edge, 1280, 101.05 - delay, 101.05) == "goal"
    assert head.goal > previous
    head.tick(101.1)
    head.tick(101.4)
    held = head.goal
    drive(head, 101.45, .5)
    assert head.angle == held and not head.error
    assert not head.valid(101.)


def test_centered_and_lost_faces_cancel_pending_corrections():
    for lost in (False, True):
        head = Head(SimMotor(speed=10))
        drive(head)
        head.follow((1000, 0, 1280, 700), 1280, 101, 101)
        head.tick(101.)
        head.tick(101.05)
        if lost:
            head.hold(taken=101.06)
        else:
            assert head.follow((600, 0, 680, 700), 1280, 101.06, 101.06) == "centered"
        head.tick(101.1)
        assert head.goal == head.angle < 3
        held = head.goal
        assert head.follow((1000, 0, 1280, 700), 1280, 101.04, 101.11) == "stale source"
        drive(head, 101.15, .5)
        assert head.angle == held


def test_pre_handover_and_out_of_order_sources_cannot_restore_following(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 101.)
    head = Head(SimMotor())
    drive(head)
    old = head.generation
    new = head.request("handover")
    head.activate(new)
    head.finish(new)
    head.tick(101.)
    edge = (1000, 0, 1280, 700)
    assert head.follow(edge, 1280, 101.01, 101.02, old) == "cancelled source"
    assert head.follow(edge, 1280, 100.99, 101.02, new) == "stale source"
    assert head.follow(edge, 1280, 101.01, 101.02, new) == "goal"
    assert head.follow(edge, 1280, 101.005, 101.02, new) == "stale source"
    head.request("stop")
    assert head.follow(edge, 1280, 101.03, 101.03, new) == "cancelled source"
    assert not head.following


def test_small_reverse_face_error_cancels_previous_forward_correction():
    motor = SimMotor(speed=10)
    motor.tolerance = 1.5
    head = Head(motor)
    drive(head)
    head.follow((1000, 0, 1280, 700), 1280, 101, 101)
    head.tick(101.)
    head.tick(101.05)
    assert 0 < head.angle < head.goal
    assert head.follow((400, 0, 500, 100), 1280, 101.06, 101.06) == 'goal'
    head.tick(101.1)
    assert head.goal < head.angle < 6


def test_centered_face_jitter_keeps_camera_view_stable():
    motor = SimMotor()
    head = Head(motor)
    drive(head)
    view, goals = head.view, len(motor.goals)
    for step in range(90):
        now = 101 + step / 15
        offset = 1280 * .11 * math.sin(step / 4)
        center = 640 + offset
        assert head.follow((center - 80, 50, center + 80, 400), 1280, now, now) == 'centered'
        head.tick(now)
    assert head.view == view and len(motor.goals) == goals
    assert head.angle == 0 and not head.moving
    assert head.follow((1000, 50, 1160, 400), 1280, 108, 108) == 'goal'


def test_exception_without_message_latches_before_cleanup_closes_motor():
    class FailingMotor(SimMotor):
        reads = 0
        def read(self, now):
            self.reads += 1
            raise AssertionError()
    motor = FailingMotor()
    head = Head(motor)
    head.tick(100.)
    assert head.error == 'AssertionError' and not head.following
    head.tick(101.)
    assert motor.reads == 1
