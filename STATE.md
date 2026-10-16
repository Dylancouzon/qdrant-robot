# State

Updated 2026-10-15. Branch: `spike/conversation-context`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Broader memory testing preserved recorded 43/47, visual recall 16/21, and conversation 4/18, but transfer fell from 2/6 to 0/6. A future-plan phrase triggered unrelated dialogue retrieval; duplicate user-only history also remains. Earlier recall improved from 1/6 to 5/6, while the exact Qdrant question still failed. Runtime source is restored; keep accepted f9. The reviewed evidence and records are retained. The enclosure worktree and result.json stay untouched.

The [worker-failure notes](research/edge-cases.md#worker-exceptions-2026-10-15) record Dylan's subsequent live test pass. Next work is indexed in [remaining priorities](research/edge-cases.md#current-priorities-after-the-project-review-2026-10-15). Returning-visitor greetings stay parked.

## Robot and jobs

Jetson `robot`: boot `809470ff`; current accepted release `f9b90b958023`, previous `78d67ad5e10d`. Both regression units finished; results, speech checks, and paging analysis are collected. No live robot or benchmark runs. WSL is idle.

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

Read the broader regression in research/conversation.md before further runtime work. Fix general retrieval eligibility and duplicate history before another integrated comparison. Keep accepted f9.
