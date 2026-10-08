# State

Last updated: 2026-10-08 10:40, by the lead. Rewrite, do not append.

## Active task

**Breadth first (D40):** every feature end to end on the Jetson, known gaps carried here, tuning after M3. M1 works end to end (talks, sees, recalls, knows Qdrant); its accuracy and latency targets stay unmet below.

**M2.2a Sighting answers in code** (next builder): "what was on your left?", "what is gone?", "is the X still there?" resolved in code from sightings and the in-view snapshot, spoken without the LLM (like `shown()`), with the brain as fallback. Acceptance: dev M2 removed and left-right capabilities, a fresh one-time probe set (the M2.1 probes are spent), no regression on `eval/dev/sessions.jsonl` oracle (39/47 with the detector).

M2.1 done (D43): sightings stored and retrieved (dev evidence 19/21), answers carried (unseen probes 0/8).

Next, in order:

1. **M2.2b Naming, forgetting, ignoring** (D37): "this is my phone" binds a name to a confirmed track (or the robot asks), several crops as one multivector point (MaxSim); "forget my phone" deletes the point, crops, and pending writes; "ignore the chair" is a class rule; both survive restart. Parsed in code.
2. **M2.3** Conversation beyond the window (answers as text points); labels on a video view; M2 gate.
3. **M3 Faces:** design gated (D41, D42: EdgeFace-S vs insightface w600k_r50, claim score bake-off, full deletion). Waiting on colleagues' photos in `eval/faces/` for held-out; dev uses public face sets.
4. **M4 hardware:** USB speaker and microphone (Dylan buys), MAXN thermal test, offline cold start, eight-hour run.
5. **Tuning phase (after M3):** fresh larger held-out set with other people's voices; turn merge for long pauses; detector labels for sight; told-statement prompting; latency to 1.2 s.

Running jobs: none. caffeinate runs on the Mac.

## Known gaps (carried, D40)

- M2 answers: the 2B ignores sighting lines; the detector misses objects outside its 50-word vocabulary or at low score (D43). Decode 28.2 tok/s with the detector at 15 fps (target 30).
- Swap grows at in-process replay restarts (44 to 756 MB), with or without the detector; a real restart is a new process.
- Answers: real-voice dev 42/47 (89%), held-out real voices 18/26 (69%, use 2 of D29) against 90%. Sight naming in clutter is the main miss (D39: more image tokens did not help).
- Latency: first synthesized audio 1.45 s p50 dev, 1.58 s held-out, against 1.2 s; no speaker yet.
- A pause over 0.35 s after a short fragment splits the question (knowledge-more-2, 1.34 s).
- The 2B sometimes ignores "The visitor told you" lines (intro-3, small-talk-3 in oracle).
- Held-out leaks: M1 held-out reuses dev frame `live/closet-night.jpg`; `bench/results` holds held-out transcripts.

## Robot access

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN (192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. Deployed: `5fd5253828fa` (the held-out run; the timeout revert after it touches only eval/replay.py). Models: `python -m tools.models` verifies `models.json`.
- Acceptance run from the Mac: `python3 eval/run.py [--model M] [--oracle | --audio audio-real] [cases]` deploys, replays, collects, judges, and checks speech. Real-voice fixtures: `tools/record.py <cases> [--check]`.

## Finding your way in the evidence

- One line per run: `grep -h '"summary"' bench/results/*.jsonl` (model, release, n, correct, p50s, `tegrastats` file, the system prompt once). Per-turn rows hold the heard text, answer, evidence ids, stage times, and the prompt without the system message.
- `<result>.judged.jsonl`: one verdict per turn (`pass`, `why`). `*.tegrastats`: memory, clocks, temperatures, named `<job>-<date>-<time>.tegrastats`; a result's summary row names its file. Files without a date are from before 2026-10-08 04:00.
- `tools/gate.py checks` runs ruff, vulture, pytest, the module self-checks (`python -m robot.<module>`), and the tool selftests. The pre-commit hook runs it.

## Robot facts (2026-10-08)

- L4T R39.2.0, Ubuntu 24.04.4, Python 3.12.3, headless. CUDA 13.2.2, cuDNN 9.20, TensorRT 10.16.2 from apt. llama.cpp 9c2e0e4 built with `GGML_CUDA_NO_VMM=ON` in `shared/src/llama.cpp`. Details: `research/stack.md`.
- Power: MAXN_SUPER (D31): GPU 1,020 MHz, EMC 3,199 MHz, CPU 1,728 MHz. Qwen3-VL-2B decode 36.0 tok/s, prefill 1,492 tok/s. The 15W thermal test peaked at 59.9 °C; the MAXN thermal test is pending.
- RAM 7,485 MB; about 6,000 MB available idle (D20). 8 GB swap file. NVMe about 130 GB free.
- Camera: mounted upside down, frames rotated 180° in `robot/camera.py`; 16 fps at 1280x720 MJPG. The USB hub disabled its port once under MAXN (D32): watch for recurrence; a reopen watchdog is unowned. Microphone: the camera's (ALSA `plughw:CARD=Light`). No speaker: answers are saved as WAVs.
- Services: `l6-robot.service` stopped and disabled (D18); `memory-robot-clock.service` kept.

## Git

Standing approval to commit and push (CLAUDE.md). Remote `origin` = github.com/Dylancouzon/qdrant-robot (private). Branches: `main` (everything reviewed), `spike/detector` (rebased on main, unmerged), `box/3080` (mailbox, at main).

## Checkpoints

- C6: replay split scoring, length-scaled hangover, overfitting rule, M2 fixtures (D37, D38).
- C0, C1: harness and architecture rethink. C2: M1.1 (`reviews/20261008-010719-8012-review.md`). C3: M1.2 (`reviews/20261008-020746-59698-review.md`). C4: M1.3 quality work (`reviews/20261008-084259-59432-review.md`). C5: repo hygiene, Edge benchmark, 4B re-run, recorder check (D34 to D36).

## Unmet targets

All CLAUDE.md targets unmeasured at acceptance scale except Edge query (met, D36). Interim (no speaker, MAXN): first synthesized audio 1.45 s p50 dev, 1.58 s held-out, against 1.2 s; decode 36.0 tok/s meets 30. Held-out answers 18/26 real voices (69% against 90%).

## Milestones and acceptance

Each milestone ends with a robot a visitor can use. Interim numbers are proposed targets (D16); the final targets are in CLAUDE.md.

| ID | Milestone | Visitor experience and acceptance |
| --- | --- | --- |
| M1 | It talks | Answers questions about the current camera view and about Qdrant aloud, on the Jetson alone. 90% correct or more; audio latency 2 s median, 4 s p95 or better; 30 minutes without restart |
| M2 | It remembers | Recalls removed objects, left and right observations, and evicted conversation, including after a restart. Dylan (2026-10-08): name an object by voice ("this is my phone": several crops as one multivector point, MaxSim) and recall it by name, labels on the video view, "forget my phone" deletes it, "ignore the chair" stops remembering it. 90% per capability; Edge search 10 ms p99; M1 speech targets held |
| M3 | It knows you | Enrolls a face with consent, recognizes returning visitors (face multivector, MaxSim), handles a new visitor replacing the last, forgets on request. 90% known-person recognition; zero false identities on held-out strangers |
| M4 | Booth-ready | Every capability offline with Jetson-connected audio for eight hours. Final CLAUDE.md targets: 1.2 s p50 and 2 s p95 audible latency, 15 fps tracking while talking, 500 MB headroom with no swap, held-out eval at target |
| M5 | Add-on | Offline Wikipedia knowledge shard, only if every M4 target still holds |

## M1 tasks

- [x] **M1.1 Stack qualification.** Done 2026-10-08.
- [x] **M1.2 Vertical slice.** Done 2026-10-08 (C3).
- [x] **M1.3 Decision run.** End to end with gaps (D40): real-voice dev 42/47, held-out 18/26, endpointing done (D38); 1,886 MB headroom (D28).
- [x] **M1.4 It talks.** End to end with gaps (D40): knowledge shard calibrated on dev (M1.4a, verbatim facts, unseen paraphrases 0.85 to 0.98), current-camera questions scored; sight naming in clutter carried (D39).
- [x] **M1.5 Milestone gate.** MILESTONE MET under D40 (`reviews/20261008-111211-5165-milestone.md`). Carried: 30 minutes without restart not yet run; research drift (stack.md Super mode, m2-design.md fusion and ignore) to clean in M2.

## Human checklist (live test day, when Dylan is at the robot)

Fixtures so far are photos and recorded audio fed as files; the live camera was checked only for capture and fps. Dylan (2026-10-08): get as far as possible first, then a live testing phase.

1. Audio: the camera microphone is the input. Speaker ordered (Waveshare USB card, 8 ohm 5 W): plug into the Jetson, run with `--speaker`, measure audible latency, check echo into the camera microphone, compare the card's microphone if any. Test the camera microphone at about 1 m with background noise before buying another microphone.
2. Faces (M3.2): Dylan, then colleagues if present, at 0.5, 1, and 2 m, frontal and turned: record clips to recalibrate the face threshold on robot-camera frames (D45: dev margin 0.011).
3. Objects (M2): show, name, remove, and move real objects (phone, mug, bag) left and right; record the session as fixtures.
4. Spoken session end to end with the speaker: every capability, interruptions, a long pause mid-question.
5. Calibrate `SCENE_CHANGE` on a lit, static scene; watch for the camera USB port fault (D32).

Without a human (Lead, when the Jetson is free and the room is lit): a live soak run (camera on, no speech, 30 minutes then hours: detection on real frames, memory growth, temperatures, leaks; closes the M1 30-minute check), and camera-domain fixtures recorded from the live camera.

## Facts from Dylan

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice. Room lights may be off at night.
- 2026-10-07 night: "Don't stop at good"; targets are a floor; keep improving models and capabilities.
- 2026-10-08: review session; hand off at a sensible point, no new milestone work.
