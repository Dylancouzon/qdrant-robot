"""Apply or verify Dylan's approved one-time STS3215 mounted-forward offset."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from robot.config import SHARED
from robot.head import interrupt
from robot.servo import connect, safe

PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46085287-if00"
BACKUP_SHA = "46f3b14bb835f8c130b95694fa1c3ef684f07c382c1cf39aad52cb57b4e80a33"
OFFSET = 2018


def save(path, record):
    """Flush the operation record before any persistent write."""
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as file:
        file.write(json.dumps(record, indent=2) + "\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def expected(backup, offset):
    saved = backup["saved_registers_0_39"].copy()
    saved[31:33] = [offset & 255, offset >> 8]
    return saved


def status(servo):
    started = time.monotonic()
    state = servo.status()
    if time.monotonic() - started > .3:
        raise RuntimeError("Setup status read exceeded the 0.3 second budget")
    safe(state)
    return started, state


def stationary(servo, offset):
    samples = []
    center = 4065 - offset
    for _ in range(20):
        started, state = status(servo)
        if (state["torque"] or state["moving"] or state["id"] != 1 or
                abs(state["position"] - center) > 2):
            raise RuntimeError(f"Unsafe or displaced mounted pose: {state}")
        samples.append({"monotonic": started, **state})
        time.sleep(.05)
    positions = [sample["position"] for sample in samples]
    if max(positions) - min(positions) > 2:
        raise RuntimeError("Mounted pose is not stationary within two encoder steps")
    return samples


def inspect(servo, backup, offset):
    samples = stationary(servo, offset)
    saved = [servo.read(address) for address in range(40)]
    lock, goal = servo.read(55), servo.read(42, 2)
    if saved != expected(backup, offset) or lock != 1 or goal != backup["goal"]:
        raise RuntimeError("Saved settings, firmware, lock, or RAM goal changed")
    # Recheck live guards after the saved-register reads, immediately before unlocking.
    started, state = status(servo)
    if state["torque"] or state["moving"] or abs(state["position"] - (4065 - offset)) > 2:
        raise RuntimeError(f"Mounted pose changed during inspection: {state}")
    return {"samples": samples, "saved": saved, "lock": lock, "goal": goal, "status": state,
            "checked_monotonic": started}


def setting(servo, address, value):
    """Permit only the approved offset, its original value, and lock transitions."""
    if (address, value) not in ((55, 0), (55, 1), (31, OFFSET), (31, 0)):
        raise ValueError("Unapproved setup write")
    servo._write(address, value, 2 if address == 31 else 1)


def change(servo, backup, operation, record, output):
    if operation not in ("apply", "verify", "rollback"):
        raise ValueError("Unknown setup operation")
    old = 0 if operation == "apply" else OFFSET
    record["before"] = inspect(servo, backup, old)
    save(output, record)
    if operation != "verify":
        record["write_attempted"] = True
        save(output, record)
        failures = []
        try:
            if time.monotonic() - record["before"]["checked_monotonic"] > .3:
                raise RuntimeError("Setup preflight expired before unlocking")
            setting(servo, 55, 0)
            setting(servo, 31, OFFSET if operation == "apply" else 0)
        except BaseException as error:
            failures.append(error)
        finally:
            for cleanup in (lambda: setting(servo, 55, 1), servo.off):
                try:
                    cleanup()
                except BaseException as error:
                    failures.append(error)
        if failures:
            record["errors"] = ["".join(traceback.format_exception(error)) for error in failures]
            raise RuntimeError("Setup or cleanup uncertain. Disconnect servo power. "
                               "Reconcile read-only; do not retry.")
    new = 0 if operation == "rollback" else OFFSET
    record["after"] = inspect(servo, backup, new)
    record["status"] = "passed"
    save(output, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("apply", "verify", "rollback"))
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    raw = args.backup.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BACKUP_SHA:
        parser.error("Require the original approved register backup")
    backup = json.loads(raw)
    output = SHARED / "results" / (
        f"{time.strftime('%Y-%m-%d')}-mounted-center-{time.time_ns()}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {"operation": args.operation, "status": "incomplete", "write_attempted": False,
              "machine": "Jetson", "release": os.environ.get("ROBOT_RELEASE"),
              "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "command": sys.argv,
              "backup": str(args.backup), "backup_sha256": BACKUP_SHA,
              "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
              "dependencies": {name: importlib.metadata.version(name)
                               for name in ("feetech-servo-sdk", "pyserial")}}
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    save(output, record)
    try:
        with connect(PORT) as servo:
            change(servo, backup, args.operation, record, output)
    except BaseException as error:
        record.update(status="failed", error=repr(error))
        save(output, record)
        print(f"Failed: {error}. Disconnect servo power. Movement is prohibited; "
              f"inspect {output}.", file=sys.stderr)
        raise
    print(json.dumps({"result": str(output), "status": record["status"],
                      "position": record["after"]["status"]["position"], "torque": 0}))


if __name__ == "__main__":
    main()
