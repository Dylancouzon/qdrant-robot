# State

Updated 2026-10-10. Branch: `main`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders this session: Sonnet sub-agents; the main session orchestrates (Dylan, 2026-10-10).

## Active task: robot speaker and microphone

The USB speaker and microphone are connected (ALSA card `Device`). Loopback and a spoken test (J): the USB microphone transcribes Dylan nearly perfectly at about -25 dBFS speech over a -53 dBFS floor, about 3 dB better than the camera microphone. It hears the robot's own speaker at -17 dBFS, so a playback gate is required.

1. Build on `spike/jetson-audio` (builder running): self-voice gate with a tail, Jetson audio as the default, a volume slider on the Mac page saved in `shared/`, and Mute acting on the Jetson microphone.
2. Review, deploy, then a live check with Dylan (checklist below).
3. Measure physical latency by loopback (an M4 requirement).

## Next tasks

1. Command set v2 (Dylan approved): distinct verbs ("remember me", "remember this", "forget ..."); the robot asks for names and confirms deletions; introductions no longer offer face enrollment; unknown objects get a teach-the-command reply. Design gate, frozen dialogue fixtures, then build.
2. Missed-face conversation reset: a face leaving the frame ends the conversation and now also clears recall frames (`research/edge-cases.md`).
3. Owner and location payloads ([research/owner-location.md](research/owner-location.md)).

## Human checks

- Live audio: wake the robot from visitor distance, ask two questions, and confirm it never answers its own voice. Set the volume with the slider; restart and confirm the level holds.
- UI Ignore: open the item list with an object in view, let it leave the frame, and press "Do not track that" within 8 s. Confirm it stays ignored after a restart, then Restore it. After 10 s the item should be gone from the list.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Current release `5c9a89a33fd4` (D150 recall, D151 UI Ignore, forget guard); rollback target `7f67670fa91e`.
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
