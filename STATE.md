# State

Updated 2026-10-11. Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Last task: compact Qdrant UI

The camera fills most of Live, with compact controls, fewer labels, and the official Qdrant theme (D157, D158). Desktop and phone checks pass (E). Readable recall, carousels, sliders, and ordinary transcript auto-scroll remain. The full-model Jetson check passes recall thumbnails, settings, and deletion with two oracle-text turns and a fixture image (J); this is not answer-quality or physical-latency acceptance.

At the next human session, check two owners' labels, yes/no near-match replies, and "Forget me" removing the visitor's objects. Dylan already confirmed recognition works. More light addresses the grainy feed.

## Next tasks (in order)

1. The jumpy "???" focus box.
2. Command set v2.
3. Missed-face reset.
4. Physical latency by loopback.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `7b53263969f1`; rollback target `a820d7495631`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 7b53263969f1`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- Running jobs: Mac monitor `tools/talk.py` on port 8765, log `build/ui-refresh/page.log`. Jetson and WSL are idle.

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

Read the focus-box rows in `research/edge-cases.md`, then write the brief for task 1.
