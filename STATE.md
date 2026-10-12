# State

Updated 2026-10-12 (session end). Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Keep the demo scope (Dylan): only changes that work reliably and make the robot feel smarter. The 2026-10-12 session used Sonnet builders and Opus reviewers with no Codex; ask Dylan whether that still holds.

## Active tasks

None in flight. Deployed as `54ce3b0eb510` (on main): missed-face reset (D161), voice deletions ask first (D162), same-object answers (D163), retention that keeps named-object evidence, spoken "Ignore that", all commands as pills, no booth in the persona (D164), and a live chat that clears only on a voice deletion and says when the conversation closed (D165). The last dev replay ran on `4b538ce2db44`; `54ce3b0eb510` changes only the live page and its chat state, covered by tests. Open for Dylan: may Codex run the answer judge (new answers are keyword-scored only)?

Human checks (live camera): hold a mug, ask "What is this?", show a different mug, ask "Is this the same thing I showed you before?" (expect no or not sure); show the first mug again (expect yes); show a phone (expect "No. Earlier you showed me a mug; this is a phone."). Also "forget my mug" then "yes", and "forget me" while looking away (expect "Please look at me..."). Hold an object and say "Edgy, ignore that" with the Mac page closed (expect "Okay, I will ignore ..." and the chat kept). Once on 2026-10-12 the robot heard nothing for 113 s after "Ignore this" while Dylan spoke (all threads idle, microphone fine afterwards); if it recurs, note the time and dump stacks with py-spy (`/tmp/py-spy` on the Jetson, needs sudo).

Next: "What am I holding?" and "a moment ago" recall (held-out misses). Physical latency by loopback is parked (D160); M4 still requires it.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `938e1f9f` (rebooted 2026-10-12). Current release `54ce3b0eb510`; rollback target `4b538ce2db44`. The robot runs as unit `qr-robot` when started from the Mac page: `python3 tools/talk.py --release 54ce3b0eb510`, then open http://127.0.0.1:8765.
- Backups of the pre-owner things shard: `shared/memory/things-backup-20261011-024622` and `shared/memory-backup-20261011-things`.
- Running jobs: at session end, Dylan's live `qr-robot` still ran release `4b538ce2db44`; Stop and Start from the page with the command above to load `54ce3b0eb510`. WSL is idle.

## Targets (floor, not ceiling)

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 44/47 keyword (judged: 42/47 at an earlier release); held-out 17/26 (2026-10-10) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | 1.43 s first WAV p50 from recorded questions; physical latency unmeasured | Close miss |
| 30 tok/s decode (soft, D160) | 29.1 tok/s | Accepted |
| 15 fps detection while talking | 14.8 fps p50 in replays | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects of 24 views; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | About 1.1 GB minimum unused in replays; 558 MiB and paging in the full-stack stress run | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run.

## Next command

Next task: design brief for "What am I holding?" and "a moment ago" recall, with two alternatives, then build, review, deploy, and replay `eval/dev/sessions.jsonl` on the Jetson.
