# State

Updated 2026-10-11. Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders this session: Sonnet sub-agents; the main session orchestrates (Dylan, 2026-10-10).

## Active task: internal showcase polish

Dylan's live session (2026-10-10, Jetson audio) found: follow-ups lapsed after 20 s, Ignore items vanished at once (the jumpy focus popped them), and teaching failed on split lines and a lost focus. D153 fixes these: a 60 s follow-up window with a "Say 'Hey Edgy'" status, 30 s Ignore offers, two-step teaching ("Track this" then "What should I call it?"), and speech-start focus. Robot audio (D152) works: no self-answers in the session.

1. Live check of D153 (2026-10-11, session `20261010-235648`): Dylan reports it works well. 11 turns, none ignored for a missing wake phrase, and one-line teaching bound every time (J). The two-step "track this" flow and the 30 s Ignore hold were not exercised in the log; they stay on the checklist.
2. Next: the jumpy "???" focus box (detection task), then command set v2 (the rest: "remember me", confirmed "forget").
3. Then the missed-face conversation reset, physical latency by loopback, and owner and location payloads ([research/owner-location.md](research/owner-location.md)).

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
