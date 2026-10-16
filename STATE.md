# State

Updated 2026-10-16. Branch: `main`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Physical runtime control and shared visitor selection are complete. Opus reviewed both feature scopes, and its blocking findings are fixed. Loose-servo motion, service shutdown, and mandatory regression checks pass. Dylan confirmed assembly on 2026-10-16. Branch reconciliation includes the enclosure and runtime histories; assembled-head qualification is next.

## Robot and jobs

Jetson `robot`: boot `809470ff`; current release `7cd0c52ce424`. Hardware checks passed on `e9471078186d`; the final follow-up fix has host regression coverage. The robot and benchmark units are stopped. Previous points to accepted `f9b90b958023`; baseline `83dd4fb999f5` remains available. The Mac monitor is stopped.

Motor output is opt-in through explicit calibration. Temporary ±8° calibration lives under `shared/experiments/head-hardware/`; it must not be reused after assembly. Mounted calibration remains absent.

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

**Test the assembled head.** Follow [mounted calibration and checks](research/servo.md#next-session-assembled-robot-testing): forward encoder, direction, small initial travel, cable clearance, gradual limits, two-person ownership, inspection, Stop, shutdown, and loaded power.

The provisional Stop settlement target of 0.3 s remains unmet at 0.553 s (J). Qualify loaded power and stationary feedback before unattended use. Inspection latency and broad acceptance remain open.

Next: read `research/servo.md` and perform the assembled-head checklist with the assembled robot.
