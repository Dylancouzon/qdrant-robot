# State

Updated 2026-10-11. Branch: `spike/recognition-import`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders this session: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Active task: recognition import from the course robot

Plan: [research/recognition-import.md](research/recognition-import.md) (design gate GO WITH CHANGES). Dylan's rules: one point per (owner, name), same-owner reteach always appends; label "Dylan's mouse"; voice confirmation of near matches only in a conversation blank, never spammy; a memory tab like the course robot's; strict admission against false positives.

1. Done: `bench/crop_arms.py` on the D145 cup video. Box 263/360, masked 241/360 (E); the detector found the cup on every frame, so the misses are descriptor scores under 0.822 during viewpoint changes. Masking is not adopted.
2. Running: `bench/gallery.py`, gallery growth (fixed, voice-confirmed, track-harvested) on 17 viewpoint videos with cross-instance distractors.
3. Next: owner and deletion contract (design gate), then crop choice, gallery cap, memory tab, voice confirmation.
4. Earlier queue, after this task: the jumpy "???" focus box, command set v2, missed-face reset, physical latency by loopback.

## Human checks

- Teaching: hold an object, say "Hey Edgy, track this", answer the question with "my bottle". Then "Track this as my cup" in one line. Note any wrong object or person named, and whether a reply spoken during the robot's question is lost.
- Follow-ups: wait 40 s between questions without the wake phrase; after 60 s the page should say "Say 'Hey Edgy'".
- UI Ignore: an item stays in the list for 30 s after it was last focused; ignore it, restart, Restore it.
- Volume slider and Mute; close the page and confirm the robot keeps answering.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `2e3308d61e5b` (D150–D153); rollback target `5c9a89a33fd4`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 2e3308d61e5b`, then open http://127.0.0.1:8765. The unit is stopped now.
- Running jobs: none. WSL box: idle.

## Targets (floor, not ceiling)

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 41/47 (87%); held-out 17/26 (2026-10-10) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | 1.41 s first WAV p50 from recorded questions; physical latency unmeasured | Close miss |
| 30 tok/s decode | 29.1 tok/s | Close miss |
| 15 fps detection while talking | 14.7–14.9 fps p50 in replays | Close miss |
| Edge 10 ms p99 | 0.49 ms at 1,000 points (D36) | Met; retest at full volume |
| 500 MB headroom, no swap in a turn | About 1.1 GB minimum unused in replays; 558 MiB and paging in the full-stack stress run | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run.

## Next command

`git log --oneline spike/jetson-audio -3` after the builder reports.
