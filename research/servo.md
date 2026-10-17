# Head movement and active visitor

The assembled head uses 40°/s speed, acceleration 40, a 20% torque cap, and ±60° travel. Dylan confirmed clear cables and good live motion. At 65°C feedback, the motor rests for at least three minutes while speech and vision continue. A 70°C report latches the head off. Transient temperature reports and prolonged enclosure heat remain unqualified.

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

[attention.py](../robot/attention.py) selects the verified face. [head.py](../robot/head.py) applies a ±12% center band and proportional corrections of at most 6°. Fresh captures update goals during movement. Centered, lost, or expired evidence cancels them. Source timestamps must increase; captures older than 300 ms cannot authorize motion. Generations reject results from an earlier selection or command. Speech and playback pause movement. Stationary centered or unknown faces preserve camera validity, so object preference checks can run. A halt requires active or pending movement.

[main.py](../robot/main.py) separates speech-start identity from the settled inspection capture. Inspection uses image-only captioning, retains the exact frame and generated-source metadata, and cancels for speech, Stop, or shutdown. Object sightings and teaching require settled captures. A changed view clears object continuity. Side and disappearance answers compare views within 1°; general recall retains evidence from other views.

[servo.py](../robot/servo.py) provides the checked transport shared with [the loose-servo helper](../tools/servo.py). The serial port opens exclusively. Startup requires torque off, stationary position mode, valid feedback, and no reported fault. It primes the measured pose after all RAM caps. On this firmware, the current-position goal itself enables torque. Runtime writes remain RAM-only.

The provisional arrival tolerance is 1.5°, accepting 17 encoder steps and rejecting 18. Absolute calibrated limits remain strict. Stationary arrival for 100 ms clears the travel deadline. Repeated goals retain the progress watch; actual movement must exceed five encoder steps to renew it. A moving flag inside tolerance retains its deadline. Nonthermal faults latch, attempt torque release, close the port, and stop the service through its health check. Thermal handling keeps the serial connection open for verified cooling. Failed release retains the fatal path.

## Mounted setup

`/home/qdrant/qdrant-robot/shared/servo-mounted.json` contains the measured calibration:

```json
{"port":"/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46085287-if00","zero":2080,"direction":1,"limit":60}
```

Motor output requires `robot.main --servo-calibration PATH`. The Mac monitor forwards that argument when launched with `tools/talk.py --servo-calibration PATH`; the path names an existing Jetson file. Start without that explicit option leaves the head disabled. Reuse the mounted calibration for the assembled robot. The runtime rejects encoder crossings, saved-limit conflicts, unsafe startup state, stale feedback, stalls, and movement deadlines. The [hardware guide](../hardware/SERVO.md) gives wiring and startup details. Loose-servo calibration must not replace the mounted file.

The saved homing offset is 2018. Its original backup and the earlier ±45° mounted file remain preserved. The [trial archive](archive/mounted-servo-trials-2026-10-16.md) records their exact paths, checksums, the uncertain write acknowledgement, and successful read-only reconciliation after power cycling. Runtime saved-register writes remain prohibited.

### Proposed mounted centering

The approved one-time setup is complete. Its historical procedure and guarded rollback are in [the calibration archive](archive/mounted-servo-trials-2026-10-16.md#proposed-mounted-centering). Do not repeat the write. The setup and loose-servo helper retain their below-60°C requirement.

## Following and wider travel, 2026-10-16

The [final ±60° stage](../bench/results/2026-10-16-mounted-travel60-1792196218214928424.json) reached +58.623° and -59.502°, returning within 0.352° of forward (J). Each turn settled in approximately 1.77 s. Saved bytes remained unchanged and torque release passed. Dylan confirmed cable clearance.

The [40°/s response trial](../bench/results/2026-10-16-mounted-response-1792196157047349769.json) completed six Stops (J). Maximum sampled additional travel was 3.164°, dispatch 5.37 ms, and settlement 0.452 s. The provisional 0.3 s settlement target remains unmet. The subsequent gentler profile is measured in the temperature follow-up. During explicitly watched tests, 3° is a reported diagnostic. Unwatched qualification retains its assertion. Strict travel, bounded dispatch and settlement, faults, and release checks remain enforced.

Longer goals removed actuator pauses: at 30°/s, repeated-goal median speed rose from 17.37°/s to 29.64°/s (J). The [paired 40°/s simulation](../bench/results/2026-10-16-follow-longer-goals40-pair.json) reduced mean error from 3.444° to 2.711° at 150 ms capture delay (E). Stationary time fell from 1.61 s to 0.92 s over the same 18 active seconds. Overshoot and wrong-way corrections stayed zero. Sources delivered at exactly 300 ms hold safely. [head_follow.py](../bench/head_follow.py) compiles source snapshots directly to prevent stale bytecode comparisons.

The [final live session](../bench/results/2026-10-16-live-follow-1792196346534844737.json) exercised continuous movement within the cleared range (J). Dylan reported good testing. Earlier failed trials, rejected measurements, review receipts, and exact reproduction notes remain in [the trial archive](archive/mounted-servo-trials-2026-10-16.md).

## Temperature guard

The servo temperature comes from register 63, independently of Jetson CPU and GPU sensors. The manufacturer [STS3215 specification](https://www.feetechrc.com/Data/feetechrc/upload/file/20260622/6391772523943436695270694.pdf), edition A/0, lists environmental operation through 60°C on page three and internal overheat cutoff above 70°C on page five. Read-only register 13 returned 80°C on this servo (J); its saved threshold remains unchanged.

D188 replaces whole-session thermal failure with one cooldown owned by the serial motor. At 65°C, the controller verifies torque off, cancels pending movement and inspection returns, and displays a warning. The camera, speech, and microphone stay available. An inspection request receives the cooling warning through normal speech delivery. Stop still suppresses future following.

Recovery requires at least 180 seconds after verified release, followed by eligibility at or below 55°C for 10 continuous seconds. Every confirmation must be fresh, stationary, bounded, and torque zero. A feedback gap over 300 ms resets the continuous confirmation. The motor remains off after eligibility until a fresh verified face or new command authorizes movement. Captures from before recovery cannot create movement or visual writes. Recovery primes the measured pose rather than replaying an old goal.

A reported 70°C latches only the head off until explicit restart after cooling. Other faults, invalid voltage, mode changes, stale transactions, travel violations, and failed release retain fatal precedence. The helper and approved offset setup keep their 60°C requirement. Runtime voltage stays 4.5–6.0 V. No temperature sample is ignored or averaged, and saved settings remain unchanged.

The 65°C release later stopped during Dylan's repeated left/right testing. Its [closed trace](../bench/results/2026-10-16-guard65-live-1792197005362604383.json) records brief published temperature changes near the final trip (J). These old samples use camera timestamps and may repeat cached feedback, so they cannot establish precise heating rates. New diagnostics record feedback completion time, duration, and monotonic time separately. After Dylan rebooted, [100 read-only samples](../bench/results/2026-10-16-feedback-check-1792197816747953931.json) returned 38–39°C, a stationary encoder, and torque off (J). Actual heating versus feedback error remains unresolved.

The earlier completed-session telemetry recorded Jetson CPU peak 67.343°C and GPU peak 70.875°C (J), independently of servo feedback. NVIDIA's [documented cool profile](https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html#fan-profile-control) was briefly selected, then quiet was restored because the microphone is inside the case. Automatic closed-loop control remains active. Original configuration and daemon state are preserved at `shared/experiments/head-cooling-1792198622/`. The restored configuration SHA-256 is `a6749863a65aeca46be75a7a30751ce598c5d8c9a4a1b6930d855e960f91f34c`; the daemon reports quiet. Recognition quality and temperatures need a paired comparison before selecting a louder profile.

The [gentler acceleration-40 trial](../bench/results/2026-10-16-mounted-response-1792198225262935717.json) completed watched ±45° moves, repeated following, and six Stops (J). Dylan found it smoother. Maximum Stop travel was 3.604°, dispatch 5.18 ms, and settlement 0.513 s. Saved bytes remained unchanged, and final torque was off at 37°C. Speed remains 40°/s, and the already cleared normal range remains ±60°. Lower acceleration also lowers deceleration because register 41 controls both. Gentler braking increases stopping travel; this short trial does not prove less heat.

## Verification and tools

The [final Jetson cooldown integration](../bench/results/2026-10-16-thermal-sim-1792199129416417914.json) passed with real models, USB microphone capture, and USB speaker output (J). Injected feedback triggered release, spoken inspection warnings, continued detection and replies, and recovery after 180.021 seconds. Stop persisted through recovery. Passive head displacement and ongoing speech left torque off until new authority. A later 70°C injection kept only the head off. The test used a fake servo, development images, and oracle text; microphone samples were zeroed before processing. It verifies availability, not live recognition or enclosure cooling. Independent saved-output transcription preserved all eight answers; a full-WAV omission of "minimum" was recovered from the unchanged warning phrase (E). Complete samples, private audio, source, and telemetry remain preserved. The [initial integration](../bench/results/2026-10-16-thermal-sim-1792198578472319434.json) remains available for comparison.


[test_attention.py](../robot/test_attention.py), [test_head.py](../robot/test_head.py), and [test_servo.py](../robot/test_servo.py) cover ownership, consent, cancellation, freshness, progress, boundaries, and cleanup. [head_sim.py](../bench/head_sim.py) uses real Jetson models with simulated yaw. Its nine-turn selection, ownership, inspection, return, and deletion scenario passed. [Independent transcription](../bench/results/2026-10-16-head-speech-1792152537.json) matched all nine saved answers (E).

[servo_runtime.py](../bench/servo_runtime.py) provides functional checks within ±10°, watched travel from an explicit calibration, and service shutdown. `python -m bench.servo_runtime CALIBRATION --travel` runs one stage and never expands the limit itself. Capture feedback and tegrastats, compare saved bytes, and verify final torque release. Private media, raw telemetry, and diagnostic scripts stay under ignored `build/` or Jetson `shared/` paths.

The thermal cooldown and gentler braking task passed its [final review](../reviews/20261016-210546-35698-review.md), 20 focused thermal checks, and the full mandatory hook in 230.28 seconds (E). The review found and verified the repair of a passive-displacement recovery bug. The smooth-following and earlier guard tasks passed full hooks in 240.06 and 243.00 seconds (E). The [cleanup review](../reviews/20261016-203148-5856-review.md) verified all 13 archived trace originals and compact summaries.


## Next session: assembled robot testing

Keep 40°/s and ±60° for watched use. The +70° trial stopped 1.67° short, so that range remains unqualified. Preserve the calibrated file and both backups. Do not repeat EEPROM setup.

Next, investigate transient temperature feedback and qualify prolonged loaded power and enclosure cooling. Then check two visitors, explicit handoff, departed targets, inspection, Stop during speech, and service shutdown. Inspection latency, sustained detection while speaking, paging, strangers, larger groups, and broader M4 acceptance remain open. Physical latency stays parked under D160.

A failed torque-release acknowledgement requires power disconnection. USB loss and forced process termination can prevent confirmation. Keep the power switch accessible. A stopped side pose can require the selected visitor to re-enter view before inspection resumes.
