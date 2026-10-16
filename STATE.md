# State

Updated 2026-10-16. Branch: `spike/conversation-context`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Shared visitor selection and bounded simulated head control are implemented and reviewed. The nine-turn Jetson scenario and all nine saved speech outputs pass. An introduction selects the sole unknown beside a known visitor. Conversation, ownership, and following share that selection. Physical runtime integration remains next; the enclosure worktree stays untouched.

## Robot and jobs

Jetson `robot`: boot `809470ff`; current release `31866696ff60`. The `qr-robot` unit is stopped, and no benchmark unit is active. Previous points to accepted `f9b90b958023`; baseline `83dd4fb999f5` remains available. Validated simulation: `shared/experiments/head-sim-1792152537/session`. The Mac monitor serves port 8765 for the current release.

Motor output stays disabled. The connected Jetson adapter passes read-only status after adding the robot user to `dialout`.

The broad acceptance measurements below precede servo work. Current simulation measurements and gaps are in [head control](research/servo.md).

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

**Calibrated servo adapter and mounted qualification.** Establish forward position, direction, encoder limits, and cable clearance with Dylan. Implement the runtime serial adapter before enabling motion. Inspection latency, sustained performance, and broader acceptance remain open. See [head control](research/servo.md#remaining-qualification).

Next: read `hardware/SERVO.md`, then plan the calibrated runtime adapter against the connected controller's readback.
