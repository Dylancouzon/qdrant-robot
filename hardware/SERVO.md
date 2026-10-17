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

The helper first disables torque, sets speed and torque limits, and replaces any old goal with the current position. It verifies each write before enabling torque. It then sends the new goal. Arrival requires two stopped samples within five steps of the target. Movement has a three-second timeout, and serial writes have a 100 ms timeout.

The helper refuses moves across the saved position limits or encoder zero. For example, a negative five-degree move from position 55 would cross zero. Small position errors also mean equal positive and negative commands may not return exactly to the start. Read the reported `start`, `target`, and `reached` values; choose a smaller move if necessary.

To release the servo explicitly:

```sh
build/servo-venv/bin/python tools/servo.py --port "$SERVO_PORT" off
```

The helper attempts torque release on errors and Ctrl-C. If it prints **"Torque off is UNCONFIRMED"**, disconnect servo power. A broken USB connection prevents software from confirming release. Forced process termination also prevents cleanup.

## How the control works

### Mounted-head travel limits

The enclosure specifies **±70° from straight ahead for normal movement**, or **140° total travel**. Its mechanical stops are at **±80°**. Keep the 10° margin on each side; powered movement must stop before contact with a mechanical stop. These design limits come from [the enclosure requirements](https://github.com/Dylancouzon/qdrant-robot/blob/241aacc/hardware/DESIGN_REQUIREMENTS.md) and still need physical cable-clearance checks.

The mounted-head controller must enforce these absolute limits relative to a calibrated forward position. Repeated relative nudges accumulate, so the bench helper's per-command limit does not protect an assembled neck. Use this helper only with the loose servo. The runtime controller enforces absolute travel from explicit calibration.

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
- **Movement refused:** read status. The helper requires position mode, no fault, a stationary motor, 4.5–6.0 V reported voltage, and temperature below 60°C. It refuses unsupported position readings instead of changing calibration.
- **Movement timed out:** disconnect power and check for obstruction or insufficient power. The helper retains conservative torque limits.

## Verified scope

On 2026-10-15, this Mac read ID one, model 777, firmware 3.10, position mode, and 5.3–5.4 V servo feedback (E). With the reviewed helper, three successive moves reached targets 60, 21, and three at positions 55, 22, and seven (E). Every completed move confirmed torque off. The final position was four encoder steps, approximately 0.35°, from that run's starting position three. Saved registers zero through 39 were identical before and after. The [final-source run](../bench/results/2026-10-15-servo-bench-1792102797.jsonl) contains the commands, versions, source checksum, and readbacks. The [first run](../bench/results/2026-10-15-servo-bench-1792102525.jsonl) records the correctly rejected boundary crossing. An [intermediate run](../bench/results/2026-10-15-servo-bench-1792102553.jsonl) verified motion before the SDK transport fixes.

The Jetson runtime uses the same transport in [robot/servo.py](../robot/servo.py). Its [current checks and qualification limits](../research/servo.md#physical-runtime-checks) distinguish physical servo motion from simulated camera tests.

## Enable the runtime after calibration

`--servo-calibration PATH` enables the USB motor in `robot.main`. Startup without that option leaves head motion disabled. The file contains exactly `port`, `zero`, `direction`, and `limit`. Servo ID one and model 777 remain fixed.

- `port` identifies the adapter under `/dev/serial/by-id/`.
- `zero` is the measured forward encoder integer, from zero through 4,095.
- `direction` is one or minus one, verified against the mounted camera's rightward view.
- `limit` sets symmetric software travel in degrees, from one through 70. Start mounted checks at 10°.

The runtime rejects encoder-boundary crossings, saved-limit conflicts, and initial positions outside this range. It requires position mode, torque off, no reported fault, and a stationary servo. Feedback must report 4.5–6.0 V and temperature below 60°C.

The runtime readback window is 4.5–6.0 V. A known-good bench supply reported 5.6 V, above the original 5.5 V software ceiling. The 6 V ceiling remains within the confirmed 7.4 V variant's [manufacturer operating range](https://www.feetechrc.com/74v-19-kgcm-plastic-case-metal-tooth-magnetic-code-double-axis-ttl-series-steering-gear.html). The manufacturer specifies 6–7.4 V; our 5 V unloaded trial does not qualify mounted operation. Keep temperature, mode, fault, and unsafe-voltage checks immediate.

Startup preserves the measured position and primes its goal before enabling torque. It caps RAM torque at 20%, speed at 40°/s, and acceleration at 60. The loose-servo nudge keeps acceleration five. On this firmware, priming the current-position goal enables torque, so all RAM caps precede that write. The provisional arrival tolerance is 1.5°. Travel limits remain strict. Normal SIGTERM, faults, and shutdown attempt torque release. USB loss can prevent confirmation.

Keep temporary loose-servo calibration in `shared/experiments/`. After assembly, create `/home/qdrant/qdrant-robot/shared/servo-mounted.json` from measured forward position and direction. Follow [assembled testing](../research/servo.md#next-session-assembled-robot-testing) before enabling normal movement.

After calibration, launch from the Mac through the project workflow. The fresh token lets the existing monitor attach.

```sh
.venv/bin/python - <<'PYTHON'
import os
import secrets
from tools.jetson import run

os.environ["ROBOT_VIEW_TOKEN"] = secrets.token_hex(32)
raise SystemExit(run("robot", [
    "-m", "robot.main", "--servo-calibration",
    "/home/qdrant/qdrant-robot/shared/servo-mounted.json",
], False))
PYTHON
```

Then open the normal monitor for the deployed release and select **Start**. Stop the robot unit before changing calibration. A fault requires an explicit restart after its cause is resolved.

Run offline safety checks with the pinned SDK:

```sh
uv run --no-project --with pytest --with feetech-servo-sdk==1.0.0 --with pyserial==3.5 pytest -q robot/test_head.py robot/test_servo.py tools/test_servo.py
```
