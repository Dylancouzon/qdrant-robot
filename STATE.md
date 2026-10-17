# State

Updated 2026-10-16. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Following tuning is complete at 40°/s and ±60° travel. Dylan confirmed cable clearance and good live testing. The reviewed runtime temperature cutoff is now 65°C; brief temperature reports remain unexplained. Current instructions and compact result summaries replace superseded trial detail. Cleanup and validation are complete. The archive tag preserves complete trial evidence.

## Robot and jobs

Jetson `robot`: boot `c5f739e0`; live release `74df9ed96eb2`; previous `7bc4a41a9f5e`. Unit `qr-robot` is listening. Logs: `journalctl -u qr-robot`; bounded numeric trace: `shared/experiments/servo-mounted-calibration/live-follow-1792197005362604383.json`. No benchmark job is running. Runtime and pinned dependency bytes match the validated local files. The Mac monitor at `http://127.0.0.1:8766` uses the live release; reuse it. Accepted `f9b90b958023` remains available.

Mounted file: `/home/qdrant/qdrant-robot/shared/servo-mounted.json`, zero 2080, direction one, limit 60. Runtime speed is 40°/s, acceleration 60, torque cap 20%, arrival tolerance 1.5°, and temperature cutoff 65°C. Helper and offset setup retain 60°C. No automatic fault restart. Do not repeat EEPROM setup or use loose-servo calibration.

[Current head control](research/servo.md) gives operation, evidence, backups, and remaining checks. [Trial history](research/archive/mounted-servo-trials-2026-10-16.md) and [the evidence manifest](research/archive/mounted-servo-evidence-2026-10-16.json) locate complete originals in tag `archive/2026-10-16/mounted-follow-trials`.

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

Investigate transient servo temperature feedback and qualify prolonged loaded power and enclosure cooling. The 60°C trip released torque; 100 read-only samples afterward returned 37–40°C (J). The cutoff adjustment does not establish harmless feedback or adequate cooling. The earlier Jetson GPU reached 70.875°C under load (J).

Stop added up to 3.164° sampled travel and settled in 0.452 s (J), missing the provisional 0.3 s goal. Keep 70° travel, two-person ownership, inspection latency, and M4 acceptance open. Physical latency stays parked. No further speed tuning is planned.

Next command: inspect `qr-robot` status and recent logs through `tools/jetson.py` before any restart. Reuse the existing monitor and read [workflow recovery](research/workflow.md#recovery). A fault requires diagnosis; an unconfirmed torque release requires power disconnection.

Validation: the temperature change passed 112 focused checks, final reviews, and the full required hook in 243.00 s (E). The prior smooth-following hook passed in 240.06 s.
