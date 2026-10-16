# State

Updated 2026-10-16. Branch: `spike/conversation-context`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

The centered command tip and stored memory map are complete. The map shows real point creation, object links, and once-per-turn recall pulses. It handles deletion, reconnect, and bounded samples. The [interface notes](research/mac-audio-interface.md#stored-memory-map-checks-2026-10-16) retain local, browser, and Jetson checks and their limits. Task reviews passed; the task commit runs all required checks.

The good-light recognition retest is closed on [Dylan's report](research/edge-cases.md#lookalike-recognition-in-good-light-2026-10-15). Conversation trials and returning-visitor greetings stay parked. The enclosure worktree and existing result.json are preserved.

## Robot and jobs

Jetson `robot`: boot `809470ff`; release `83dd4fb999f5` follows the isolated memory-map checks and is running as `qr-robot`. Previous points to accepted `f9b90b958023` for rollback. Logs: `journalctl -u qr-robot`; session: `shared/sessions/20261016-002006`. The Mac monitor serves port 8765 and is connected. The memory-map benchmark finished. WSL is idle.

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

## Next command

Use the live interface at http://127.0.0.1:8765 to assess memory creation and recall during real questions. Resume [conversation next steps](research/conversation.md#next-steps) when Dylan chooses the next task; keep the architecture and evidence requirements fixed.
