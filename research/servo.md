# Head movement and active visitor

One active visitor supplies conversation identity, object ownership, and following. An introduction selects the sole unknown face beside a recognized visitor. Multiple unknown faces require clarification. "Talk to NAME" selects one visible, uniquely verified enrolled visitor. Enrollment still requires explicit consent.

## Commands

| Input | Behavior |
| --- | --- |
| An introduction | Select the sole unknown face, or the matching recognized face when everyone is known. |
| "Talk to NAME" | Select a verified visible person and clear pending personal questions. |
| "This is my phone" | Use the selected visitor's owner ID, including when another person is visible. |
| "What is on your left/right?" | Inspect the fixed -45°/+45° view, describe it, return, and resume the previous following state. |
| "Stop" or the Stop head button | Cancel movement, following, and obsolete inspection returns. A verified selection can enable following again. |

Selection persists through arrivals and departures until an introduction, verified handover, forgetting, or reset. Ambiguous face matches hold position. Missing face and body evidence preserves the selected owner and blocks personal actions. A brief face miss on the same confirmed body retains the existing conversation behavior. Enrollment and deletion require fresh face evidence. A handover clears pending consent, naming, deletion, teaching, and conversation context.

The shared microphone follows this turn-taking convention. It provides no speaker separation. Introductions beside multiple unknown faces need clarification.

## Implementation

- [attention.py](../robot/attention.py) selects one source-specific face. The existing face model embeds each eligible face separately because its declared batch size is one.
- [head.py](../robot/head.py) owns bounded motion. Following uses the verified active face box directly, a ±6% center band, and corrections of at most 3°. Sources older than 300 ms cannot steer.
- The simulator advances at 20°/s. Every goal stays within ±70°. Speech and playback pause movement. A command generation invalidates older goals and returns. Turn cleanup remains atomic with Stop.
- [main.py](../robot/main.py) preserves speech-start identity separately from the settled inspection image. Inspection uses the existing image-only caption operation, with no conversational retrieval or prefill. Empty or malformed output produces uncertainty. Foreground speech, Stop, and shutdown cancel captioning.
- Each inspection retains its exact frame in the existing RAM history. Turn logs retain capture time, view angle, raw generated caption, caption duration, and actual text instructions. The interface labels the description as generated.
- Object sightings and teaching accept settled captures. A changed view clears object continuity. Sightings retain their view angle; side and disappearance answers compare compatible views within 1°. General past recall retains other angles and avoids labeling a currently visible category absent.

The runtime enables the motor through `robot.main --servo-calibration PATH`. Without that explicit file, the head stays disabled. [servo.py](../robot/servo.py) supplies one checked transport shared with the [loose-servo helper](../tools/servo.py). The [hardware guide](../hardware/SERVO.md) defines calibration and startup. The enclosure branch and worktree stay unchanged.

The serial motor rejects unsafe startup state, malformed calibration, saved-limit conflicts, and encoder-boundary crossings. It preserves the measured startup pose and replaces old goals before enabling torque. RAM settings cap torque at 20%, speed at 10°/s, and acceleration at five. EEPROM remains unchanged. One provisional 1° arrival tolerance applies to both motor progress and Head settlement. Following can hold up to 1° inside the travel limit. Absolute travel limits remain strict. The controller uses acknowledged encoder goals and actual feedback for inspection evidence.

The bus opens exclusively. Transactions use a monotonic clock and a 100 ms serial write timeout. Complete feedback older than 300 ms, unexpected torque changes, stalls, and movement deadlines latch a fault. Faults and shutdown attempt torque release and close the port. A head fault stops the live session through its health check. It cannot leave visual recognition silently disabled. Input and normal shutdown report the fault; restart remains explicit. Unconfirmed release produces an explicit error. Normal service SIGTERM enters cleanup and ignores repeated SIGTERM during release. Completed movements clear their travel deadline; a later displacement starts a fresh progress watch. Stationary holds within arrival tolerance preserve object continuity.

The adapter is connected to the Jetson at `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46085287-if00`. The robot user now belongs to `dialout`. A [read-only check](../bench/results/2026-10-16-head-servo-status.json) returned 5.4 V, 27°C, position mode, zero faults, and torque off (J). It requested no motion and wrote no servo registers. Encoder position 853 does not establish forward direction.

## Verification

[test_attention.py](../robot/test_attention.py) exercises shared ownership, unknown introductions, handover, consent, deletion, absent body tracks, exact inspection sources, malformed captions, and cancellation through real Edge stores. [test_head.py](../robot/test_head.py) covers convergence, limits, stale frames, playback, Stop, and concurrent cleanup. [test_servo.py](../robot/test_servo.py) covers calibration, startup ordering, encoder precision, delayed feedback, finite-speed Stop, lost acknowledgements, stalls, and cleanup failures. The existing identity, object, recall, privacy, worker, HTTP, and browser checks remain required.

[head_sim.py](../bench/head_sim.py) renders camera pixels from measured simulated yaw while all runtime models run on the Jetson. It uses development portraits and isolated memory. It performs no serial access or physical movement.

Release `6ff84b1df3ce` passed the [nine-turn scenario](../bench/results/2026-10-16-head-sim-1792152537.json) (J). It selected the introducing stranger beside an enrolled visitor and preserved the owner ID. It followed through a position swap and held when the selected person left. It rejected automatic takeover, obeyed Stop, described both views, returned, and completed confirmed deletion. Observed goals stayed between -45° and +45°. The following window recorded 15.10 detection fps; this short window does not qualify sustained performance.

The right view contained a stop sign, and the left view contained a cat. Both spoken descriptions named the correct main object. Caption durations were 2.96 s and 1.85 s. Speech-ready times, including simulated movement, were 6.16 s and 6.61 s. These are oracle-text simulation measurements, separate from physical audible latency. Independent [Mac transcription](../bench/results/2026-10-16-head-speech-1792152537.json) matched all nine saved answer WAVs with zero word errors (E).

The paired isolated streaming alternative also named both objects. It started text earlier, but included unnecessary scene detail. The product reuses the existing caption operation and speaks its main object. This avoids another runtime prompt path.

## Evidence and decisions

The first controller required an admitted person track. The raw two-person fixture scored 0.249 and 0.218, below the existing 0.25 admission threshold (J). JPEG compression raised those scores to 0.488 and 0.411, admitting both bodies. This explains why a saved-image diagnostic worked while the raw-camera scenario held. Fresh face recognition still succeeded. Following the selected verified face removes this independent admission failure.

The early conversational inspection path returned the robot introduction despite a correct stopped capture. Removing knowledge retrieval did not fix it. The image-only caption operation removed the conversational context and passed both inspected views.

[Design approval](../reviews/20261016-080857-92381-design.md) covers the image-only correction, owner preservation during loss, and atomic cleanup. Earlier [counsel](../reviews/20261016-073807-57540-design.md) required rejection tracing before another following change. Trial JSONs and raw logs remain available; [D175 and D176](../DECISIONS.md) record the binding choices.

The [simulation task review](../reviews/20261016-081534-99885-review.md) passed without blocking findings. Deployed release `31866696ff60` matches all 25 checked runtime, model, and dependency files in validated release `6ff84b1df3ce`. The original regression expectations were updated for explicit handover and preserved ownership during target loss. Accepted rollback release `f9b90b958023` remains the previous release. Raw telemetry and voice files stay under ignored `build/` storage or Jetson `shared/` paths.

## Physical runtime checks

[servo_runtime.py](../bench/servo_runtime.py) drives the real loose servo through Head. Its projected visitor uses measured yaw. The bench range is ±8° around encoder 853, separate from mounted calibration. It tests ±5° moves, following to the bench limit, Stop, obsolete-return cancellation, saved registers, and final torque. Its hold mode verifies service shutdown.

The [first physical trial](../bench/results/2026-10-16-head-hardware-1792158881.json) reached both inspection positions but following blocked on ideal-angle versus encoder rounding (J). The [second trial](../bench/results/2026-10-16-head-hardware-1792158965.json) reached 7.119° against a 7.734° goal before the six-step tolerance triggered a stall (J). Both failures confirmed torque off and unchanged saved registers. The trace does not establish the second trial's raw stationary flag before shutdown.

The controller now uses acknowledged goals. A provisional 1° tolerance accepts seven-step endpoint error without increasing torque. Boundary tests accept 11 steps and reject 12 stationary steps after the stall deadline. Mounted precision remains unqualified. The [design counsel](../reviews/20261016-095710-11537-design.md) records the evidence and required checks. The [follow-up approval](../reviews/20261016-100020-15408-design.md) accepts the bounded hardware and shutdown trials after regressions pass.

The [third trial](../bench/results/2026-10-16-head-hardware-1792159643.json) passed both inspection moves and settled following at 7.822° against a 7.998° goal (J). Stop confirmed settlement after 0.885 s with 0.791° additional travel. It missed the provisional 0.3 s timing goal. The failure record remains unchanged. Torque release and saved-register checks passed. Canceled-return and final-return checks were skipped after that assertion.

The [first service-hold trial](../bench/results/2026-10-16-head-hardware-1792159743.json) stopped on the existing voltage/temperature guard before the manual SIGTERM command. Torque release passed. A separate [100-sample read-only check](../bench/results/2026-10-16-head-voltage-1792159806.json) reported 5.3–5.4 V, 29°C, and torque off (J). The original guard message did not retain the triggering reading. The first physical trial already recorded 5.6 V before motion on the same supply. This makes the old 5.5 V software ceiling a plausible cause, rather than proof of a physical supply fault. Diagnostics now retain that reading. The readback guard now permits 4.5–6.0 V without debounce. The 6 V ceiling is within the confirmed 7.4 V model rating; see the manufacturer source in the hardware guide. Out-of-window voltage, temperature, mode, and reported faults still stop immediately. Mounted power qualification remains necessary.

The provisional 0.3 s Stop target stays visible. The revised loose-servo functional check requires a hold goal in the first available controller cycle, sampled excursion within 3°, and stationary confirmation within two seconds. It records timing separately, preserves the failed timing trial, and completes cancellation and explicit-return checks. It adds no acceleration, torque, or firmware tuning.

The [detailed 20°/s trial](../bench/results/2026-10-16-head-hardware-1792159934.json) measured 4.68 ms hold dispatch, 3.340° maximum sampled excursion, and 0.899 s settlement (J). It failed the 3° excursion criterion. The [first SIGTERM check](../bench/results/2026-10-16-head-shutdown-interrupted.json) exposed repeated signals interrupting cleanup. A separate release command confirmed torque off afterward. The signal handler now ignores repeats during cleanup.

The [10°/s trial](../bench/results/2026-10-16-head-hardware-1792160221.json) passed inspections, settled following, Stop, canceled-return rejection, disabled following, and explicit return (J). Maximum sampled angle was 7.822° within the ±8° bench range. Stop dispatched in 4.40 ms, acknowledged in 5.66 ms, settled in 0.554 s, and moved at most 1.230° after the request. The provisional 0.3 s timing target remains unmet. Feedback reads stayed below 5.68 ms. Saved registers were unchanged, and final torque was off. The [prompt service-shutdown check](../bench/results/2026-10-16-head-hardware-1792160240.json) also passed. It establishes cleanup, not long-run power stability.

The [boundary trial](../bench/results/2026-10-16-head-hardware-1792161973.json) held stationary at 7.031° with a 7.646° acknowledged goal (J). The harness incorrectly required its goal within 0.1° of the 8° limit. The corrected check uses measured stationary arrival within the approved 1° tolerance. It retains ten following calls with unchanged view and goal-write timestamps. The [completed run](../bench/results/2026-10-16-head-hardware-1792162158.json), release `e9471078186d`, passed those checks, Stop, canceled return, explicit return, unchanged saved registers, and torque off. Stop dispatched in 4.44 ms, settled in 0.553 s, and added at most 1.143° sampled travel (J). The provisional 0.3 s timing target remains unmet. The failed harness result remains unchanged. Current release `7cd0c52ce424` also includes the host-tested queued follow-up correction. The separate [20-second hold and service stop](../bench/results/2026-10-16-head-hardware-1792161470.json) passed with the revised voltage guard. This short unloaded hold does not qualify mounted power.

The motor speed is `SPEED` in `robot/servo.py`. Lower speed reduced sampled Stop excursion, with longer traversal as its tradeoff. Mounted qualification must measure the complete 45° inspection and return.

## Opus verification and dispositions

Opus reviewed the [committed visitor and head feature](../reviews/20261016-opus-visitor-control.md) and the [runtime hardware changes](../reviews/20261016-opus-servo-runtime.md). The [follow-up review](../reviews/20261016-opus-servo-followup.md) and [boundary review](../reviews/20261016-opus-head-boundaries.md) also checked the fixes. The [final Opus review](../reviews/20261016-opus-servo-final.md) found one further queued follow-up timing bug. A separate accepted-input timestamp now keeps queued follow-ups eligible before an answer completes. The answer-end timestamp retains conversation expiry, consent, and object-history behavior. A chained follow-up regression verifies this behavior while rejected movement stays canceled. These were static reviews; the tests and Jetson measurements are separate evidence.

The follow-up voltage finding was resolved against the manufacturer range and the already recorded 5.6 V sample. The boundary fixes suppress repeated quantized limit goals, preserve follow-up eligibility at accepted input, and discard small unsent goals on Stop. The fixes include the justified voltage window, post-release nudge position, settled-view recall checks, expired movement deadlines, silent vision inhibition after a motor fault, shutdown error status, overwritten camera errors, stationary holds resetting object continuity, recall across angles, and delayed wake-rejected commands overriding Stop. Focused regression checks cover each path. The unused enrollment parameter and duplicate test patch were removed. Single-face helpers remain necessary for the existing benchmark callers.

The [final runtime task review](../reviews/20261016-105221-90832-review.md) passed without blocking findings. It checked the completed hardware run and the accepted-input correction. The first full hook then exposed three audio fixtures missing Head and one conversation-reset regression. The fixtures now include a disabled Head. Separating input admission from answer-end time preserves the original reset assertion. The [regression recheck](../reviews/20261016-105947-99678-review.md) passed without blockers. All 123 focused checks passed before the full hook rerun.

The introduction order remains deliberate. Dylan required the sole unknown to be the introducing person beside one recognized face. A matching spoken name cannot override that source rule. A name-collision regression preserves it. Selection does not expire automatically because personal ownership must not transfer after a face miss. These choices retain D175 and D176.

The existing name parser can treat a capitalized "I am ..." statement as an introduction. Use "My name is ..." for the demo. Larger-group embedding cost, ambiguous introductions, and automatic target expiry remain later interaction work.

## Next session: assembled robot testing

Dylan must assemble the head before this qualification. Keep the loose-servo calibration under `shared/experiments/`; its encoder zero is a bench reference. Create a separate mounted calibration after assembly.

1. Switch off power, mount the head facing forward, and check cable slack throughout the permitted travel.
2. Read the forward encoder, confirm the direction with a 5° command, and start with a 10° software limit.
3. Expand travel gradually toward ±70° while watching cables and clearance from the ±80° mechanical stops.
4. Introduce one unknown beside one recognized visitor, transfer with "Talk to NAME", and verify following and "my phone" ownership.
5. Ask both inspection questions, verify fresh scene descriptions and return position, then test Stop during movement and speech.
6. Stop the service and verify torque release. Check disconnect handling with the power switch accessible, then repeat regression checks.

Record loaded power, temperature, stopping time, stopping distance, servo noise, and camera tracking while the robot speaks. Investigate intermittent supply-guard trips before unattended operation. Preserve the selected visitor during loss and reject personal writes without fresh identity evidence. Test crossing visitors, a departed target, multiple unknown people, and reacquisition.

The live microphone uses the selected-visitor convention. Speaker separation remains outside this version.

## Remaining qualification

- A mounted load could keep the raw moving flag set inside arrival tolerance. Verify settlement and retain the movement deadline until stationary confirmation.
- Stop preserves an already-settled holding goal within 1°. It cancels unsent goals; residual closed-loop corrections remain within the bench excursion criterion.
- Mounted forward direction, travel, cable clearance, physical stops, and loaded power remain unqualified.
- Software cannot confirm torque release after USB loss or forced process termination. A failed release closes the port and reports that power must be disconnected. Automatic reconnect and retries remain outside this demo.
- Inspection latency exceeds the project target. Sustained detection while speaking, paging, strangers, larger groups, and broader held-out acceptance remain unqualified.
- Body-dependent face-name overlays retain their existing admission rule. Following can work while a weak body detection prevents that overlay.
- Losing both the active face and body also pauses inspection commands. After Stop at a side pose, the visitor can need to re-enter view. Recovery without visible identity remains pending.
