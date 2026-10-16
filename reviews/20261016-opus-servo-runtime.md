# Claude Code Review

Target: working tree diff

I am reading the new servo runtime and its integration in `robot/main.py`. Next I check shutdown order and the head control loop.I reviewed the code changes and the bench records. The new runtime has no blocking defect for loose-servo bench work. Finding 1 needs a fix before mounted or booth use.

## Findings

**1. High: one transient head fault turns off object recognition until restart** (`robot/head.py:219`, `robot/servo.py:148`)
- Any exception in `SerialMotor.read` sets `head.error` for the rest of the session. After that, `Head.valid()` returns False for every frame. This stops the object query (`robot/main.py:791`), sightings (`robot/main.py:1053`), and side answers (`robot/main.py:2469`) until a restart.
- The bench records show such a fault can come from a power reading alone. Hold trial `1792159743` stopped on the voltage guard without any motion, and the readings before and after were 5.4 V. The status read before trial `1792158881` reported 5.6 V, which is above the 5.5 V limit in `safe()`.
- `safe()` runs on every 50 ms tick, so one out-of-range sample is enough to trip the fault.
- Recommendation: count a guard failure only after several consecutive bad readings. Also separate "motion is off" from "the view angle is unknown". After torque release, the controller can continue to read the position without writing. `valid()` can then stay True while the head is stationary.

**2. Medium: a small push after arrival causes an immediate fault** (`robot/servo.py:218`)
- `self.deadline` is set only in `move()`. After the head settles, no new goal is written while it holds still.
- If a visitor, cable tension, or the load moves the head more than 1° (11 encoder steps), the deadline has already passed. The next read then raises "Servo movement timed out" and latches finding 1.
- This is likely on a mounted head, because the torque is capped at 20%.
- Recommendation: run the deadline check only while a commanded movement is in progress. While holding, rewrite the goal or allow the 1 s stall window first.

**3. Low: a failed torque release at shutdown exits without an error status** (`robot/head.py:232`)
- `_close_motor` catches "Torque off is UNCONFIRMED" and prints it to stderr. `Robot.close()` then calls `check_health()`, which does not check `head.error`, so `main` returns normally.
- The bench script catches this case through `head_error`. The production service does not.
- Recommendation: raise after cleanup when `head.error` contains the unconfirmed-release text.

**4. Low: the records are behind the evidence** (`research/servo.md`)
- The section ends at the third trial and the first hold trial. Three later results are not recorded:
  - Trial `1792159934` failed with "Stop excursion exceeded three degrees".
  - Trial `1792160221` passed, with Stop settling in 0.554 s against the 0.3 s target.
  - Hold trial `1792160240` passed.
- The new runtime check removed the assertion on the Stop time, the check that failed trial `1792159643`. The docs say this, and the 0.3 s target stays visible. Add one line per run so that the excursion failure is not lost.

**5. Note: 10°/s makes inspection slow** (`robot/servo.py:11`)
- A 45° inspection takes at least 4.5 s each way, plus the return. This is a deliberate safety cap, and the docs already say inspection latency misses the target.
- Name `SPEED` as the setting to change during mounted qualification.

## Checks that hold

- The shared `Servo` and `connect` transport removes about 100 duplicated lines from `tools/servo.py`. It also gives the CLI the exclusive lock and the 100 ms write timeout.
- The `ExitStack` order releases the motor last when `Robot()` fails, and `test_live_model_startup_failure_releases_motor` tests this. `Robot.close()` releases the head before it joins the other threads.
- The `interrupt` handler ignores repeated SIGTERM, which fixes the cleanup that a second SIGTERM interrupted. The subprocess test covers this.
- `move()` returns the actual encoder angle, and `goal` takes that value. This removes the rounding mismatch that blocked following in trial `1792158881`. Each angle in `read()` and `move()` is computed by one expression from integer encoder values, so the exact float comparison `sent == goal` is reliable.
- Calibration validation, saved-limit checks, stale-feedback refusal, and the order of steps before torque enable all have tests that confirm no write happens on a bad path.

I could not run the tests in read-only mode, so I did not verify that they pass.
