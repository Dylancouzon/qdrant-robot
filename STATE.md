# State

Last updated: 2026-10-08 10:40, by the lead. Rewrite, do not append.

## Active task

**Breadth first (D40):** every feature end to end on the Jetson, known gaps carried here, tuning after M3. M1 works end to end (talks, sees, recalls, knows Qdrant); its accuracy and latency targets stay unmet below.

**M2.2a done** (D48): sighting questions answered in code; one-time probes 7/8. **Next active: M2.2c live-track stability** (D47): majority label per track, merge a short track into a neighbor with the same label and side, bound stored sightings; measure on `shared/clips/live-items-1.avi` (needs a clip source in the replay) and the 64-window question.

Next, in order (D55, D61, D62):

1. M2.2b (builder running): object naming actions, DINOv2 matching, forget, ignore; recall as retrieval.
2. D60 identity rulings and the video view hook (D59) in robot/main.py.
3. Latency: the TTS first phrase takes 0.53 s (Kokoro should be about 0.1 s): measure alone vs during decode, fix.
4. RAM budget per component with everything active, what can be freed, and whether Qwen3-VL-4B fits (D62: squeeze the bigger model).
5. Assistant v1 (D61, D62): always retrieve with calibrated per-shard minimum scores; retrieval lines into the brain; actions by rules, then a Qdrant intents shard (replaces route.py), then confirmation; teach the focus object with confirmation (view labels "Smartphone?" or "???" or the name); time-decay Formula and Rrf of statements and sightings; memory panel on the view; answers toward 200 tokens with context and barge-in checked; 2B vs 4B evidence use; compare with today's code answers, then delete them; drop left and right; first-person statements scoped to the visitor, general ones shared (D70).
6. M2 and M3 gates; live test day (human checklist); then decide optimizations and training from the biggest measured gaps.
7. M4: speaker (ordered), offline cold start, eight-hour run.

Stop (D55, D71): privacy-mechanism expansion, tracker polish, fixture growth beyond acceptance checks; edge cases go to research/edge-cases.md until v1 is tested end to end.

Running jobs: one builder, V1-E (evidence quality: details, no left/right, no contradictions, missing told lines, ownership only on strong matches, prompt shape I; then paired retrieval-into-brain vs code answers on the Jetson; delete the code answers if not worse, D74). Fast checks on the Mac bake-off harness while building, one full Jetson set at the end.

## Known gaps (carried, D40)

- Audio in the integrated visit (D58): "Qdrant hatch" for "Qdrant Edge"; a short opener ("Okay, so...") splits a question.
- Privacy (D54): a turn frame showing a visitor who was not identified in it survives "forget me" until 12 h retention evicts it.
- Live camera (D47): tracks fragment and labels flicker on real frames (52 tracks, 11 relabeled, in a 90 s clip); sightings are unbounded (185 in a 30-minute soak). Next M2 work: majority label per track, merge short tracks, bound stored sightings.
- M2 answers: the 2B ignores sighting lines; the detector misses objects outside its 50-word vocabulary or at low score (D43). Decode 28.2 tok/s with the detector at 15 fps (target 30).
- Swap grows at in-process replay restarts (44 to 756 MB), with or without the detector; a real restart is a new process.
- Answers: real-voice dev 42/47 (89%), held-out real voices 18/26 (69%, use 2 of D29) against 90%. Sight naming in clutter is the main miss (D39: more image tokens did not help).
- Latency: first synthesized audio 1.45 s p50 dev, 1.58 s held-out, against 1.2 s; no speaker yet.
- A pause over 0.35 s after a short fragment splits the question (knowledge-more-2, 1.34 s).
- The 2B sometimes ignores "The visitor told you" lines (intro-3, small-talk-3 in oracle).
- Held-out leaks: M1 held-out reuses dev frame `live/closet-night.jpg`; `bench/results` holds held-out transcripts.

## Robot access

- 3080 box (Dylan, 2026-10-08): `ssh dylan@192.168.1.74` (key auth; WSL2 Ubuntu 26.04; RTX 3080 10 GB; CUDA 12.6 at /usr/local/cuda; no passwordless sudo). For brain and prompt bake-offs, parallel text replays, judging, and later training; acceptance numbers stay on the Jetson. Setup task X1 running (llama.cpp 9c2e0e4, parity with the Jetson).

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

Without a human: 30-minute live soak done (D47: stable; closes the M1 30-minute check without speech); hours-long soak next. Clips: `shared/clips/live-items-1.avi` (90 s, Dylan handling items, unscripted). Live sessions: snapshot with thirds first, timed cues to the end, record only after Dylan says ready.

## Facts from Dylan

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice. Room lights may be off at night.
- 2026-10-07 night: "Don't stop at good"; targets are a floor; keep improving models and capabilities.
- 2026-10-08: review session; hand off at a sensible point, no new milestone work.
