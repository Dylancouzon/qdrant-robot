# State

Updated 2026-10-16. Branch: `spike/conversation-context`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Dylan accepted the UI and Memory work. The repository handoff indexes current components and preserves historical evidence separately. Conversation trials, returning-visitor greetings, and broader acceptance remain parked. The enclosure worktree stays untouched.

## Robot and jobs

Jetson `robot`: boot `809470ff`; deployed release `83dd4fb999f5`. The `qr-robot` unit is stopped, and no benchmark unit is active. Previous points to accepted `f9b90b958023` for rollback. Last session: `shared/sessions/20261016-002006`; logs: `journalctl -u qr-robot`. The Mac monitor serves port 8765. WSL is idle.

The cleanup changes documentation and benchmark labels only. It does not deploy or start the robot.

The target measurements below precede this interface refresh.

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

**Servo motor control and voice commands.** Inspect the connected servo/controller, power supply, electrical interface, travel limits, and desired spoken commands. Review the smallest bounded control path before motion. Keep models, memory, consent, and deletion behavior intact. See the [work queue](research/edge-cases.md#next-steps).

Start with `rg -n 'servo|motor|GPIO|I2C|PWM' robot tools research/architecture.md` to locate existing integration points.
