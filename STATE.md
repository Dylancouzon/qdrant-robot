# State

Updated 2026-10-11. Branch: `spike/recognition-import`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders this session: Codex `gpt-6.1-sol` at low effort (Dylan, 2026-10-11): `codex exec --model gpt-6.1-sol -c model_reasoning_effort=low -s workspace-write`, stdin closed. Land incremental changes, each measured.

## Active task: recognition import from the course robot

Plan: [research/recognition-import.md](research/recognition-import.md) (design gate GO WITH CHANGES). Dylan's rules: one point per (owner, name), same-owner reteach always appends; label "Dylan's mouse"; voice confirmation of near matches only in a conversation blank, never spammy; a memory tab like the course robot's; strict admission against false positives.

1. Done: `bench/crop_arms.py` on the D145 cup video. Box 263/360, masked 241/360 (E); the detector found the cup on every frame, so the misses are descriptor scores under 0.822 during viewpoint changes. Masking is not adopted.
2. Done: D154 in the runtime: a 6 s teaching window after naming ("Turn it slowly so I can see all sides"), live recognition settings on the page (`robot/settings.py`, `shared/settings.json`). Mac checks pass.
3. Jetson regression replay of D154 (release `2e3975d8d8fc`): 41/47 judged, first audio 1.42 s p50, same as before (J).
4. Done: owner contract (D155), release `f84e54f81e55` deployed (not started). Live things shard migrated; old one in `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
5. Done: Memory tab (Live and Memory tabs; object cards by owner with view thumbnails, Forget, Remove view; edits queued on the conversation worker).
6. Done: voice near-match question (D156).
7. Done: emoji stripped before speech. Final Jetson replay on release `39b2b07265da` (deployed, unit stopped): 42/47 judged, speech 45/47, first audio 1.43 s p50 (J).
8. Next: Dylan's live check (Human checks below); tune settings on the page from what the real camera does.
9. Earlier queue, after this task: the jumpy "???" focus box, command set v2, missed-face reset, physical latency by loopback.

## Human checks (recognition import)

- Teach: "Hey Edgy, this is my mouse", then turn it slowly for 6 s. The page shows "Learning views". Later, show it from a new side: is it "Dylan's mouse"?
- Near match: show it from an odd angle and stay quiet about 4 s: does the robot ask "Is this your mouse?" Answer yes once, no once. It should never ask during speech or more than three times.
- Two owners: a second person (or "I'm Ana" in a new conversation) says "this is my mouse"; the labels must differ.
- Memory tab: cards by owner, thumbnails, Remove view, Forget. "Forget me" removes your objects.
- Settings card: raise or lower the threshold and watch the labels change.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `39b2b07265da` (D154–D156, deployed, not started); rollback target `2e3308d61e5b`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 39b2b07265da`, then open http://127.0.0.1:8765. The unit is stopped now.
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
