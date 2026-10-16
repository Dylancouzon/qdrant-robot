# Claude Code Review

Target: working tree diff

I am reviewing the servo and head changes now; next I check how `Robot` takes ownership of the injected head.I am checking one possible regression: the new wake rejection runs at transcription time, before the previous answer updates `last_line`.The diff has two blocking bugs and one hardware risk. The servo extraction, the startup cleanup order, the SIGTERM handling, and the head-fault reporting look correct.

**Verdict:** Fix findings 1 and 2 before commit.

I reviewed the code by reading it and the bench result files. Bash was denied, so I could not run the test suite.

### Findings

**1. At the travel limit, following sends the same goal again and again. Each resend clears object tracks (high, confirmed by reading the code).**

- **Where:** `robot/head.py:163`, `:130-138`, and `robot/main.py:568-577`.
- **Cause:** `follow()` clamps the goal to `self.limit`, for example 8.0. `SerialMotor.move` rounds that goal to an encoder step and returns 7.998. The loose servo also often stops short of its goal. So `self.goal != self.angle` stays true, and `follow()` returns `"goal"` instead of `"limit"`.
- **Effect:** On the next tick, a target of 8.0 differs from `sent` (7.998), so the head sends the move again. Any send sets `moving = True` and adds one to `view`. `_head_view` then drops every non-person track and clears `focus`, `verified`, `window`, `views`, and `offers`.
- **When it happens:** A visitor stands past the edge of travel. The cycle repeats each time the head settles, which is several times per second. Objects in view never stay stable.
- **Same bug short of the limit:** If `angle + delta` clamps to a goal within `tolerance` of the angle, the servo may not move. The same resend cycle then runs forever.
- **Why the bench passed:** `exercise()` breaks out of its loop the first time the head settles at the limit. The bench never calls `follow()` again from that position.
- **Fix:** In `follow()`, compute the clamped goal first. If it is within `self.tolerance` of `self.angle`, return `"limit"` and leave `self.goal` unchanged. Add a test that uses a quantizing motor at the limit.

**2. A follow-up line is rejected based on an outdated `last_line` (medium, confirmed by reading the code).**

- **Where:** `robot/main.py:466-471` and `:1328`.
- **Cause:** `_motion_request` runs on the transcribe thread, before earlier queued turns finish. `last_line` changes only after an answer plays (line 1530). Now `_turn` treats `motion == -1` as final and does not check the wake rule again.
- **Example:** A visitor says "Hey Edgy, what is this?" and then "What color is it?" before the first answer plays. The second line gets `-1` and is logged as background. Before this change, `_turn` checked the rule again with the new `last_line` and answered it as a D65 follow-up.
- **Fix:** In `_turn`, check the wake rule again. Then call `_motion_request` when `turn.motion <= 0`. Keep `-1` only as a hint that no motion was requested.

**3. A servo that stops close to its goal but still reports moving can stop the whole session (medium, likely but not proven).**

- **Where:** `robot/servo.py:214-227`.
- **Cause:** In the within-tolerance branch, `deadline` is cleared only when `status["moving"]` is 0. If the servo stops a few steps short and keeps register 66 set, `read()` raises "Servo movement timed out" about two seconds later. The torque limit is 20%, so a mounted load could hold the servo short like this.
- **Effect:** `check_health` then stops the robot.
- **Evidence:** Run `1792158881` held 0.54° short for seven seconds. That file does not record the servo's own moving flag, so I could not confirm the cause. Run `1792160221` had the flag clear at one step short.
- **Next step:** Record this as a mounted-qualification check, or treat "within tolerance and no progress" as settled.

**4. Stop can still leave a small move active (low).**

- **Where:** `robot/head.py:145-151`.
- **Cause:** When the head is stopped or blocked while stationary, and the pending goal is within `tolerance` (1°), `_target` keeps that goal. The head can then send a move of up to 1° while blocked or right after Stop. The old code always braked to the measured angle.
- **Impact:** This is within the 3° Stop excursion limit. It is acceptable if intended, but write it down.

### Checked and correct

- **Startup cleanup:** The `ExitStack` order releases the microphone, then the camera, then the motor, even if model startup fails. A test covers this.
- **SIGTERM handling:** `interrupt` ignores further SIGTERMs, so cleanup can confirm torque off. A subprocess test covers this.
- **Shutdown faults:** If torque off fails, `_close_motor` records the error. `check_health` then reports it at shutdown.
- **Closing twice:** `Robot.close` and the `ExitStack` both close the head. This is safe because `SerialMotor.close` checks `closed`.
- **Recall change:** Recall now includes sightings from other angles only when the view is settled and that label is not in view. This matches the "not in view now" wording.
- **Docs:** `hardware/SERVO.md:62` already says 100 ms, so the earlier review's optional note is done.
