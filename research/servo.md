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

Selection persists through other arrivals. Ambiguous face matches hold position. Missing face and body evidence preserves the selected owner and blocks personal actions. A brief face miss on the same confirmed body retains the existing conversation behavior. Enrollment and deletion require fresh face evidence. A handover clears pending consent, naming, deletion, teaching, and conversation context.

The shared microphone follows this turn-taking convention. It provides no speaker separation. Introductions beside multiple unknown faces need clarification.

## Implementation

- [attention.py](../robot/attention.py) selects one source-specific face. The existing face model embeds each eligible face separately because its declared batch size is one.
- [head.py](../robot/head.py) owns bounded motion. Following uses the verified active face box directly, a ±6% center band, and corrections of at most 3°. Sources older than 300 ms cannot steer.
- The simulator advances at 20°/s. Every goal stays within ±70°. Speech and playback pause movement. A command generation invalidates older goals and returns. Turn cleanup remains atomic with Stop.
- [main.py](../robot/main.py) preserves speech-start identity separately from the settled inspection image. Inspection uses the existing image-only caption operation, with no conversational retrieval or prefill. Empty or malformed output produces uncertainty. Foreground speech, Stop, and shutdown cancel captioning.
- Each inspection retains its exact frame in the existing RAM history. Turn logs retain capture time, view angle, raw generated caption, caption duration, and actual text instructions. The interface labels the description as generated.
- Object sightings and teaching accept settled captures. A changed view clears object continuity. Sightings retain their view angle; side and disappearance answers compare compatible views within 1°.

The normal runtime has a disabled head. Tests inject the finite-speed simulator. The reviewed [loose-servo helper](../tools/servo.py) and [hardware guide](../hardware/SERVO.md) provide separate STS3215 status and small-nudge checks. The calibrated runtime serial adapter remains pending. The enclosure branch and worktree stay unchanged.

The adapter is connected to the Jetson at `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46085287-if00`. The robot user now belongs to `dialout`. A [read-only check](../bench/results/2026-10-16-head-servo-status.json) returned 5.4 V, 27°C, position mode, zero faults, and torque off (J). It requested no motion and wrote no servo registers. Encoder position 853 does not establish forward direction.

## Verification

[test_attention.py](../robot/test_attention.py) exercises shared ownership, unknown introductions, handover, consent, deletion, absent body tracks, exact inspection sources, malformed captions, and cancellation through real Edge stores. [test_head.py](../robot/test_head.py) covers convergence, limits, stale frames, playback, Stop, and concurrent cleanup. The existing identity, object, recall, privacy, worker, HTTP, and browser checks remain required.

[head_sim.py](../bench/head_sim.py) renders camera pixels from measured simulated yaw while all runtime models run on the Jetson. It uses development portraits and isolated memory. It performs no serial access or physical movement.

Release `6ff84b1df3ce` passed the [nine-turn scenario](../bench/results/2026-10-16-head-sim-1792152537.json) (J). It selected the introducing stranger beside an enrolled visitor and preserved the owner ID. It followed through a position swap and held when the selected person left. It rejected automatic takeover, obeyed Stop, described both views, returned, and completed confirmed deletion. Observed goals stayed between -45° and +45°. The following window recorded 15.10 detection fps; this short window does not qualify sustained performance.

The right view contained a stop sign, and the left view contained a cat. Both spoken descriptions named the correct main object. Caption durations were 2.96 s and 1.85 s. Speech-ready times, including simulated movement, were 6.16 s and 6.61 s. These are oracle-text simulation measurements, separate from physical audible latency. Independent [Mac transcription](../bench/results/2026-10-16-head-speech-1792152537.json) matched all nine saved answer WAVs with zero word errors (E).

The paired isolated streaming alternative also named both objects. It started text earlier, but included unnecessary scene detail. The product reuses the existing caption operation and speaks its main object. This avoids another runtime prompt path.

## Evidence and decisions

The first controller required an admitted person track. The raw two-person fixture scored 0.249 and 0.218, below the existing 0.25 admission threshold (J). JPEG compression raised those scores to 0.488 and 0.411, admitting both bodies. This explains why a saved-image diagnostic worked while the raw-camera scenario held. Fresh face recognition still succeeded. Following the selected verified face removes this independent admission failure.

The early conversational inspection path returned the robot introduction despite a correct stopped capture. Removing knowledge retrieval did not fix it. The image-only caption operation removed the conversational context and passed both inspected views.

[Design approval](../reviews/20261016-080857-92381-design.md) covers the image-only correction, owner preservation during loss, and atomic cleanup. Earlier [counsel](../reviews/20261016-073807-57540-design.md) required rejection tracing before another following change. Trial JSONs and raw logs remain available; [D175 and D176](../DECISIONS.md) record the binding choices.

The [final task review](../reviews/20261016-081534-99885-review.md) passed without blocking findings. Deployed release `31866696ff60` matches all 25 checked runtime, model, and dependency files in validated release `6ff84b1df3ce`. The original regression expectations were updated for explicit handover and preserved ownership during target loss. Accepted rollback release `f9b90b958023` remains the previous release. Raw telemetry and voice files stay under ignored `build/` storage or Jetson `shared/` paths.

The mandatory pre-commit checks passed in 232.33 s. They ran lint, dead-code detection, the complete regression suite, browser checks, module assertions, and workflow self-checks. The pinned SDK environment separately passed all 24 servo checks.

## Remaining qualification

- Implement the calibrated runtime serial adapter. Verify forward position, direction, saved limits, and encoder-zero handling before enabling it.
- Check loaded motion, cable clearance, the ±70° software limits, and the enclosure's ±80° mechanical stops after mounting.
- Measure physical stopping, power behavior, servo noise, and USB-loss behavior. Software cannot promise torque release after disconnect.
- Inspection latency exceeds the project target. Sustained detection while speaking, paging, strangers, larger groups, and broader held-out acceptance remain unqualified.
- Body-dependent face-name overlays retain their existing admission rule. Following can work while a weak body detection prevents that overlay.
- Losing both the active face and body also pauses inspection commands. After Stop at a side pose, the visitor can need to re-enter view. Recovery without visible identity remains pending.
