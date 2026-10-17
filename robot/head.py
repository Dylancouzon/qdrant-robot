"""Bounded following and inspection. Only this controller owns its motor."""
import math
import re
import signal
import sys
import threading
import time

LIMIT = 70.0
INSPECT = 45.0
FRESH_S = 0.3
SETTLE_S = 0.1
PERIOD_S = 0.05
REVERSE_S = 0.25


def interrupt(signum, _frame):
    """Let normal cleanup release the motor on service SIGTERM."""
    signal.signal(signum, signal.SIG_IGN)
    raise KeyboardInterrupt


class Interrupted(RuntimeError):
    pass


def command(text):
    line = text.lower().strip(" .!?")
    if re.fullmatch(r"(?:please )?stop(?: moving| following(?: me)?)?", line):
        return "stop"
    if re.fullmatch(r"(?:please )?look (left|right)", line):
        return line.split()[-1]
    match = re.fullmatch(r"what(?: is|'s) (?:on|to) your (left|right)(?: side)?", line)
    return match[1] if match else None


class SimMotor:
    """Advance measured angle at a finite speed; tests render their camera from this readback."""

    def __init__(self, angle=0.0, speed=20.0):
        if not math.isfinite(angle) or abs(angle) > LIMIT or not 0 < speed <= 40:
            raise ValueError("Require a bounded initial angle and speed up to 40 degrees/s")
        self.angle, self.speed, self.target, self.last = angle, speed, angle, None
        self.goals = []

    def read(self, now):
        elapsed = 0 if self.last is None else max(0, now - self.last)
        delta = self.target - self.angle
        self.angle += math.copysign(min(abs(delta), self.speed * elapsed), delta)
        self.last = now
        return self.angle, abs(self.target - self.angle) > .01

    def move(self, angle):
        if not math.isfinite(angle) or abs(angle) > LIMIT:
            raise ValueError("Motor goal exceeds travel")
        self.target = angle
        self.goals.append(angle)

    def close(self):
        self.target = self.angle


class Head:
    def __init__(self, motor=None, blocked=lambda: False):
        self.motor, self.blocked = motor, blocked
        self.limit = min(LIMIT, getattr(motor, "limit", LIMIT))
        self.tolerance = getattr(motor, "tolerance", .1)
        self.condition = threading.Condition(threading.RLock())
        self.angle = self.goal = 0.0
        self.generation = self.view = 0
        self.changed = self.settled = 0.0
        self.following, self.inspecting, self.halt = True, False, False
        self.paused = False
        self.moving, self.error, self.closed = False, "", False
        self.sent, self.stationary = None, None
        self.source = self.follow_after = 0.
        self.follow_direction, self.reverse_since = 0, None
        self.valid_after = 0.
        self.expires = None
        self.cooling = False
        self.awaiting_motion = False
        self.thread = None
        self.release_confirmed = None  # None before close, False after failure, True after success

    @property
    def fatal_error(self):
        with self.condition:
            return self.error if self.release_confirmed is not True else ""

    @property
    def view_angle(self):
        with self.condition:
            return None if self.error else self.angle

    @property
    def warning(self):
        with self.condition:
            if self.error and self.release_confirmed is True:
                return ("Head motor stopped after a fault. Motor off; restart to enable movement. "
                        "I can still see and talk.")
            if not self.cooling:
                return ""
            if self.motor.thermal_latched:
                return ("Head motor reported at least 70°C. Motor off; restart after cooling. "
                        "I can still see and talk.")
            remaining = math.ceil(max(0, self.motor.cooldown_until - time.monotonic()))
            wait = (f"{remaining} seconds minimum." if remaining else
                    "Waiting for safe temperature.")
            return f"Head motor cooling. {wait} I can still see and talk."

    def start(self):
        if self.motor is not None:
            self.tick(time.time())
            self.thread = threading.Thread(target=self._run, name="head", daemon=True)
            self.thread.start()

    def _run(self):
        while True:
            with self.condition:
                if self.closed:
                    return
                self.condition.wait(PERIOD_S)
            self.tick(time.time())

    def request(self, kind):
        """Invalidate old motion before a queued answer can resume or return."""
        with self.condition:
            self.generation += 1
            self.follow_after = time.time()
            self.expires = None
            self.follow_direction, self.reverse_since = 0, None
            self.halt = self.motor is not None and not self.error
            self.inspecting = kind != "stop" and not self.error
            if kind == "stop":
                self.following = False
            self.condition.notify_all()
            return self.generation

    def activate(self, generation):
        with self.condition:
            if self.error and self.release_confirmed is True and \
                    generation == self.generation and not self.closed:
                return
            self._current(generation)
            self.following = True

    def tick(self, now):
        with self.condition:
            if self.motor is None or self.closed or self.error:
                return
            try:
                self._tick(now)
            except Exception as error:
                self.error = str(error) or type(error).__name__
                self.following, self.inspecting = False, False
                self.generation += 1
                self.expires = None
                self._close_motor()
                if self.release_confirmed is True:
                    self.cooling, self.moving, self.halt = False, False, False
                    self.goal = self.sent = self.angle
                    self.view += 1
                    self.changed = time.time()
                    self.settled = self.valid_after = self.changed + SETTLE_S
                    print(f"{self.warning} Fault: {self.error}", flush=True)
            self.condition.notify_all()

    def _tick(self, now):
        angle, moving = self.motor.read(now)
        if not math.isfinite(angle) or abs(angle) > self.limit + .1:
            raise RuntimeError("Head feedback exceeds calibrated travel")
        if self.sent is None:
            self.goal = angle
        self.angle = angle
        if self._thermal(angle, moving, now):
            return
        if self.awaiting_motion:
            self.goal = self.sent = angle
            self.halt = False
            self._settle(angle, moving, now)
            return
        if self.expires is not None and now > self.expires:
            self.halt, self.expires = True, None
            self.reverse_since = None
        blocked = self.blocked()
        if blocked or self.paused:
            self.reverse_since = None
        target = self._target(angle, moving, blocked)
        if target != self.sent:
            if not math.isfinite(target) or abs(target) > self.limit:
                raise RuntimeError("Head goal exceeds calibrated travel")
            actual = self.motor.move(target)
            self.sent = target if actual is None else actual
            if self.goal == target:
                self.goal = self.sent
            moving = True
        self._settle(angle, moving, now)

    def _settle(self, angle, moving, now):
        if moving or abs(self.goal - angle) > self.tolerance:
            if not self.moving:
                self.view += 1
                self.changed = now
            self.moving, self.stationary = True, None
        else:
            self.stationary = now if self.stationary is None else self.stationary
            if self.moving and now - self.stationary >= SETTLE_S:
                self.moving, self.settled = False, now

    def _thermal(self, angle, moving, now):
        cooling = getattr(self.motor, "cooling", False)
        if cooling != self.cooling:
            self.cooling = cooling
            self.awaiting_motion = True
            self.generation += 1
            self.follow_after = self.valid_after = time.time()
            self.expires = None
            self.follow_direction, self.reverse_since = 0, None
            self.inspecting, self.halt = False, False
            self.goal = self.sent = angle
            self.view += 1
            self.changed, self.stationary, self.moving = now, None, True
            print(self.warning if cooling else
                  "Head motor cooled; waiting for fresh movement input.", flush=True)
        if cooling:
            self.goal = self.sent = angle
            self.halt, self.moving, self.stationary = False, moving, None
        return cooling

    def _target(self, angle, moving, blocked):
        pending = self.goal != self.sent
        if self.halt or (blocked and not self.inspecting):
            if pending or moving or abs(self.goal - angle) > self.tolerance:
                self.goal = angle
            self.halt = False
        braking = blocked and (pending or moving or abs(self.goal - angle) > self.tolerance)
        target = angle if braking else self.goal
        return target

    def follow(self, box, width, taken, now=None, generation=None):
        """Refresh a bounded correction from a fresh, uniquely verified face."""
        now = time.time() if now is None else now
        with self.condition:
            if generation is not None and generation != self.generation:
                return "cancelled source"
            if reason := self._follow_hold(taken, now):
                return reason
            if taken - self.source > FRESH_S:
                self.reverse_since = None
            self.source, self.expires = taken, taken + FRESH_S
            error = (box[0] + box[2]) / (2 * width) - .5
            if abs(error) > .12:
                delta = max(-6., min(6., 48 * error))
                direction = 1 if delta > 0 else -1
                if self._reversal_wait(direction, now):
                    self.condition.notify_all()
                    return "reversal pause"
                goal = max(-self.limit, min(self.limit, self.angle + delta))
                if abs(goal - self.angle) <= self.tolerance:
                    if delta * (self.goal - self.angle) < 0:
                        self.halt = True
                        self.condition.notify_all()
                        return "reversal"
                    return "limit"
                if abs(goal - self.goal) < getattr(self.motor, "resolution", 0.):
                    return "limit"
                self.goal = goal
                self.follow_direction, self.reverse_since = direction, None
                self.awaiting_motion = False
                self.condition.notify_all()
                return "goal"
            self.hold(generation)
            return "centered"

    def _reversal_wait(self, direction, now):
        """Brake once, then require stationary time and repeated opposite face evidence."""
        if direction != -self.follow_direction:
            self.reverse_since = None
            return False
        if self.reverse_since is None:
            self.reverse_since = now
            self.halt = self.moving or self.goal != self.sent
        return (self.moving or self.stationary is None or
                now - max(self.reverse_since, self.stationary) < REVERSE_S)

    def _follow_hold(self, taken, now):
        states = ((not self.following, "stopped"), (self.paused, "conversation"),
                  (self.cooling, "cooling"),
                  (self.inspecting, "inspection"), (self.halt, "settling"),
                  (bool(self.error), "fault"), (self.blocked(), "microphone suppressed"),
                  (not max(self.source, self.follow_after) < taken <= now or
                   now - taken > FRESH_S, "stale source"))
        return next((reason for held, reason in states if held), "")

    def hold(self, generation=None, taken=None):
        with self.condition:
            if taken is not None and taken <= self.source:
                return
            if (generation is None or generation == self.generation) and not self.inspecting:
                self.reverse_since = None
                if taken is not None:
                    self.source = taken
                self.expires = None
                self.halt = self.moving or self.goal != self.sent
                self.condition.notify_all()

    def move(self, angle, generation):
        with self.condition:
            self._current(generation)
            if self.cooling:
                raise RuntimeError(self.warning)
            if not math.isfinite(angle):
                raise ValueError("Head goal must be finite")
            if self.motor is None:
                raise RuntimeError("Head movement is disabled until calibration.")
            self.goal, self.halt = max(-self.limit, min(self.limit, angle)), False
            self.awaiting_motion = False
            self.inspecting = True
            self.condition.notify_all()

    def wait(self, generation, timeout=20):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                self._current(generation)
                if self.cooling:
                    raise RuntimeError(self.warning)
                if not self.halt and self.sent == self.goal and not self.moving:
                    return self.settled
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.request("stop")
                    raise RuntimeError("Head movement timed out.")
                self.condition.wait(min(.1, remaining))

    def _current(self, generation):
        if generation != self.generation or self.closed:
            raise Interrupted("Head movement was cancelled.")
        if self.error:
            raise RuntimeError(self.warning or self.error)

    def resume(self, generation):
        with self.condition:
            self._current(generation)
            self.inspecting = False

    def finish(self, generation):
        """Release a turn atomically even when Stop or shutdown took ownership meanwhile."""
        with self.condition:
            if generation == self.generation and not self.closed:
                self.inspecting = False
            self.paused = False

    def valid(self, taken, view=None):
        with self.condition:
            if self.error:
                return (self.release_confirmed is True and taken >= self.valid_after and
                        (view is None or view == self.view))
            if self.motor is None:
                return True
            return (not self.error and not self.cooling and not self.moving and
                    not self.halt and taken >= max(self.settled, self.valid_after)
                    and (view is None or view == self.view))

    def close(self):
        self.request("stop")
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        if self.thread:
            self.thread.join()
        if self.motor:
            self._close_motor()

    def _close_motor(self):
        if self.release_confirmed is not None:
            return
        self.release_confirmed = False
        try:
            self.motor.close()
            self.release_confirmed = True
        except Exception as error:
            self.error = f"{self.error}; {error}".strip("; ")
            print(self.error, file=sys.stderr, flush=True)
