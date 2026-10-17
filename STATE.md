# State

Updated 2026-10-17. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Dylan confirmed the speaker works. The local monitor now shows a large wake-up bubble in an empty chat and a pinned tips bubble during conversation. Dylan will check the UI; broader tests and browser checks are skipped at his request. The active robot remains on release ff1206efa987. Physical heating improvement, alternating-input tracking bias, and live Stop/Resume confirmation remain pending.

## Robot and jobs

Jetson boot is 748cf835, current release ff1206efa987, and previous release d35fce65af87. The qr-robot unit is active. The Mac monitor at http://127.0.0.1:8766 is Listening and uses the mounted calibration. Logs use journalctl -u qr-robot; telemetry uses shared/results/robot-*.tegrastats. Memories, results, and the previous release remain intact.

Mounted file: /home/qdrant/qdrant-robot/shared/servo-mounted.json, zero 2080, direction one, limit 60. Runtime speed is 40°/s, acceleration/deceleration 40, torque cap 20%, and arrival tolerance 1.5°. Reported 65°C verifies release and pauses the head for at least 180 seconds, with 10 continuous seconds at or below 55°C before eligibility. Reported 70°C latches only the head off until restart after cooling. Speech and vision remain available.

Fresh movement input is required after recovery. Other faults latch the head off after confirmed shutdown; unconfirmed shutdown remains fatal. Helpers retain 60°C. Do not repeat EEPROM setup.

[Current head control](research/servo.md) gives operation, validation, calibration backups, trial history, and remaining checks. Memories, benchmark evidence, and raw logs remain preserved.

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

Next step: reload the monitor and check the empty-chat wake prompt and pinned tips during conversation. Select Stop in the monitor to end the robot session.
