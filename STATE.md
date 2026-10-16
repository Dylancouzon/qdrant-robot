# State

Updated 2026-10-16. Branch: `main`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Improve live following after initial assembled bring-up. Dylan reports slow, uneven tracking and limited travel; small scripted movements and cable clearance passed within ±10°. The controller currently stops between corrections of at most 3°, with motor speed capped at 10°/s. Mounted Stop, return, short service shutdown, upright camera capture, and audible robot replies passed (J). Await readiness for watched ±20° clearance checks while measuring the live tracking pauses.

## Robot and jobs

Jetson `robot`: boot `c5f739e0`; live release `d4bfe27ff762`; previous `454112d0d65a`. Unit `qr-robot` is listening; logs are in `journalctl -u qr-robot` and `shared/sessions/`. Benchmarks are stopped. The Mac monitor runs at `http://127.0.0.1:8766`. The final recorded-fixture import correction is host-only; live runtime files match. Accepted `f9b90b958023` remains available.

Motor output is opt-in through `/home/qdrant/qdrant-robot/shared/servo-mounted.json`. It uses measured zero 2019, verified direction one, and a 10° limit. Loose-servo calibration must not be reused.

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

The provisional Stop settlement target of 0.3 s remains unmet at 0.509 s, with 1.143° additional sampled travel (J). Qualify loaded power and stationary feedback before unattended use. Inspection latency and broad acceptance remain open.

Next: sample live following, distinguish commanded settling from feedback faults, and compare a smoother bounded correction with the current controller. Expand travel only through watched clearance checks. Full 45° inspection travel, prolonged loaded power, two-person ownership, and M4 acceptance remain open. Do not repeat the EEPROM write.
