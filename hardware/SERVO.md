# Control the STS3215 servo

Use [tools/servo.py](../tools/servo.py) to read and gently move one loose servo from a Mac or Linux computer. The helper uses the same small Feetech SDK package as LeRobot. It does not load LeRobot or the robot application.

## Connect the hardware

The tested hardware is a **Feetech STS3215, 7.4 V**, a **Waveshare Bus Servo Adapter (A)**, and an external **5 V DC, 4 A** supply. Dylan confirmed the servo version and supply. The board photo shows its model name along the left edge.

1. Switch off servo power before changing connections.
2. Connect the servo to either white three-pin port. Both ports serve the same bus.
3. Set both yellow jumpers to **B**, the USB control position.
4. Connect the adapter's USB-C port to the computer with a data cable.
5. Connect the external 5 V supply to the barrel jack. Check its polarity and 5.5 × 2.1 mm plug first.

The USB-C connection carries commands. The barrel jack supplies the servo. **Keep the 12 V supply away from this 7.4 V servo.** The board passes its input voltage to the servo; its printed "DC 9–12.6 V" label does not override the servo's voltage requirement. See [Waveshare's power explanation](https://docs.waveshare.com/Bus_Servo_Adapter_A/FAQ) and [LeRobot's supply instructions](https://huggingface.co/docs/lerobot/main/en/assemble_so101).

Use the external supply for this check. Power from a Jetson USB-A port remains unverified under movement.

## Install two small packages

Run these commands from the repository root. They create a separate environment under the ignored `build/` directory and leave the robot environment unchanged. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first if necessary.

```sh
uv venv --python 3.12 build/servo-venv
uv pip install --python build/servo-venv/bin/python feetech-servo-sdk==1.0.0 pyserial==3.5
build/servo-venv/bin/python tools/servo.py ports
```

Choose the adapter's USB serial port. Our Mac reports `/dev/cu.usbmodem5A460852871`, with USB vendor/product `1A86:55D3`. Linux commonly reports `/dev/ttyACM0`. Use the path printed on your computer.

## Read status first

Set `SERVO_PORT` to that path. This example uses our measured Mac port.

```sh
SERVO_PORT=/dev/cu.usbmodem5A460852871
build/servo-venv/bin/python tools/servo.py --port "$SERVO_PORT" status
```

The command only pings and reads registers. It uses **1,000,000 baud**, STS protocol **0**, and servo ID **1**. The helper checks model number **777** before continuing. For a previously configured servo, pass its known ID with `--id`, before `status`. The helper never changes IDs, baud rates, operating mode, or calibration.

An actual status response from our servo was:

```json
{"id": 1, "position": 3, "mode": 0, "torque": 0, "voltage_v": 5.4, "temperature_c": 27, "fault": 0, "moving": 0}
```

`mode: 0` means position control. `torque: 0` means the motor is released. `fault: 0` means no reported fault. Position uses 4,096 encoder steps per turn, approximately 0.088° per step. The encoder position does not establish which direction the robot faces.

## Test a small movement

Use this test only with a loose servo that has room to turn. Keep fingers and cables clear of the horn. Keep the supply switch accessible.

```sh
build/servo-venv/bin/python tools/servo.py --port "$SERVO_PORT" nudge 5
build/servo-venv/bin/python tools/servo.py --port "$SERVO_PORT" status
build/servo-venv/bin/python tools/servo.py --port "$SERVO_PORT" nudge -3
```

Each nudge moves relative to the measured position, waits for arrival, and releases torque. The shaft can move freely afterward. A nudge accepts at most 10° in either direction. It uses 100 steps/s, acceleration value five, and at most 20% torque. These conservative settings remain in RAM after the test.

The helper first disables torque, sets speed and torque limits, and replaces any old goal with the current position. It verifies each write before enabling torque. It then sends the new goal. Arrival requires two stopped samples within five steps of the target. Movement has a three-second timeout, and serial writes have a half-second timeout.

The helper refuses moves across the saved position limits or encoder zero. For example, a negative five-degree move from position 55 would cross zero. Small position errors also mean equal positive and negative commands may not return exactly to the start. Read the reported `start`, `target`, and `reached` values; choose a smaller move if necessary.

To release the servo explicitly:

```sh
build/servo-venv/bin/python tools/servo.py --port "$SERVO_PORT" off
```

The helper attempts torque release on errors and Ctrl-C. If it prints **"Torque off is UNCONFIRMED"**, disconnect servo power. A broken USB connection prevents software from confirming release. Forced process termination also prevents cleanup.

## How the control works

### Mounted-head travel limits

The enclosure specifies **±70° from straight ahead for normal movement**, or **140° total travel**. Its mechanical stops are at **±80°**. Keep the 10° margin on each side; powered movement must stop before contact with a mechanical stop. These design limits come from [the enclosure requirements](https://github.com/Dylancouzon/qdrant-robot/blob/241aacc/hardware/DESIGN_REQUIREMENTS.md) and still need physical cable-clearance checks.

The mounted-head controller must enforce these absolute limits relative to a calibrated forward position. Repeated relative nudges accumulate, so the bench helper's per-command limit does not protect an assembled neck. Use this helper only with the loose servo until mounted-head calibration and travel enforcement exist.

The SDK opens the serial port with `PortHandler` and uses `PacketHandler(0)`. The helper calls its register read/write methods and checks both communication results and servo error flags. Two-byte STS values use little-endian order; the SDK handles packet construction and checksums. The helper replaces the SDK's unbounded serial drain with an input-buffer reset and clears its busy flag after failed requests. This lets cleanup attempt another packet after a serial exception.

These addresses come from [LeRobot's STS control table at revision 297774f](https://github.com/huggingface/lerobot/blob/297774fca4e3ad0aa34e7425fbf937111637e77b/src/lerobot/motors/feetech/tables.py).

| Register | Address | Bytes | Use |
| --- | --- | --- | --- |
| Operating mode | 33 | 1 | Read; require position mode zero. |
| Torque enable | 40 | 1 | Write zero to release, or one to hold. |
| Acceleration | 41 | 1 | Write five for this bench check. |
| Goal position | 42 | 2 | Write an encoder target from zero through 4,095. |
| Goal time | 44 | 2 | Write zero to remove a previous timed-move setting. |
| Goal velocity | 46 | 2 | Write 100 steps/s. Zero selects maximum speed. |
| Torque limit | 48 | 2 | Cap at 200 out of 1,000; preserve a lower existing limit. |
| Present position | 56 | 2 | Read the encoder position. |
| Present voltage | 62 | 1 | Read tenths of a volt. |
| Present temperature | 63 | 1 | Read degrees Celsius. |
| Status | 65 | 1 | Read fault bits. |
| Moving | 66 | 1 | Read zero for stopped. |

All helper writes target RAM registers. It leaves EEPROM settings, including the center offset, untouched. Full LeRobot installation, firmware changes, and a separately programmed microcontroller are unnecessary for this bench check.

## Troubleshooting

- **No serial port:** check the USB data cable and computer USB connection.
- **No status response:** check external power, both jumpers at B, the servo lead, and the known servo ID. Close other programs using the port.
- **Linux permission denied:** give your user access through the serial device's group, commonly `dialout`, then sign in again.
- **Movement refused:** read status. The helper requires position mode, no fault, a stationary motor, 4.5–5.5 V reported voltage, and temperature below 60°C. It refuses unsupported position readings instead of changing calibration.
- **Movement timed out:** disconnect power and check for obstruction or insufficient power. The helper retains conservative torque limits.

## Verified scope and main-branch handoff

On 2026-10-15, this Mac read ID one, model 777, firmware 3.10, position mode, and 5.3–5.4 V servo feedback (E). With the reviewed helper, three successive moves reached targets 60, 21, and three at positions 55, 22, and seven (E). Every completed move confirmed torque off. The final position was four encoder steps, approximately 0.35°, from that run's starting position three. Saved registers zero through 39 were identical before and after. The [final-source run](../bench/results/2026-10-15-servo-bench-1792102797.jsonl) contains the commands, versions, source checksum, and readbacks. The [first run](../bench/results/2026-10-15-servo-bench-1792102525.jsonl) records the correctly rejected boundary crossing. An [intermediate run](../bench/results/2026-10-15-servo-bench-1792102553.jsonl) verified motion before the SDK transport fixes.

For main, take this guide, `tools/servo.py`, `tools/test_servo.py`, the three linked run records, and the README link. These files have no enclosure-code dependency. Run the offline checks without connecting hardware:

```sh
.venv/bin/python -m pytest -q tools/test_servo.py
```

To include the regression check against the real SDK, run:

```sh
uv run --no-project --with pytest --with feetech-servo-sdk==1.0.0 --with pyserial==3.5 pytest -q tools/test_servo.py
```

Jetson control, USB-port power, loaded motion, and mounted-head travel remain unverified (U). Before runtime integration, establish the head's forward position, direction, software travel limits, and cable clearance. The bench helper provides no mounted-head calibration.
