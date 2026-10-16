"""Checked STS3215 transport and calibrated motor for the single head controller."""
import contextlib
import json
import math
import time
from pathlib import Path

SCALE = 4096 / 360
TOLERANCE = 1.0  # Provisional loose-servo precision; travel limits remain strict.
FEEDBACK_S = 0.3
SPEED = 10


class Servo:
    """Check SDK results at the hardware boundary; write RAM registers only."""

    def __init__(self, port, packet, servo_id):
        self.port, self.packet, self.id = port, packet, servo_id

    def check(self, result, error):
        if result != 0:
            raise RuntimeError(self.packet.getTxRxResult(result))
        if error:
            raise RuntimeError(f"Servo error 0x{error:02x}: {self.packet.getRxPacketError(error)}")

    def read(self, address, size=1):
        try:
            value, result, error = getattr(self.packet, f"read{size}ByteTxRx")(
                self.port, self.id, address)
        finally:
            self.port.is_using = False  # The SDK leaves this set on serial exceptions.
        self.check(result, error)
        return value

    def write(self, address, value, size=1):
        if address not in (40, 41, 42, 44, 46, 48):
            raise ValueError("Servo control writes RAM registers only")
        self._write(address, value, size)

    def _write(self, address, value, size=1):
        """Checked transaction; persistent setup has its own restricted caller."""
        try:
            result, error = getattr(self.packet, f"write{size}ByteTxRx")(
                self.port, self.id, address, value)
        finally:
            self.port.is_using = False
        self.check(result, error)
        if self.read(address, size) != value:
            raise RuntimeError(f"Register {address} did not retain {value}")

    def status(self):
        return {"id": self.id, "position": self.read(56, 2), "mode": self.read(33),
                "torque": self.read(40), "voltage_v": self.read(62) / 10,
                "temperature_c": self.read(63), "fault": self.read(65),
                "moving": self.read(66)}

    def off(self):
        try:
            self.write(40, 0)
        except Exception as exc:
            raise RuntimeError("Torque off is UNCONFIRMED. Disconnect servo power.") from exc

    def wait(self, target):
        deadline = time.monotonic() + 3
        stable = 0
        while time.monotonic() < deadline:
            position = self.read(56, 2)
            stopped = self.read(66) == 0
            stable = stable + 1 if abs(position - target) <= 5 and stopped else 0
            if stable >= 2:
                return position
            time.sleep(0.05)
        raise RuntimeError(f"Movement timed out at {position}, target {target}")

    def nudge(self, degrees):
        if not math.isfinite(degrees) or not 0 < abs(degrees) <= 10:
            raise ValueError("Use a nonzero relative angle of at most 10 degrees")
        delta = round(degrees * 4096 / 360)
        if delta == 0:
            raise ValueError("Angle is smaller than one encoder step")
        status = self.status()
        safe(status)
        if status["moving"]:
            raise RuntimeError("Require a stationary servo")
        try:
            self.off()
            start = self.read(56, 2)
            target = start + delta
            low, high = self.read(9, 2), self.read(11, 2)
            if not 0 <= low <= start <= high <= 4095 or not low <= target <= high:
                raise ValueError("Move crosses the saved position limits or encoder boundary")
            self.prepare(start, 100)
            self.write(40, 1)
            self.write(42, target, 2)
            reached = self.wait(target)
            return {"start": start, "target": target, "reached": reached,
                    "speed_steps_s": 100, "acceleration": 5,
                    "torque_limit": self.read(48, 2)}
        finally:
            self.off()

    def prepare(self, position, speed):
        """Cap RAM power and speed, then replace old goals before torque enable."""
        self.off()
        self.write(48, min(self.read(48, 2), 200), 2)
        self.write(41, 5)
        self.write(44, 0, 2)
        self.write(46, speed, 2)
        self.write(42, position, 2)


@contextlib.contextmanager
def connect(path, servo_id=1):
    """Open one exclusive, bounded serial connection without changing registers."""
    import scservo_sdk as scs

    port = scs.PortHandler(path)
    try:
        if not port.setBaudRate(1_000_000):
            raise RuntimeError("Could not open the port at 1 Mbaud")
        port.ser.exclusive = True
        port.ser.write_timeout = 0.1
        port.clearPort = port.ser.reset_input_buffer
        port.getCurrentTime = lambda: time.monotonic() * 1000
        servo = Servo(port, scs.PacketHandler(0), servo_id)
        model, result, error = servo.packet.ping(port, servo_id)
        servo.check(result, error)
        if model != 777:
            raise RuntimeError(f"Expected STS3215 model 777, got {model}")
        yield servo
    finally:
        if port.is_open:
            port.closePort()


def calibration(zero, direction, limit):
    if type(zero) is not int or not 0 <= zero <= 4095:
        raise ValueError("Calibration zero must be an encoder integer from 0 through 4095")
    if type(direction) is not int or direction not in (-1, 1):
        raise ValueError("Calibration direction must be -1 or 1")
    if type(limit) not in (int, float) or not math.isfinite(limit) or not 1 <= limit <= 70:
        raise ValueError("Calibration limit must be from 1 through 70 degrees")
    low, high = math.ceil(zero - limit * SCALE), math.floor(zero + limit * SCALE)
    if not 0 <= low < zero < high <= 4095:
        raise ValueError("Calibrated travel crosses the encoder boundary")
    return low, high


def safe(status):
    # The 5 V supply has reported 5.6 V; 6 V remains within the 7.4 V model rating.
    if status["mode"] != 0 or status["fault"]:
        raise RuntimeError("Require position mode and no servo fault")
    if not 4.5 <= status["voltage_v"] <= 6.0 or status["temperature_c"] >= 60:
        raise RuntimeError(f"Servo supply {status['voltage_v']} V, "
                           f"temperature {status['temperature_c']} C; "
                           "require 4.5..6.0 V and below 60 C")


class SerialMotor:
    """Use absolute calibrated travel, measured feedback, and latched failure shutdown."""
    tolerance = TOLERANCE
    resolution = 1 / SCALE

    def __init__(self, servo, zero, direction, limit):
        self.low, self.high = calibration(zero, direction, limit)
        self.servo, self.zero, self.direction, self.limit = servo, zero, direction, limit
        self.connection = None
        self.closed = self.enabled = False
        self.target = self.position = None
        self.feedback = self.deadline = self.progress = 0.
        self.distance = math.inf
        self.read(time.time())
        if self.status["torque"] or self.status["moving"]:
            raise RuntimeError("Require a stationary servo with torque off before startup")
        if not servo.read(9, 2) <= self.low < self.high <= servo.read(11, 2):
            raise ValueError("Calibration exceeds the servo saved travel limits")

    @classmethod
    def open(cls, path):
        config = json.loads(Path(path).read_text())
        if not isinstance(config, dict) or set(config) != {"port", "zero", "direction", "limit"}:
            raise ValueError("Require port, zero, direction, and limit in servo calibration")
        if not isinstance(config["port"], str) or not config["port"].startswith("/dev/"):
            raise ValueError("Calibration requires an explicit /dev/ serial port")
        calibration(config["zero"], config["direction"], config["limit"])
        connection = connect(config["port"])
        servo = connection.__enter__()
        try:
            motor = cls(servo, config["zero"], config["direction"], config["limit"])
        except BaseException:
            connection.__exit__(None, None, None)
            raise
        motor.connection = connection
        return motor

    def read(self, _now):
        started = time.monotonic()
        status = self.servo.status()
        finished = time.monotonic()
        if finished - started > FEEDBACK_S:
            raise RuntimeError("Servo feedback expired during read")
        self.status = status
        safe(status)
        if not self.low <= status["position"] <= self.high:
            raise RuntimeError("Servo feedback exceeds calibrated travel")
        if self.enabled and status["torque"] != 1:
            raise RuntimeError("Servo torque changed unexpectedly")
        self.position, self.feedback, self.status = status["position"], finished, status
        self.read_s = finished - started
        self._progress(finished)
        angle = self.direction * (self.position - self.zero) / SCALE
        return angle, bool(status["moving"])

    def _progress(self, now):
        if self.target is None:
            return
        distance = abs(self.target - self.position)
        if distance <= self.tolerance * SCALE:
            self.progress = now
            if not self.status["moving"]:
                self.deadline = None
        elif self.deadline is None:
            # Holding has no expired travel deadline. Watch a new displacement normally.
            self.progress, self.distance = now, distance
            self.deadline = now + distance / (SPEED * SCALE) + 2.
        elif distance < self.distance - 1:
            self.progress, self.distance = now, distance
        elif now - self.progress > 1.:
            raise RuntimeError("Servo movement stalled")
        if self.deadline is not None and now > self.deadline:
            raise RuntimeError("Servo movement timed out")

    def move(self, angle):
        if self.closed:
            raise RuntimeError("Servo is closed")
        if not math.isfinite(angle) or abs(angle) > self.limit:
            raise ValueError("Servo goal exceeds calibrated travel")
        if time.monotonic() - self.feedback > FEEDBACK_S:
            raise RuntimeError("Servo feedback is stale")
        target = round(self.zero + self.direction * angle * SCALE)
        target = max(self.low, min(self.high, target))
        if not self.enabled:
            self._enable()
        self.sent_at = time.monotonic()
        self.servo.write(42, target, 2)
        self.ack_at = time.monotonic()
        self.write_s = self.ack_at - self.sent_at
        self.target, self.progress = target, time.monotonic()
        self.distance = abs(target - self.position)
        self.deadline = self.progress + self.distance / (SPEED * SCALE) + 2.
        return self.direction * (target - self.zero) / SCALE

    def _enable(self):
        started = time.monotonic()
        self.servo.prepare(self.position, round(SPEED * SCALE))
        if time.monotonic() - started > 1.:
            raise RuntimeError("Servo startup transaction budget exceeded")
        self.servo.write(40, 1)
        self.enabled = True

    def close(self):
        if self.closed:
            return
        try:
            self.servo.off()
        finally:
            self.closed = True
            if self.connection:
                self.connection.__exit__(None, None, None)
