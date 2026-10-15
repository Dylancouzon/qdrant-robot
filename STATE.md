# State

Updated 2026-10-15. Branch: `codex/robot-enclosure`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first.

## Active task: Print and fit the revised enclosure

The servo-control handoff is ready in [hardware/SERVO.md](hardware/SERVO.md). Fresh reviews, SDK failure tests, and repository checks passed. The loose 7.4 V STS3215 moved through the Waveshare adapter on the Mac with external 5 V 4 A power (E); torque is off and saved settings are unchanged. This task changes no robot runtime or deployed release.

The enclosure is ready for test-piece printing, then the White and Black projects. The Jetson strip slot, bearing hub, and horn disc need physical fit checks. See [ASSEMBLY.md](hardware/enclosure/ASSEMBLY.md) and [edge cases](research/edge-cases.md). Mounted-head calibration, powered head motion, and H5's Jetson USB supply remain unverified (U).

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `39b2b07265da` (D154 to D156); rollback target `2e3308d61e5b`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 39b2b07265da`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- This Mac-only task started no robot jobs. The USB servo is ID one at `/dev/cu.usbmodem5A460852871`, at 1 Mbaud (E). Robot and WSL details are the last recorded state; recheck before remote work.

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

Dylan prints the enclosure test pieces. Record fit results in `hardware/enclosure/MEASUREMENTS.md` before changing CAD or starting mounted-head control. Use the servo guide's `status` command for read-only checks.
