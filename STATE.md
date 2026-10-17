# State

Updated 2026-10-16. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

The phone-to-cat naming fix is deployed. Naming captures the eligible orange focus when speech starts. Comparison questions retain held-object priority. Paired local and Jetson checks pass; live confirmation remains pending. Concurrent staged enclosure changes remain separate.

## Robot and jobs

Jetson boot is 89124a54; robot release is 43a78a5a93a3 (previous d1cea3bcf37b). Unit qr-robot is stopped. The deployed naming check passed with isolated real Edge stores and synthetic crops. The Mac monitor is http://127.0.0.1:8766 and retains --servo-calibration /home/qdrant/qdrant-robot/shared/servo-mounted.json for Start. Logs use journalctl -u qr-robot; telemetry uses shared/results/robot-*.tegrastats. No benchmark job remains running.

Mounted file: /home/qdrant/qdrant-robot/shared/servo-mounted.json, zero 2080, direction one, limit 60. Runtime speed is 40°/s, acceleration/deceleration 40, torque cap 20%, and arrival tolerance 1.5°. Reported 65°C verifies release and pauses the head for at least 180 seconds, with 10 continuous seconds at or below 55°C before eligibility. Reported 70°C latches only the head off until restart after cooling. Speech and vision remain available. Fresh movement input is required after recovery. Other faults remain fatal. Helpers retain 60°C. Do not repeat EEPROM setup.

[Current head control](research/servo.md) gives operation, validation, backups, and remaining checks. [Trial history](research/archive/mounted-servo-trials-2026-10-16.md) and [the evidence manifest](research/archive/mounted-servo-evidence-2026-10-16.json) locate complete originals in tag archive/2026-10-16/mounted-follow-trials. Private media and raw logs remain under ignored build/ and Jetson shared/. Concurrent enclosure edits were left untouched.

The broad acceptance measurements below precede servo work.

## Targets

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 43/47 judged, 44/47 keyword; held-out 17/26 (J) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run (J) | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | Recorded first WAV 1.769 s p50; physical latency unmeasured (J) | Miss |
| 30 tok/s decode (soft, D160) | 29.1 tok/s (J) | Accepted |
| 15 fps detection while talking | 14.82 fps p50 in paired recorded replay (J) | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | Accepted and candidate both paged during response intervals; sampled available minima 877/868 MB (J) | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run. Physical latency stays parked under D160.

## Next step

Real heating versus temperature-feedback error remains unresolved. Qualify prolonged enclosure cooling and microphone recognition before selecting a louder fan profile. Then check two-person handoff, inspection, Stop during speech, and departure. The +70° range remains unqualified. Stop travel reached 3.604° and settled in 0.513 s (J); the provisional 0.3 s target remains unmet. Unattended motion remains unqualified.

Next command: reload http://127.0.0.1:8766 and select Start. Use the Memory tab to forget the incorrect cat memory, then teach the plushie with its orange focus selected. Confirm that the phone keeps its name. Named-greeting testing remains pending. A failed torque-release acknowledgement requires power disconnection.

Validation: 14 focused naming, selection, pin, and comparison checks pass locally and on the Jetson with synthetic crops (E, J). The original selector fails all four typed/audio naming variants on both machines. Full checks pass in 265.27 s (E), and task review passes. Live confirmation and broader acceptance targets remain open.
