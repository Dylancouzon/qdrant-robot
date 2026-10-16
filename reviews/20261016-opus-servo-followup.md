# Claude Code Review

Target: working tree diff

Now the new robot/servo.py.Reviewing the servo runtime diff; checking whether the servo's moving flag stays set inside the arrival tolerance in the bench traces.I found one finding that matters before the live robot uses the servo. I also found three minor ones. I could not run the tests because Bash is denied in this session, so this review comes from reading the code and the bench records.

## Should fix

**1. One bad supply reading stops the whole robot.**
- **Where:** `robot/servo.py:148` and `robot/main.py:374`.
- **What happens:** `SerialMotor.read` calls `safe(status)` on every 50 ms head tick. One reading outside 4.5–5.5 V records a head fault. That fault cannot be cleared without a restart. The new `check_health` check then makes `hear()` and `next_turn()` raise, so conversation and memory stop with the head.
- **Evidence:** The first trial's "before" status in `bench/results/2026-10-16-head-hardware-1792158881.json` reads **5.6 V** on the same 5 V / 4 A supply. That reading fails the current guard. `research/servo.md` says the cause of the trip in run 1792159743 is unknown and cites only 5.3–5.4 V readings. It does not mention the 5.6 V reading already in the evidence.
- **Why the limit is suspect:** The 5.5 V upper bound comes from the bench helper's policy. I believe the STS3215 itself is rated higher, but I did not check its datasheet. The trip is likely the supply sitting at the edge of the guard, not a real supply fault.
- **Fix:** Debounce the voltage check, for example two or three consecutive bad readings, or justify a wider upper bound. Keep the temperature, mode, and fault checks strict. Record the 5.6 V reading in `research/servo.md` as the probable cause.

## Minor

**2. `nudge` reads the start position before releasing torque** (`robot/servo.py:82`).
- The old order was `off()`, then read the start position. Now the start is read first, and `prepare()` releases torque afterwards.
- If torque was on and the servo sags when released, the new goal uses a stale start, and the servo jumps when torque comes back on.
- **Fix:** Move the start read after `self.off()`, or call `prepare` first and read the position after it.

**3. The bench Stop check can fail when the head is already at rest** (`bench/servo_runtime.py:97`).
- The new `Head._target` resets the goal only when the head is moving or outside the tolerance. A Stop on a stationary head therefore sends no new goal.
- `head.motor.sent_at` then comes from an earlier goal, so `dispatch` is negative and the assertion fails.
- This cannot happen in the current script, because Stop always lands mid-motion. It is a trap for later edits.

**4. Recall can describe a stale view** (`robot/main.py:2384–2388`).
- Sightings from other angles are now kept when their label is absent from `self.view`. Nothing checks `self.head.valid(self.view_taken)` first.
- While the head is moving, `self.view` can be an earlier frame. The robot can then say "it is not in view now" about an object that the new view shows.
- **Fix:** Use the label check only when the view is settled. Otherwise skip other-angle sightings, as the old code did.

## Checked and correct

- **Wake-rejected commands:** The `motion == -1` fix works. The other places that read `turn.motion` (lines 1334 and 1738) cannot treat -1 as a valid head command.
- **Shutdown order:** The ExitStack releases the microphone, then the camera, then the motor. Closing the head twice is safe because `SerialMotor.close` returns early after the first call.
- **Torque release on SIGTERM:** `Robot.close` closes the head first, so torque is released before the slow model shutdown. Repeated SIGTERM is ignored during cleanup, and the subprocess test covers it.
- **Moving flag at rest:** In the 10°/s trial, the servo's moving flag clears inside the deadband. The movement deadline therefore clears and does not trigger a false timeout.
- **Port locking:** Setting `exclusive` after the port opens takes the `flock` lock through pyserial 3.5's reconfigure path.

To confirm before you commit: run the mandatory pre-commit hook and the pinned-SDK command from `hardware/SERVO.md`.
