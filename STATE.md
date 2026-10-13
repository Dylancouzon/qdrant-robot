# State

Updated 2026-10-11. Branch: `codex/robot-enclosure`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Active task: Enclosure revision after Dylan's review (2026-10-13)

Dylan found the assembly guide unreadable, part names unclear, and the Jetson modeled as a solid box. Fixed: the Jetson is a flat board with a heatsink block, held by its plastic strip in a vertical slot (slot coupon added); the servo takes 5 V from a Jetson USB port (H5, no regulator); the camera cable runs through holes in the head floor and roof (H6); the guide is 27 steps with a part glossary, generated from one list in `preview.py` into the viewer and [ASSEMBLY.md](hardware/enclosure/ASSEMBLY.md). Codex review passed. Builders are Sonnet 5.5; Codex gpt-6.1-sol reviews each change, and Dylan wants back-and-forth until Codex and the lead agree the design is ready.

Waiting on Dylan: the Jetson plastic strip thickness (`JETSON_STRIP_T`, 11.0 U) and whether the servo lead plugs into the adapter board face or edge (`BUS_FACE_GAP`, 2.0 U). Next: an independent walkthrough of the guide against the CAD, then a final Codex readiness review.

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

Apply Dylan's two measurements in `geometry.py`, rerun `body.py`, `head.py`, `coupons.py`, `bambu.py`, and `preview.py`, then run the final review. After the coupon print, record fit results in `hardware/enclosure/MEASUREMENTS.md`.
