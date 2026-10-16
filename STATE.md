# State

Updated 2026-10-15. Branch: `spike/conversation-context`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Conversation-memory testing found no qualifying change. Bounded storage and retrieval supplied all opening replies; best judged recall improved from 1/6 to 5/6, but the exact Qdrant question failed. Native-role controls also failed. Both prototypes are archived and runtime source is restored. The reviewed fixtures and evidence are retained. The enclosure worktree and result.json stay untouched.

The [worker-failure notes](research/edge-cases.md#worker-exceptions-2026-10-15) record Dylan's subsequent live test pass. Next work is indexed in [remaining priorities](research/edge-cases.md#current-priorities-after-the-project-review-2026-10-15). Returning-visitor greetings stay parked.

## Robot and jobs

Jetson `robot`: boot `809470ff`; current accepted release `f9b90b958023`, previous `78d67ad5e10d`. All exchange tests and controls finished. No live robot or benchmark runs. WSL is idle.

## Targets

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 43/47 judged, 44/47 keyword; held-out 17/26 (J) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run (J) | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | Recorded first WAV 1.80 s p50; physical latency unmeasured (J) | Miss |
| 30 tok/s decode (soft, D160) | 29.1 tok/s (J) | Accepted |
| 15 fps detection while talking | 14.92 fps p50 in recorded replay (J) | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | Earlier stress: 558 MiB with paging; rejected model also paged during response intervals (J) | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run. Physical latency stays parked under D160.

## Next command

Read the stored-exchange evidence in research/conversation.md before a different generation diagnostic. Retain accepted f9; do not repeat the rejected integrations unchanged.
