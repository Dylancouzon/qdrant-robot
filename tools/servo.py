#!/usr/bin/env python3
"""Read or gently test one loose STS3215 through its USB bus adapter.

Install the two pinned SDK dependencies as described in hardware/SERVO.md.
"""
import argparse
import json
import math
import sys
import time


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
            raise ValueError("Only the bench test's RAM registers can be written")
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
        if status["mode"] != 0 or status["fault"] or status["moving"]:
            raise RuntimeError("Require position mode, no fault, and a stationary servo")
        if not 4.5 <= status["voltage_v"] <= 5.5 or status["temperature_c"] >= 60:
            raise RuntimeError("Require a 5 V supply and temperature below 60 C")
        try:
            self.off()
            start = self.read(56, 2)
            target = start + delta
            low, high = self.read(9, 2), self.read(11, 2)
            if not 0 <= low <= start <= high <= 4095 or not low <= target <= high:
                raise ValueError("Move crosses the saved position limits or encoder boundary")
            # RAM: 20% maximum torque, slow acceleration, no timed-move override.
            self.write(48, min(self.read(48, 2), 200), 2)
            self.write(41, 5)
            self.write(44, 0, 2)
            self.write(46, 100, 2)
            self.write(42, start, 2)  # Replace any old goal before torque is enabled.
            self.write(40, 1)
            self.write(42, target, 2)
            reached = self.wait(target)
            return {"start": start, "target": target, "reached": reached,
                    "speed_steps_s": 100, "acceleration": 5,
                    "torque_limit": self.read(48, 2)}
        finally:
            self.off()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Explicit USB serial device; use 'ports' to list")
    parser.add_argument("--id", type=int, default=1, choices=range(254), metavar="0..253")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("ports", "status", "off"):
        commands.add_parser(name)
    nudge = commands.add_parser("nudge", help="Loose bench servo; releases torque afterward")
    nudge.add_argument("degrees", type=float)
    args = parser.parse_args()
    if args.command != "ports" and not args.port:
        parser.error("--port is required")

    # Lazy imports let offline safety tests run without installing the hardware SDK.
    import scservo_sdk as scs
    from serial.tools import list_ports

    if args.command == "ports":
        for port in sorted(list_ports.comports(), key=lambda p: p.device):
            print(f"{port.device}  {port.description}  {port.hwid}")
        return
    port, packet = scs.PortHandler(args.port), scs.PacketHandler(0)
    try:
        if not port.setBaudRate(1_000_000):
            raise RuntimeError("Could not open the port at 1 Mbaud")
        port.ser.write_timeout = 0.5
        # SDK clearPort uses flush/tcdrain, which has no write timeout. Discard stale RX
        # bytes instead; pyserial write already transmits each complete SDK packet.
        port.clearPort = port.ser.reset_input_buffer
        servo = Servo(port, packet, args.id)
        model, result, error = packet.ping(port, args.id)
        servo.check(result, error)
        if model != 777:
            raise RuntimeError(f"Expected STS3215 model 777, got {model}")
        if args.command == "nudge":
            print(json.dumps({**servo.nudge(args.degrees), "torque": servo.read(40)}))
        elif args.command == "off":
            servo.off()
            print("Torque off confirmed")
        else:
            print(json.dumps(servo.status()))
    finally:
        if port.is_open:
            port.closePort()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted. If shutdown was unconfirmed, disconnect servo power.", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
