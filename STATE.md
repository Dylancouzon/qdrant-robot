# State

Updated 2026-10-11. Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Last task: first-start video

The monitor waits for the live endpoint before showing video. Failed image requests retry through the existing poll. Lifecycle and browser recovery checks pass; review passes. The updated Mac monitor attaches to the running robot. Reload the page once to load the update.

## Next tasks (in order)

1. Command set v2.
2. Missed-face reset.
3. Physical latency by loopback.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `56ce07810e7a`; rollback target `7b53263969f1`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 56ce07810e7a`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- Running jobs: Mac monitor `tools/talk.py` on port 8765, log `build/first-start/page.log`. Jetson unit `qr-robot` is active; its journal and tegrastats are under `shared/results/`. WSL is unused.

## Targets (floor, not ceiling)

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 42/47 (89%); held-out 17/26 (2026-10-10) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | 1.43 s first WAV p50 from recorded questions; physical latency unmeasured | Close miss |
| 30 tok/s decode | 29.1 tok/s | Close miss |
| 15 fps detection while talking | 14.8 fps p50 in replays | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects of 24 views; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | About 1.1 GB minimum unused in replays; 558 MiB and paging in the full-stack stress run | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run.

## Next command

Read the command-set requirements in `research/mac-audio-interface.md` before writing the task 2 brief.
