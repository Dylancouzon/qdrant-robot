"""Qualify the real loose servo through Head, using measured yaw for projected following."""
import argparse
import json
import os
import signal
import time
from pathlib import Path

from robot.config import SHARED
from robot.head import Head, Interrupted, interrupt
from robot.servo import SPEED, SerialMotor, connect


def wait_stopped(head, token):
    settled = head.wait(token, timeout=5)
    if head.error:
        raise RuntimeError(head.error)
    return settled


def exercise(head, trace):
    def note(kind):
        with head.condition:
            trace.append({"kind": kind, "time": time.time(), "angle": head.angle,
                          "goal": head.goal, "moving": head.moving, "error": head.error,
                          "feedback_s": head.motor.read_s,
                          "goal_write_s": getattr(head.motor, "write_s", None),
                          "encoder_goal": head.motor.target,
                          "encoder_position": head.motor.position,
                          "servo_moving": head.motor.status["moving"],
                          "settled": head.settled,
                          "feedback_monotonic": head.motor.feedback,
                          "goal_sent_monotonic": getattr(head.motor, "sent_at", None),
                          "goal_ack_monotonic": getattr(head.motor, "ack_at", None)})
    for goal in (5, -5, 0):
        started = time.monotonic()
        token = head.request("right" if goal > 0 else "left")
        head.move(goal, token)
        wait_stopped(head, token)
        note("inspection")
        trace[-1]["movement_s"] = time.monotonic() - started
        assert abs(head.angle - goal) <= head.tolerance
        head.finish(token)
    # A fixed visitor lies to the right. Its projected box follows measured motor yaw.
    following_started = time.monotonic()
    deadline = following_started + 8
    while time.monotonic() < deadline:
        if head.error:
            raise RuntimeError(head.error)
        if (not head.moving and head.sent == head.goal and
                head.angle >= head.limit - head.tolerance):
            break
        center = 640 + (20 - head.angle) * 15
        head.follow((center - 60, 100, center + 60, 220), 1280, time.time())
        note("following")
        time.sleep(.07)
    assert (not head.moving and head.sent == head.goal and
            head.angle >= head.limit - head.tolerance), "Following never settled at bench limit"
    note("following settled")
    trace[-1]["following_s"] = time.monotonic() - following_started
    view, sent_at = head.view, head.motor.sent_at
    for _ in range(10):
        assert head.follow((1000, 100, 1120, 220), 1280, time.time()) == "limit"
        time.sleep(.07)
        assert not head.error and head.view == view and head.motor.sent_at == sent_at
    note("following held limit")
    token = head.request("left")
    head.move(-head.limit, token)
    deadline = time.monotonic() + 2
    while head.angle > head.limit - 2 and time.monotonic() < deadline:
        if head.error:
            raise RuntimeError(head.error)
        time.sleep(.01)
    assert head.moving, "Stop test did not intercept motion"
    stop_result = stop_check(head, trace, note)
    try:
        head.move(0, token)
        raise AssertionError("Obsolete return was accepted")
    except Interrupted:
        pass
    assert not head.following
    token = head.request("left")
    head.move(0, token)
    wait_stopped(head, token)
    note("returned")
    return stop_result


def stop_check(head, trace, note):
    """Measure an intercepted move; the caller requires active motion."""
    before, started = head.angle, time.monotonic()
    stop = head.request("stop")
    maximum = 0.
    while True:
        note("stopping")
        maximum = max(maximum, abs(head.angle - before))
        if head.error:
            raise RuntimeError(head.error)
        if not head.halt and not head.moving and head.sent == head.goal:
            break
        if time.monotonic() - started > 2:
            raise RuntimeError("Stop did not settle within two seconds")
        time.sleep(.02)
    wait_stopped(head, stop)
    elapsed = time.monotonic() - started
    dispatch = head.motor.sent_at - started
    acknowledgement = head.motor.ack_at - started
    result = {"stop_request_monotonic": started, "stop_settled_s": elapsed,
              "stop_dispatch_s": dispatch, "stop_ack_s": acknowledgement,
              "stop_maximum_sampled_degrees": maximum,
              "stop_time_target_s": .3, "stop_time_target_met": elapsed <= .3}
    trace.append({"kind": "stop", **result})
    assert 0 <= dispatch <= .1, "Hold goal missed the first controller cycle"
    assert maximum <= 3, "Stop excursion exceeded three degrees"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("--hold", action="store_true", help="Wait for service SIGTERM")
    args = parser.parse_args()
    config = json.loads(args.calibration.read_text())
    assert config["limit"] <= 10, "Loose-servo qualification requires at most 10 degrees"
    result = {"release": os.environ.get("ROBOT_RELEASE"), "machine": "Jetson",
              "mode": "service-shutdown" if args.hold else "loose-servo",
              "calibration": config, "external_supply": "5 V / 4 A",
              "configured_speed_deg_s": SPEED,
              "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "trace": []}
    output = SHARED / "results" / (
        f"{time.strftime('%Y-%m-%d')}-head-hardware-{int(time.time())}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, interrupt)
    with connect(config["port"]) as device:
        before = [device.read(address) for address in range(40)]
        result["before"] = device.status()
    head = None
    try:
        head = Head(SerialMotor.open(args.calibration))
        head.start()
        wait_stopped(head, 0)
        print("servo ready", flush=True)
        if args.hold:
            while True:
                if head.error:
                    raise RuntimeError(head.error)
                time.sleep(.1)
        else:
            result.update(exercise(head, result["trace"]))
        result["status"] = "passed"
    except KeyboardInterrupt:
        result["status"] = "passed" if args.hold else "interrupted"
    except Exception as error:
        result["status"], result["error"] = "failed", repr(error)
        raise
    finally:
        if head:
            result["fault_status"] = head.motor.status
            head.close()
        result["head_error"] = head.error if head else result.get("error", "")
        with connect(config["port"]) as device:
            result["after"] = device.status()
            result["saved_registers_unchanged"] = before == [
                device.read(address) for address in range(40)]
        if (result["head_error"] or result["after"]["torque"] or result["after"]["moving"] or
                not result["saved_registers_unchanged"]):
            result["status"] = "failed"
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"result": str(output), "status": result["status"],
                          "head_error": result["head_error"]}), flush=True)
    assert result["status"] == "passed"


if __name__ == "__main__":
    main()
