# State

Updated 2026-10-11. Branch: `codex/robot-enclosure`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Active task: Concept A enclosure

Read [hardware/DESIGN_REQUIREMENTS.md](hardware/DESIGN_REQUIREMENTS.md) for Dylan's enclosure requirements and owned hardware. Keep the owned servo and prioritize repacking. Consider a replacement only for a substantial improvement.

The packaging study, fit coupons, and removable power-exit trial are in [hardware/concept-a/](hardware/concept-a/README.md). Mac geometry checks and power-trial slicing pass (E). Final mounts, head joint, cable behavior, cooling, and physical fits remain U. Dylan authorized head yaw (H1), owns 7.4 V STS3215 servos, and uses a P1S with its default nozzle. PLA is preferred. USB protrusion is 10 mm. The power plug has an 11 mm diameter, an 11 mm straight reach, and a 10 mm rotatable elbow. The trial uses an upward exit and a recessed face 9 mm from the provisional socket plane.

The body envelope is 136 × 112 × 160 mm, with a 230 mm overall height (E). Next physical work: check the power-exit trial and fit coupons, confirm the servo drawing, identify the bus adapter, and measure port coordinates and fan orientation. Continue the removable casing and manual joint prototype from `PROTOTYPE_BRIEF.md`. Use external camera routing until complete connector admission through both bearing bores is verified. Browser appearance remains U.

## Next tasks (in order)

1. The jumpy "???" focus box.
2. Command set v2.
3. Missed-face reset.
4. Physical latency by loopback.

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

Read `hardware/concept-a/PROTOTYPE_BRIEF.md`, then build the bearing carrier and casing around verified interfaces. Keep uncertain interfaces replaceable.
