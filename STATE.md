# State

Updated 2026-10-15. Branch: `main`. Architecture is settled; use the [topic index](research/README.md) for details.

## Active task

Cleanup is reviewed. Startup notes now index settled architecture, workflow, and experiment history. Code checks and Jetson validation are saved in bench/results and reviews. All existing tests remain. The enclosure branch, worktree, and pre-existing result.json stay untouched.

Next work is indexed in [remaining priorities](research/edge-cases.md#current-priorities-after-the-project-review-2026-10-15). Conversation spill and returning-visitor greetings stay parked.

## Robot and jobs

Jetson `robot`: boot `9c5cc14a`, current release `78d67ad5e10d`, previous `94a07aadc5dc`; earlier live release `64d7d3fbe413` remains available. No robot or benchmark job is running. Production memories were separate from validation. WSL is idle for this task.

## Targets

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 43/47 judged, 44/47 keyword; held-out 17/26 (J) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run (J) | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | Recorded first WAV 1.80 s p50; physical latency unmeasured (J) | Miss |
| 30 tok/s decode (soft, D160) | 29.1 tok/s (J) | Accepted |
| 15 fps detection while talking | 14.92 fps p50 in recorded replay (J) | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | Earlier stress run: 558 MiB with paging; latest replay unit reported zero swap peak (J) | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run. Physical latency stays parked under D160.

## Next command

For a live check, run `.venv/bin/python tools/talk.py --release 78d67ad5e10d`. Diagnose the listening stall before adding worker recovery.
