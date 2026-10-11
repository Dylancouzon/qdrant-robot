# State

Updated 2026-10-11. Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Last task: recognition import (done, merged)

The teaching window, owner-keyed objects, Memory tab, live recognition settings, and the voice near-match question are on `main` (D154 to D156). How they work: [research/objects.md](research/objects.md). Final Jetson replay on release `39b2b07265da`: 42/47 judged, speech 45/47, first audio 1.43 s p50 (J).

Dylan's live check (2026-10-11): recognition works well. The feed is grainy in a dim room; more light is the fix (lessons row "Camera at 15 fps"). At the next human session, recheck the items not yet reported one by one: two owners get different labels, the near-match question answered yes and no, and "Forget me" removes the visitor's objects.

## Next tasks (in order)

1. The jumpy "???" focus box.
2. Command set v2.
3. Missed-face reset.
4. Physical latency by loopback.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `39b2b07265da` (D154 to D156); rollback target `2e3308d61e5b`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 39b2b07265da`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- Running jobs: none. WSL box: idle.

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

Read `research/edge-cases.md` for the focus-box rows, then write the brief for task 1.
