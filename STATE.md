# State

Updated 2026-10-17. Read [CLAUDE.md](CLAUDE.md), the [workflow](research/workflow.md), and [lessons](research/lessons.md). The [topic index](research/README.md) links subsystem guidance; [DECISIONS.md](DECISIONS.md) records binding choices.

## Active task

The bounded [overnight conversation plan](research/overnight-conversation.md) is ready for Opus. Dialogue fixtures and judging paths are audited. Sonnet 5.5 and Opus 5.5 reviewed the fixtures and plan. The handoff incorporates the blocking plan corrections. No overnight trials have started. The other session retains Jetson access until it explicitly releases it. Mac analysis and judging are authorized; Jetson model trials will run serially.

## Robot and jobs

Another session is using the Jetson. Current ownership, services, and deployment must be reconciled before remote work. Last verified here: boot 748cf835, release 6e8fd759c5d2, previous ff1206efa987, no loaded qr-* unit, and an Idle Mac monitor at http://127.0.0.1:8766. These observations precede the other session.

Use `tools/jetson.py` for remote work. Logs use `journalctl -u qr-robot`; telemetry uses `shared/results/robot-*.tegrastats`. Preserve memories, results, backups, and previous releases. Run overnight trials with fixture inputs and no physical motion.

[Head control](research/servo.md) owns mounted calibration, temperature guards, and recovery instructions. Physical heating, Stop/Resume, alternating-input following, and unattended motion remain unqualified. The [remaining-work list](research/edge-cases.md#next-steps) owns other gaps. The broad acceptance measurements below precede servo work.

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

Execute the [overnight execution plan](research/overnight-conversation.md). Its fixtures, limits, selection rules, and morning deliverables govern the next session. Reconcile Jetson ownership before trials. [Conversation memory](research/conversation.md) records shipped behavior and deferred consolidation work.
