#!/usr/bin/env python3
"""Read or gently test one loose STS3215 through its USB bus adapter."""
import argparse
import json
import sys
from pathlib import Path

# Direct script invocation puts tools/ on sys.path instead of the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from robot.servo import connect


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
    from serial.tools import list_ports

    if args.command == "ports":
        for port in sorted(list_ports.comports(), key=lambda p: p.device):
            print(f"{port.device}  {port.description}  {port.hwid}")
        return
    with connect(args.port, args.id) as servo:
        if args.command == "nudge":
            print(json.dumps({**servo.nudge(args.degrees), "torque": servo.read(40)}))
        elif args.command == "off":
            servo.off()
            print("Torque off confirmed")
        else:
            print(json.dumps(servo.status()))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted. If shutdown was unconfirmed, disconnect servo power.", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
