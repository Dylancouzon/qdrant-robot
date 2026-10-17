# State

Updated 2026-10-16. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

The requested 40°/s profile and 120° total travel (±60°) are running. Dylan confirmed cable clearance after both turns and returns. Continuous six-degree corrections reduce pauses. The final task review passed. Remaining work concerns qualification rather than further speed tuning.

## Robot and jobs

Jetson `robot`: boot `c5f739e0`; deployed release `7bc4a41a9f5e`. Unit `qr-robot` is listening. Its bounded following diagnostics stay under `shared/experiments/servo-mounted-calibration/`; its service log is `journalctl -u qr-robot`. The Mac monitor is at `http://127.0.0.1:8766`. Accepted `f9b90b958023` remains available.

Motor output is opt-in through `/home/qdrant/qdrant-robot/shared/servo-mounted.json`. It uses confirmed forward zero 2080, verified direction one, and the watched ±60° limit. The previous mounted file is backed up. Loose-servo calibration must not be reused.

The broad acceptance measurements below precede servo work. Current evidence and gaps are in [head control](research/servo.md).

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

The requested following profile and watched travel checks are complete. The provisional Stop settlement target of 0.3 s remains unmet at up to 0.452 s, with up to 3.164° additional sampled travel (J). One isolated 65°C report triggered immediate shutdown; its cause remains unresolved. Qualify loaded power and feedback before unattended use.

Next: qualify prolonged loaded power and feedback, then two-person ownership and inspection. Keep 70° travel, inspection latency, and M4 acceptance open. Do not repeat the EEPROM write.
