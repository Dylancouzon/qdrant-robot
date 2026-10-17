"""Calibrated travel, stale feedback, startup ordering, and real motor shutdown failures."""
import math
from types import SimpleNamespace

import pytest

from robot import servo
from robot.head import Head
from tools.test_servo import Packet


def bus():
    packet = Packet()
    device = servo.Servo(SimpleNamespace(is_using=False), packet, 1)
    return device, packet


def motor():
    device, packet = bus()
    return servo.SerialMotor(device, 2048, 1, 10), packet


@pytest.mark.parametrize("zero,direction,limit", [
    (True, 1, 10), (2048, True, 10), (2048, 0, 10), (2048, 1, True),
    (2048, 1, math.nan), (2048, 1, 71), (10, 1, 10), (4090, 1, 10),
])
def test_invalid_calibration_never_writes(zero, direction, limit):
    device, packet = bus()
    with pytest.raises(ValueError):
        servo.SerialMotor(device, zero, direction, limit)
    assert not packet.writes


@pytest.mark.parametrize("address,value", [
    (33, 1), (65, 1), (40, 1), (66, 1), (62, 120), (63, 65), (56, 100), (11, 2050),
])
def test_unsafe_startup_never_writes(address, value):
    device, packet = bus()
    packet.memory[address] = value
    with pytest.raises((ValueError, RuntimeError)):
        servo.SerialMotor(device, 2048, 1, 10)
    assert not packet.writes


def test_prime_old_goal_and_respect_direction():
    device, packet = bus()
    packet.memory[42] = 4000
    actual = servo.SerialMotor(device, 2048, -1, 10)
    actual.move(5)
    assert packet.positions == [2048, 2048 - round(5 * servo.SCALE)]
    assert packet.memory[46] == 455  # Approximately 40 degrees/s.
    assert packet.memory[41] == 60
    assert packet.memory[48] == 200
    assert all(address >= 40 for address, _ in packet.writes)
    actual.close()
    assert packet.memory[40] == 0


def test_head_uses_actual_motor_limits_and_arrival_error(monkeypatch):
    monkeypatch.setattr(servo.time, "time", lambda: 100.)
    actual, packet = motor()
    head = Head(actual)
    head.tick(100.)
    token = head.request("right")
    head.move(45, token)
    head.tick(100.05)
    assert abs(packet.memory[42] - 2048) <= 10 * servo.SCALE
    packet.memory[56] -= 7  # Physical run stopped seven steps short (0.615 degrees).
    head.tick(100.10)
    head.tick(100.25)
    assert not head.moving
    assert head.wait(token, .01)
    head.finish(token)
    head.follow((1000, 0, 1280, 720), 1280, 100.26, 100.26)
    assert head.goal <= 10
    head.close()


def test_stale_feedback_and_invalid_goals_cannot_write(monkeypatch):
    actual, packet = motor()
    for angle in (11, -11, math.nan):
        with pytest.raises(ValueError):
            actual.move(angle)
    monkeypatch.setattr(servo.time, "monotonic", lambda: actual.feedback + .31)
    with pytest.raises(RuntimeError, match="stale"):
        actual.move(5)
    assert not packet.writes


def test_delayed_feedback_latches_fault_before_any_goal(monkeypatch):
    actual, packet = motor()
    clock = [100.]
    original = actual.servo.status
    def delayed():
        clock[0] += .31
        return original()
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(actual.servo, "status", delayed)
    head = Head(actual)
    head.tick(100.)
    assert "expired" in head.error and not head.following
    assert packet.writes == [(40, 0)]
    head.tick(101.)
    assert packet.writes == [(40, 0)]


def test_lost_enable_ack_is_latched_and_releases_torque():
    actual, packet = motor()
    packet.fail_at = (40, 1)
    head = Head(actual)
    head.tick(100.)
    assert "timeout" in head.error
    assert packet.memory[40] == 0 and actual.closed
    writes = list(packet.writes)
    head.tick(101.)
    assert packet.writes == writes


def test_failed_torque_off_closes_port_and_keeps_fault():
    actual, packet = motor()
    cleanup = []
    actual.connection = SimpleNamespace(__exit__=lambda *args: cleanup.append(True))
    packet.fail_at = (40, 0)
    head = Head(actual)
    head.tick(100.)
    assert "UNCONFIRMED" in head.error and actual.closed and cleanup == [True]
    head.close()
    assert "UNCONFIRMED" in head.error


def test_stall_and_movement_deadline(monkeypatch):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    head = Head(actual)
    head.tick(100.)
    token = head.request("left")
    head.move(-5, token)
    head.tick(100.1)
    packet.memory.update({56: 2048, 66: 1})
    clock[0] += 1.1
    head.tick(101.2)
    assert "stalled" in head.error and packet.memory[40] == 0

    actual, packet = motor()
    actual.move(5)
    actual.deadline = clock[0] - 1
    packet.memory[56] = 2050  # Some progress, but beyond its movement deadline.
    with pytest.raises(RuntimeError, match="timed out"):
        actual.read(0)
    actual.close()


class DelayedPacket(Packet):
    """Advance actual position at 20 degrees/s during every delayed bus transaction."""
    def __init__(self):
        import time
        super().__init__()
        self.delay, self.position, self.last = .002, 2048., time.monotonic()

    def advance(self):
        import time
        time.sleep(self.delay)
        now = time.monotonic()
        if self.memory[40]:
            delta = self.memory[42] - self.position
            step = min(abs(delta), (now - self.last) * 20 * servo.SCALE)
            self.position += math.copysign(step, delta)
        self.last = now
        self.memory[56] = round(self.position)
        self.memory[66] = int(self.memory[40] and abs(self.memory[42] - self.position) > 1)

    def read1ByteTxRx(self, port, ident, address):
        self.advance()
        return super().read1ByteTxRx(port, ident, address)

    read2ByteTxRx = read1ByteTxRx

    def write1ByteTxRx(self, _port, _id, address, value):
        self.advance()
        self.writes.append((address, value))
        self.memory[address] = value
        return (-6, 0) if (address, value) == self.fail_at else (0, 0)

    write2ByteTxRx = write1ByteTxRx


@pytest.mark.parametrize("fault", [None, "delayed", "lost_ack"])
def test_complete_stop_path_with_delayed_finite_speed_bus(fault):
    import time
    packet = DelayedPacket()
    actual = servo.SerialMotor(servo.Servo(SimpleNamespace(is_using=False), packet, 1),
                               2048, 1, 10)
    head = Head(actual)
    try:
        head.start()
        head.wait(0, 2)
        token = head.request("right")
        head.move(8, token)
        until = time.monotonic() + 2
        while head.angle < 1 and time.monotonic() < until:
            time.sleep(.005)
        assert head.moving and head.angle >= 1
        before, started = actual.position, time.monotonic()
        if fault == "delayed":
            packet.delay = .045
        if fault == "lost_ack":
            packet.fail_at = (42, round(2048 - 5 * servo.SCALE))
            token = head.request("left")
            head.move(-5, token)
        else:
            token = head.request("stop")
        try:
            head.wait(token, 2)
        except RuntimeError:
            assert fault and head.error
        elapsed = time.monotonic() - started
        distance = abs(actual.position - before) / servo.SCALE
        assert elapsed <= (2 if fault else .3)
        assert distance <= (20 if fault else 3)
        if fault:
            assert actual.closed and packet.memory[40] == 0
        else:
            assert not head.following and not head.moving
    finally:
        head.close()


def test_partial_open_closes_connection_without_enabling(tmp_path, monkeypatch):
    import contextlib
    device, packet = bus()
    packet.memory[40] = 1
    closed = []
    @contextlib.contextmanager
    def connection(_path):
        try:
            yield device
        finally:
            closed.append(True)
    monkeypatch.setattr(servo, "connect", connection)
    config = tmp_path / "servo.json"
    config.write_text('{"port":"/dev/unused","zero":2048,"direction":1,"limit":10}')
    with pytest.raises(RuntimeError, match="torque off"):
        servo.SerialMotor.open(config)
    assert closed == [True] and not packet.writes


@pytest.mark.parametrize("text", ['[]', '{}', '{"port":"/dev/unused"}',
                                  '{"port":"unused","zero":2048,"direction":1,"limit":10}'])
def test_malformed_config_never_opens_port(tmp_path, monkeypatch, text):
    config = tmp_path / "servo.json"
    config.write_text(text)
    monkeypatch.setattr(servo, "connect", lambda _: pytest.fail("Port opened for bad config"))
    with pytest.raises(ValueError):
        servo.SerialMotor.open(config)


def test_stop_waits_for_bounded_startup_without_old_goal_jump():
    import threading
    import time
    packet = DelayedPacket()
    actual = servo.SerialMotor(servo.Servo(SimpleNamespace(is_using=False), packet, 1),
                               2048, 1, 10)
    packet.memory[42], packet.delay = 4000, .02
    head = Head(actual)
    start = threading.Thread(target=head.start)
    try:
        start.start()
        time.sleep(.04)
        started = time.monotonic()
        token = head.request("stop")
        head.wait(token, 2)
        assert time.monotonic() - started <= 2
        assert abs(actual.position - 2048) / servo.SCALE <= 20
        assert not head.following and abs(head.angle) <= head.tolerance
    finally:
        start.join()
        head.close()


@pytest.mark.parametrize("steps,accepted", [(17, True), (18, False)])
def test_arrival_tolerance_boundary_keeps_stationary_stall_check(monkeypatch, steps, accepted):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    head = Head(actual)
    head.tick(100.)
    token = head.request("right")
    head.move(5, token)
    head.tick(100.1)
    packet.memory[56] -= steps
    head.tick(100.2)
    head.tick(100.4)
    if accepted:
        assert not head.moving and not head.error
    else:
        clock[0] += 1.1
        head.tick(101.5)
        assert "stalled" in head.error and actual.closed
    head.close()


def test_settled_hold_starts_new_watch_after_external_displacement(monkeypatch):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    actual.move(5)
    actual.read(0)
    clock[0] += .11
    actual.read(0)
    assert actual.deadline is None
    clock[0] += 10
    actual.read(0)
    packet.memory[56] -= 25  # External movement after the old travel deadline.
    actual.read(0)
    assert actual.deadline > clock[0]
    clock[0] += .5
    packet.memory[56] = packet.memory[42]
    actual.read(0)
    clock[0] += .11
    actual.read(0)
    assert actual.deadline is None
    actual.close()


def test_stationary_encoder_error_does_not_reset_view_for_every_hold():
    actual, packet = motor()
    head = Head(actual)
    head.tick(100.)
    token = head.request("right")
    head.move(5, token)
    head.tick(100.1)
    packet.memory[56] -= 7
    head.tick(100.2)
    head.tick(100.4)
    view, writes = head.view, len(packet.writes)
    for now in (100.5, 100.6, 100.7):
        head.hold()
        head.tick(now)
        assert head.valid(now)
    assert head.view == view and len(packet.writes) == writes and not head.moving
    head.close()


@pytest.mark.parametrize("voltage,accepted", [(56, True), (60, True), (61, False), (120, False)])
def test_measured_supply_readback_window(voltage, accepted):
    device, packet = bus()
    packet.memory[62] = voltage
    if accepted:
        actual = servo.SerialMotor(device, 2048, 1, 10)
        actual.close()
    else:
        with pytest.raises(RuntimeError, match="Servo supply"):
            servo.SerialMotor(device, 2048, 1, 10)
        assert not packet.writes


@pytest.mark.parametrize("temperature", [59, 60, 64, 65, 70, 80])
def test_runtime_temperature_boundary_preserves_cool_setup_requirement(temperature):
    device, packet = bus()
    packet.memory[63] = temperature
    status = device.status()
    if temperature < 60:
        servo.safe(status)
    else:
        with pytest.raises(RuntimeError, match="below 60 C"):
            servo.safe(status)
    if temperature < 65:
        actual = servo.SerialMotor(device, 2048, 1, 10)
        actual.close()
    else:
        with pytest.raises(RuntimeError, match="below 65 C"):
            servo.SerialMotor(device, 2048, 1, 10)
        assert not packet.writes


def test_runtime_temperature_trip_latches_and_releases_without_recovery():
    actual, packet = motor()
    head = Head(actual)
    head.tick(100.)
    assert packet.memory[40] == 1
    packet.memory[63] = 65
    head.tick(100.05)
    assert "temperature 65 C" in head.error and actual.closed
    assert packet.memory[40] == 0
    packet.memory[63] = 39
    head.tick(100.1)
    assert head.error and actual.closed and not head.following
    assert packet.memory[40] == 0


@pytest.mark.parametrize("steps", [7, 17])
def test_following_holds_quantized_limit_without_repeated_view_resets(monkeypatch, steps):
    monkeypatch.setattr(servo.time, "time", lambda: 100.)
    actual, packet = motor()
    head = Head(actual)
    head.tick(100.)
    token = head.request("right")
    head.move(10, token)
    head.tick(100.1)
    packet.memory[56] -= steps
    head.tick(100.2)
    head.tick(100.4)
    head.finish(token)
    view, writes = head.view, len(packet.writes)
    for step in range(20):
        now = 100.5 + step / 20
        assert head.follow((1000, 0, 1280, 720), 1280, now, now) == "limit"
        head.tick(now)
    assert head.view == view and len(packet.writes) == writes and not head.moving
    head.close()


@pytest.mark.parametrize("moving", [0, 1])
@pytest.mark.parametrize("targets", [(5, -5), (5, .1), (.1, -.1)])
def test_retargeting_a_frozen_encoder_cannot_refresh_watchdog(monkeypatch, targets, moving):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    actual.move(5)
    packet.memory.update({56: 2048, 66: moving})
    started = actual.progress
    with pytest.raises(RuntimeError, match="stalled|timed out"):
        for step in range(1, 80):
            clock[0] += .05
            actual.read(0)
            actual.move(targets[step % 2])
            packet.memory.update({56: 2048, 66: moving})
            assert actual.progress == started
    assert clock[0] - started <= 2.6
    actual.close()
    assert packet.memory[40] == 0


def test_fresh_encoder_progress_allows_continuous_goals_and_reversals(monkeypatch):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    actual.move(5)
    for direction in (1, -1):
        for _ in range(45):
            clock[0] += .05
            packet.memory.update({56: actual.position + direction * 2, 66: 1})
            actual.read(0)
            angle = (actual.position - 2048) / servo.SCALE + direction * 3
            actual.move(max(-10, min(10, angle)))
    assert actual.progress > clock[0] - .16
    actual.close()


def test_moving_flag_inside_arrival_tolerance_keeps_bounded_deadline(monkeypatch):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, "monotonic", lambda: clock[0])
    actual.move(5)
    target = packet.memory[42]
    with pytest.raises(RuntimeError, match="timed out"):
        for step in range(1, 80):
            clock[0] += .05
            packet.memory.update({56: target + (2 if step % 2 else -2), 66: 1})
            actual.read(0)
    actual.close()



@pytest.mark.parametrize('moving', [0, 1])
def test_encoder_noise_with_alternating_nearby_goals_cannot_renew_deadline(monkeypatch, moving):
    actual, packet = motor()
    clock = [actual.feedback]
    monkeypatch.setattr(servo.time, 'monotonic', lambda: clock[0])
    actual.move(1.6)
    deadline = actual.deadline
    with pytest.raises(RuntimeError, match='stalled|timed out'):
        for step in range(80):
            clock[0] += .05
            packet.memory.update({56: 2048 + (2 if step % 2 == 0 else -2), 66: moving})
            actual.read(0)
            actual.move(-1.6 if step % 2 == 0 else 1.6)
            assert actual.deadline == deadline
    assert clock[0] <= deadline + .051
    actual.close()


@pytest.mark.parametrize('watched', [False, True])
def test_watched_stop_reports_clearance_diagnostic_without_loosening_other_checks(watched):
    import time
    from bench.servo_runtime import stop_check
    head = SimpleNamespace(angle=0., halt=False, moving=False, sent=0., goal=0., error='',
                           motor=SimpleNamespace(), wait=lambda *args, **kwargs: None)
    def request(_kind):
        head.angle = 3.1640625
        head.motor.sent_at = head.motor.ack_at = time.monotonic()
        return 1
    head.request = request
    trace = []
    def note(kind):
        trace.append({'kind': kind})
    if watched:
        result = stop_check(head, trace, note, watched=True)
        assert not result['stop_excursion_target_met'] and result['watched']
    else:
        with pytest.raises(AssertionError, match='excursion'):
            stop_check(head, trace, note)
    assert trace[-1]['stop_maximum_sampled_degrees'] == 3.1640625
