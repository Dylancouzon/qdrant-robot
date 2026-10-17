# Head movement and active visitor

The assembled head uses 40°/s speed, acceleration 60, a 20% torque cap, and ±60° travel. Dylan confirmed clear cables and good live motion. The mounted runtime stops at internal servo feedback 65°C. Transient temperature reports and prolonged enclosure heat remain unqualified.

## Commands and ownership

One active visitor supplies conversation identity, object ownership, and following. Enrollment requires explicit consent. Introductions select the sole unknown face beside a recognized visitor. Multiple unknown faces require clarification. "Talk to NAME" selects one visible, uniquely verified enrolled visitor.

| Input | Behavior |
| --- | --- |
| An introduction | Select the sole unknown face, or the matching recognized face when everyone is known. |
| "Talk to NAME" | Select a verified visible person and clear pending personal questions. |
| "This is my phone" | Use the selected visitor's owner ID, including when another person is visible. |
| "What is on your left/right?" | Inspect -45°/+45°, describe the settled capture, return, and restore following. |
| "Stop" or Stop head | Cancel movement, following, and obsolete inspection returns. Verified selection can enable following again. |

Selection persists through arrivals and departures until an introduction, verified handover, forgetting, or reset. Ambiguous matches hold position. Missing face and body evidence preserves ownership and blocks personal actions. Enrollment and deletion require fresh face evidence. A handover clears pending consent, naming, deletion, teaching, and conversation context. The microphone uses this turn-taking convention without speaker separation.

## Controller and evidence

[attention.py](../robot/attention.py) selects the verified face. [head.py](../robot/head.py) applies a ±6% center band and proportional corrections of at most 6°. Fresh captures update goals during movement. Centered, lost, or expired evidence cancels them. Source timestamps must increase; captures older than 300 ms cannot authorize motion. Generations reject results from an earlier selection or command. Speech and playback pause movement.

[main.py](../robot/main.py) separates speech-start identity from the settled inspection capture. Inspection uses image-only captioning, retains the exact frame and generated-source metadata, and cancels for speech, Stop, or shutdown. Object sightings and teaching require settled captures. A changed view clears object continuity. Side and disappearance answers compare views within 1°; general recall retains evidence from other views.

[servo.py](../robot/servo.py) provides the checked transport shared with [the loose-servo helper](../tools/servo.py). The serial port opens exclusively. Startup requires torque off, stationary position mode, valid feedback, and no reported fault. It primes the measured pose after all RAM caps. On this firmware, the current-position goal itself enables torque. Runtime writes remain RAM-only.

The provisional arrival tolerance is 1.5°, accepting 17 encoder steps and rejecting 18. Absolute calibrated limits remain strict. Stationary arrival for 100 ms clears the travel deadline. Repeated goals retain the progress watch; actual movement must exceed five encoder steps to renew it. A moving flag inside tolerance retains its deadline. Faults latch, attempt torque release, close the port, and stop the service through its health check. Restart remains explicit.

## Mounted setup

`/home/qdrant/qdrant-robot/shared/servo-mounted.json` contains the measured calibration:

```json
{"port":"/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46085287-if00","zero":2080,"direction":1,"limit":60}
```

Motor output requires `robot.main --servo-calibration PATH`. The runtime rejects encoder crossings, saved-limit conflicts, unsafe startup state, stale feedback, stalls, and movement deadlines. The [hardware guide](../hardware/SERVO.md) gives wiring and startup details. Loose-servo calibration must not replace the mounted file.

The saved homing offset is 2018. Its original backup and the earlier ±45° mounted file remain preserved. The [trial archive](archive/mounted-servo-trials-2026-10-16.md) records their exact paths, checksums, the uncertain write acknowledgement, and successful read-only reconciliation after power cycling. Runtime saved-register writes remain prohibited.

### Proposed mounted centering

The approved one-time setup is complete. Its historical procedure and guarded rollback are in [the calibration archive](archive/mounted-servo-trials-2026-10-16.md#proposed-mounted-centering). Do not repeat the write. The setup and loose-servo helper retain their below-60°C requirement.

## Following and wider travel, 2026-10-16

The [final ±60° stage](../bench/results/2026-10-16-mounted-travel60-1792196218214928424.json) reached +58.623° and -59.502°, returning within 0.352° of forward (J). Each turn settled in approximately 1.77 s. Saved bytes remained unchanged and torque release passed. Dylan confirmed cable clearance.

The [40°/s response trial](../bench/results/2026-10-16-mounted-response-1792196157047349769.json) completed six Stops (J). Maximum sampled additional travel was 3.164°, dispatch 5.37 ms, and settlement 0.452 s. The provisional 0.3 s settlement target remains unmet. During explicitly watched tests, 3° is a reported diagnostic. Unwatched qualification retains its assertion. Strict travel, bounded dispatch and settlement, faults, and release checks remain enforced.

Longer goals removed actuator pauses: at 30°/s, repeated-goal median speed rose from 17.37°/s to 29.64°/s (J). The [paired 40°/s simulation](../bench/results/2026-10-16-follow-longer-goals40-pair.json) reduced mean error from 3.444° to 2.711° at 150 ms capture delay (E). Stationary time fell from 1.61 s to 0.92 s over the same 18 active seconds. Overshoot and wrong-way corrections stayed zero. Sources delivered at exactly 300 ms hold safely. [head_follow.py](../bench/head_follow.py) compiles source snapshots directly to prevent stale bytecode comparisons.

The [final live session](../bench/results/2026-10-16-live-follow-1792196346534844737.json) exercised continuous movement within the cleared range (J). Dylan reported good testing. Earlier failed trials, rejected measurements, review receipts, and exact reproduction notes remain in [the trial archive](archive/mounted-servo-trials-2026-10-16.md).

## Temperature guard

The servo temperature comes from register 63, independently of Jetson CPU and GPU sensors. The manufacturer [STS3215 specification](https://www.feetechrc.com/Data/feetechrc/upload/file/20260622/6391772523943436695270694.pdf), edition A/0, lists environmental operation through 60°C on page three and internal overheat cutoff above 70°C on page five. Read-only register 13 returned 80°C on this servo (J); its saved threshold remains unchanged.

D187 sets the mounted software cutoff at 65°C at Dylan's request. The guard acts on one sample immediately. Voltage remains 4.5–6.0 V. Reported hardware faults, source expiry, travel limits, and latched shutdown stay enforced. The helper and approved offset setup keep 60°C. No debounce, averaging, automatic recovery, or saved-setting change was added.

Separate 65°C and 60°C reports interrupted testing. The latter stopped the live service after readings near 39°C (J). Captured transitions also included brief 39°C, 44°C, then 39°C readings. A [100-sample read-only reconciliation](../bench/results/2026-10-16-live-guard-feedback-1792196660578608665.json) confirmed torque off, stationary feedback, and 37–40°C across primary and repeated reads (J). These observations do not establish actual overheating or a harmless sensor error. The [65°C-release startup observation](../bench/results/2026-10-16-guard65-live-1792197005362604383.json) recorded 37–41°C servo feedback without a fault (J). The same completed-session telemetry recorded Jetson CPU peak 67.343°C and GPU peak 70.875°C (J). Those sensors differ from the servo register. Enclosure cooling, feedback integrity, and prolonged loaded power remain open.

## Verification and tools

[test_attention.py](../robot/test_attention.py), [test_head.py](../robot/test_head.py), and [test_servo.py](../robot/test_servo.py) cover ownership, consent, cancellation, freshness, progress, boundaries, and cleanup. [head_sim.py](../bench/head_sim.py) uses real Jetson models with simulated yaw. Its nine-turn selection, ownership, inspection, return, and deletion scenario passed. [Independent transcription](../bench/results/2026-10-16-head-speech-1792152537.json) matched all nine saved answers (E).

[servo_runtime.py](../bench/servo_runtime.py) provides functional checks within ±10°, watched travel from an explicit calibration, and service shutdown. `python -m bench.servo_runtime CALIBRATION --travel` runs one stage and never expands the limit itself. Capture feedback and tegrastats, compare saved bytes, and verify final torque release. Private media, raw telemetry, and diagnostic scripts stay under ignored `build/` or Jetson `shared/` paths.

The smooth-following task passed its [review](../reviews/20261016-201906-95508-review.md) and mandatory checks in 240.06 s (E). The temperature follow-up passed 112 focused checks, its [review](../reviews/20261016-202742-3446-review.md), and the full mandatory hook in 243.00 s (E). The [cleanup review](../reviews/20261016-203148-5856-review.md) verified all 13 archived trace originals and compact summaries.

## Next session: assembled robot testing

Keep 40°/s and ±60° for watched use. The +70° trial stopped 1.67° short, so that range remains unqualified. Preserve the calibrated file and both backups. Do not repeat EEPROM setup.

Next, investigate transient temperature feedback and qualify prolonged loaded power and enclosure cooling. Then check two visitors, explicit handoff, departed targets, inspection, Stop during speech, and service shutdown. Inspection latency, sustained detection while speaking, paging, strangers, larger groups, and broader M4 acceptance remain open. Physical latency stays parked under D160.

A failed torque-release acknowledgement requires power disconnection. USB loss and forced process termination can prevent confirmation. Keep the power switch accessible. A stopped side pose can require the selected visitor to re-enter view before inspection resumes.
