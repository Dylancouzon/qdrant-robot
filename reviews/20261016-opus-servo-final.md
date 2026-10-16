# Claude Code Review

Target: working tree diff

Reading `robot/main.py` next, to check how the head is wired in and the new sightings filter.Checking the latest hardware trace for the servo's moving flag while it holds position.I reviewed the full diff. I found one regression to fix before you commit, plus four smaller items.

**Note:** The working tree changed while I reviewed it. A new passing result appeared (`2026-10-16-head-hardware-1792162158.json`, release `e9471078186d`), and someone loosened the pass check in `bench/servo_runtime.py:50-58`. This review covers the tree as it is now.

## Fix before commit

**1. A follow-up can now be dropped while the robot is still answering** (`robot/main.py:466-474` and `robot/main.py:1331`)
- `_motion_request` runs when the line is transcribed. It extends `last_line` only for turns that used the wake phrase. Follow-ups without the wake phrase do not extend it.
- When a turn falls outside the 60 s window, the code sets `turn.motion = -1`. `_turn` then rejects that turn and does not check the window again.
- Before this diff, `_turn` checked the window after the previous answer had finished and updated `last_line`.
- Example: the last answer ended at L. Follow-up B arrives at L+50 and plays a long answer until L+67. The visitor says "look left" at L+61. 61 is more than 60, so the turn is marked -1 and dropped. The old code accepted it, because by then `last_line` was L+67.
- **Fix:** in `_motion_request`, set `last_line = max(last_line, speech_end)` for every accepted turn, not only woken turns. This keeps the -1 block for head commands. Add a test for the case of a follow-up spoken during another follow-up's answer.

## Smaller items

**2. Following stops up to 1° short of the travel limit** (`robot/head.py:165`)
- `follow()` returns "limit" when the new goal is within the 1° tolerance of the current angle. The head then never sends the goal at the limit.
- The latest passing run settled with goal 7.646° and angle 7.031°, against an 8° limit.
- The bench now passes because the check was loosened to `angle >= limit - tolerance`. The "following held limit" step passes for the same reason, not because the goal reached the limit.
- At ±70° this is harmless. But the bench no longer tests that following reaches the limit. Either accept and document the 1° shortfall, or check the tolerance against the clamped goal only.

**3. After a fault, shutdown does not try torque-off again** (`robot/servo.py:258-266`)
- A tick fault calls `motor.close()`. That sets `closed = True` and closes the port in `finally`, even when `off()` raised.
- `Head.close()` at shutdown then does nothing. A short serial glitch therefore leaves torque status unconfirmed with no second attempt. The error message does tell the operator to disconnect power.

**4. One voltage reading out of range stops the whole robot** (`robot/servo.py:146-153`, `robot/main.py:374`)
- `safe()` runs on every 50 ms readback with no debounce. A head fault now makes `check_health` raise for every input.
- This matches the documented choice. `STATE.md` already lists the intermittent supply-guard trips as open. Measure loaded voltage dips on the mounted head before unattended use.

**5. `STATE.md` names an old release**
- It names `1fddd451b236` as the validated hardware release. The boundary fixes came later, in releases `1135cdf4ca7a` and `e9471078186d`, and `e9471078186d` has the latest passing hardware run.
- The research notes do not mention the latest failing run (`1792161973`) or the change to the pass check.

**Nits:** In `robot/servo.py`, `Servo.nudge` calls `off()` and then `prepare()`, which calls `off()` again. Line 97 has an extra blank line.

## What checks out

- Repeated SIGTERM during cleanup is now ignored, and a subprocess test covers it.
- Startup checks the motor before it enables torque: calibration, saved limits, and stationary with torque off. It writes the current position as the goal before torque goes on.
- Shutdown order releases the motor last, and a test covers it.
- Goal rounding to encoder steps (`sent = actual`, then `goal = sent`) settles without repeated writes.
- The new sightings rule changes nothing when no motor is attached, because every sighting then has view angle 0.
- I found no lock-order problem between `detecting` and the head lock.
- The `attention.py` change only adds a comment and new message text. The selection logic is the same as before.

I could not run the tests, because Bash is blocked in this session.
