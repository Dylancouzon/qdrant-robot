# State

Updated 2026-10-12. Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Session 2026-10-12 (Dylan): builders are Sonnet subagents in worktrees, task reviews are Opus subagents, no Codex this session. Keep the demo scope: only changes that work reliably and make the robot feel smarter. Land incremental changes, each measured.

## Active tasks

1. Same-object answers (builder, worktree): [research/same-object.md](research/same-object.md).

Done on main, not yet deployed: missed-face reset (D161), voice deletions ask first (D162), and one start-anchored yes/no reader. After task 1: deploy, then a paired Jetson replay of `eval/dev/sessions.jsonl` against `56ce07810e7a` (must keep 42/47 with no new miss). Then "What am I holding?" and "a moment ago" recall. Physical latency by loopback is parked (D160); M4 still requires it.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `938e1f9f` (rebooted 2026-10-12). Current release `56ce07810e7a`; rollback target `7b53263969f1`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 56ce07810e7a`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- Running jobs: no Mac monitor runs (start it with the command above). Jetson unit `qr-robot` is stopped. WSL is idle.

## Targets (floor, not ceiling)

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 42/47 (89%); held-out 17/26 (2026-10-10) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | 1.43 s first WAV p50 from recorded questions; physical latency unmeasured | Close miss |
| 30 tok/s decode (soft, D160) | 29.1 tok/s | Accepted |
| 15 fps detection while talking | 14.8 fps p50 in replays | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects of 24 views; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | About 1.1 GB minimum unused in replays; 558 MiB and paging in the full-stack stress run | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run.

## Next command

Review each builder diff with an Opus reviewer, then merge, deploy, and replay `eval/dev/sessions.jsonl` on the Jetson.
