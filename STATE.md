# State

Updated 2026-10-11. Branch: `codex/robot-enclosure`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Active task: Simplified enclosure (2026-10-12)

Dylan rejected Concept A for printing and assembly (tagged `archive/concept-a-enclosure`, deleted). The [simplified enclosure](hardware/enclosure/README.md) has nine printed parts, 719 mm² overhang against Concept A's 34,887, zero floating islands, and zero thin walls (E). All parts slice on the P1S without supports or warnings: 13.4 h and 500 g. Builders and verifiers were Sonnet 5.5 for this session (Dylan), with Codex at the design gate and the final review.

Next: Dylan prints the coupon plate, the hub with both bearings, and the horn disc on the real horn, then the full set ([assembly](hardware/enclosure/ASSEMBLY.md)). Physical fit, cooling, acoustics, and powered motion remain U ([edge cases](research/edge-cases.md)).

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `39b2b07265da` (D154 to D156); rollback target `2e3308d61e5b`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 39b2b07265da`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- This Mac-only task started no robot jobs. Robot and WSL details are the last recorded state; recheck before remote work.

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

After the coupon print, record fit results in `hardware/enclosure/MEASUREMENTS.md` and adjust clearances in `interface.py`, `body.py`, or `neck.py`.
