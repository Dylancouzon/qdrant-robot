# State

Updated 2026-10-16. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Stop head now becomes Resume head while following is stopped. Resume requires fresh camera input and preserves cooling and fault blocks. Checks and task review pass. The reviewed GPIO-clearance correction is committed separately. Dylan confirmed the Jetson is powered off; deployment remains pending.

## Robot and jobs

Last verified Jetson boot is 89124a54; release is 1e95640260aa (previous 43a78a5a93a3). Unit qr-robot was last verified stopped. Dylan confirmed that the Jetson is powered off. The simulated-motor Jetson smoke passed; no physical motion occurred. A post-crash read-only check confirmed motor off, stationary, 38°C, 5.4 V, and no reported fault. The Mac monitor is http://127.0.0.1:8766 and retains --servo-calibration /home/qdrant/qdrant-robot/shared/servo-mounted.json for Start. Logs use journalctl -u qr-robot; telemetry uses shared/results/robot-*.tegrastats. No benchmark job remains running.

Mounted file: /home/qdrant/qdrant-robot/shared/servo-mounted.json, zero 2080, direction one, limit 60. Runtime speed is 40°/s, acceleration/deceleration 40, torque cap 20%, and arrival tolerance 1.5°. Reported 65°C verifies release and pauses the head for at least 180 seconds, with 10 continuous seconds at or below 55°C before eligibility. Reported 70°C latches only the head off until restart after cooling. Speech and vision remain available. Fresh movement input is required after recovery. Other faults latch the head off after confirmed shutdown; unconfirmed shutdown remains fatal. Helpers retain 60°C. Do not repeat EEPROM setup.

[Current head control](research/servo.md) gives operation, validation, backups, and remaining checks. [Trial history](research/archive/mounted-servo-trials-2026-10-16.md) and [the evidence manifest](research/archive/mounted-servo-evidence-2026-10-16.json) locate complete originals in tag archive/2026-10-16/mounted-follow-trials. Private media and raw logs remain under ignored build/ and Jetson shared/. The reviewed GPIO-clearance correction is committed as 6813a36.

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

Next command: when the Jetson is powered on, inspect its release and jobs, deploy the current source, and restart the monitor on port 8766 with the matching release and mounted calibration. Then reload the page and check Stop head followed by Resume head.

Validation: 17 focused control and proxy checks, the page harness, and full release checks pass (E). Full checks took 265.50 s. Task review passes. Live Stop/Resume validation and deployment remain pending while the Jetson is off. Broader acceptance targets remain open.
