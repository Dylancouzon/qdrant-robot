# State

Updated 2026-10-17. Read [CLAUDE.md](CLAUDE.md), the [workflow](research/workflow.md), and [lessons](research/lessons.md). The [topic index](research/README.md) links subsystem guidance; [DECISIONS.md](DECISIONS.md) records binding choices.

## Active task

The [memory demo session](research/overnight-conversation.md) is complete (D207, D208). Exchange quotes, recall gating, memory facts, follow-up grounding, and object-mention deletion are kept. Results are in the [conversation record](research/conversation.md#memory-demo-session-2026-10-17). The demo validation set's first use is spent; a later conversation change needs a new set.

## Robot and jobs

No qr-* unit runs. Boot 748cf835. Deployed release c85580324e35 (main at ee63bf2); its knowledge selftest passes on the Jetson (0.88 ms, J). `previous` points to experiment release 1a8445ee3604, so `tools/jetson.py rollback` lands there; the pre-session release 6e8fd759c5d2 remains under `releases/`. The speaker was 0% during testing and is back at 100% (mixer and `shared/speaker-volume`).

Use `tools/jetson.py` for remote work. Logs use `journalctl -u qr-robot`; telemetry uses `shared/results/*.tegrastats`. Preserve memories, results, backups, and previous releases.

[Head control](research/servo.md) owns mounted calibration, temperature guards, and recovery instructions. Physical heating, Stop/Resume, alternating-input following, and unattended motion remain unqualified. The [remaining-work list](research/edge-cases.md#next-steps) owns other gaps.

## Demo notes for Dylan

- Name small objects while holding them; "That's my motorbike" is refused unless held.
- One new person at a time for "remember me"; a crowded view refuses enrollment.
- A false face on the teddy bear can lock faceless turns ("Please look at me"); keep your own face in view.
- Dialogue quotes need a speech verb: "What did you tell me about X?" works; "And what was that fact?" does not.

## Targets

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Demo dev 49/79 judged; demo validation 15/34; held-out 17/26 (J) | Miss |
| Zero false identities on strangers | Zero in every 2026-10-17 demo and validation run; no stranger acceptance run (J) | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | Recorded first WAV 1.75 s p50; physical latency unmeasured (J) | Miss |
| 30 tok/s decode (soft, D160) | 29.1 tok/s (J) | Accepted |
| 15 fps detection while talking | 14.82 fps p50 in paired recorded replay (J) | Close miss |
| Edge 10 ms p99 | things.score 2.29 ms at 200 objects; memory and knowledge under 1 ms (J) | Met |
| 500 MB headroom, no swap in a turn | Replay headroom 857 to 1,220 MB with 75 to 458 MB swap held; turn paging unmeasured (J) | Miss under stress |

M4 also needs offline cold start, restart and deletion checks, physical latency, and an eight-hour run. Physical latency stays parked under D160.

## Next step

Run a live demo rehearsal with Dylan and record its turns as fixtures. Candidates from the edge-case list: the run-on reply cap, a face-inside-person filter for false faces, and similarity-ranked exchanges; each needs a fresh validation set.
