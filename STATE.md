# State

Updated 2026-10-17. Read [CLAUDE.md](CLAUDE.md), the [workflow](research/workflow.md), and [lessons](research/lessons.md). The [topic index](research/README.md) links subsystem guidance; [DECISIONS.md](DECISIONS.md) records binding choices.

## Active task

The [memory demo session](research/overnight-conversation.md) is complete (D207, D208). The [hybrid Edge memory session](research/edge-hybrid-memory.md) is complete. Dylan chose hybrid exchange recall (D210, superseding D209): fused dense and BM25 retrieval finds far more (13/13 against 6/13, E), while judged answers stay within noise (validation 23/55 against 25/55, J). Both demo validation sets are spent; a later conversation change needs a new set.

## Robot and jobs

No qr-* unit runs; `robot-monitor` runs (D211). Boot 8cbcfb5c; a reboot started `robot-monitor` and rejoined Wi-Fi (E). Deployed release f65fb1941942 (on-robot monitor and phone tabs, D211); `previous` is a7a7f5385d29; the hybrid recall release 7629fadf194a (D210) remains under `releases/`. `tools/jetson.py rollback` strips answer vectors before switching (qualified, J); the pre-session release 6e8fd759c5d2 remains under `releases/`. The speaker is at 100% (mixer and `shared/speaker-volume`); set it to 0% for tests.

Use `tools/jetson.py` for remote work. Logs use `journalctl -u qr-robot`; telemetry uses `shared/results/*.tegrastats`. Preserve memories, results, backups, and previous releases.

[Head control](research/servo.md) owns mounted calibration, temperature guards, and recovery instructions. Physical heating, Stop/Resume, alternating-input following, and unattended motion remain unqualified. The [remaining-work list](research/edge-cases.md#next-steps) owns other gaps.

## Running on the robot and network failsafes (D211)

- The boot unit `robot-monitor` serves the page from the Jetson: `http://qdrant-robot.local:8765/?key=KEY`, or the robot's IP. Read KEY with `ssh robot cat qdrant-robot/shared/monitor-key` and bookmark the link. Start, Stop, and the view passed end to end from the Mac (E).
- The robot needs no network after Start. 90 to 120 s after Wi-Fi drops, it raises its own hotspot `l6-robot` at `http://10.42.0.1:8765/?key=KEY`. The drill passed: hotspot 111 s after the cut, page served, timed Wi-Fi restore worked (E). The password and key are in gitignored `.env` (`HOTSPOT_PASSWORD`, `MONITOR_KEY`). A reboot or `nmcli con up <wifi>` returns to Wi-Fi.
- At phone width, a Chat tab splits the robot view from the conversation. USB-C networking (`192.168.55.1`) is untested.

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

Run a live demo rehearsal with Dylan and record its turns as fixtures. Dialogue recall is limited by the 2B model's use of quoted exchanges and by the speech-verb cue, not by retrieval; `bench/recall_bench.py` measures retrieval for a later attempt. Other candidates: the run-on reply cap and a face-inside-person filter for false faces.
