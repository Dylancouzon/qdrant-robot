# State

Last updated: 2026-10-08 09:50, by the lead (handoff after a repo review). Rewrite, do not append.

## Active task

**M1.3 Decision run**: not met. All work is on `main` (the reviewed robot was merged; `spike/*` is for bake-offs only).

- Dev, synthetic voices, MAXN_SUPER, Qwen3-VL-2B: 41/47 judged (87%), speech 46/47; p50 from end of speech: transcript 0.73 s, first token 0.82 s, first phrase 1.04 s, first synthesized audio 1.47 s (`bench/results/2026-10-08-replay-1791463902.judged.jsonl`). Qwen3-VL-4B re-run on the same pipeline: 37/47, 1.91 s; the 2B stays (D35).
- Dev, real voices (first run): 29/47 judged, but 16 turns heard the previous step's question. The recordings are right; a pause inside a question splits the line at the VAD, and `eval/replay.py` then shifts every later step by one (D36). Held-out stays at 15/26 synthetic (17/26 under D33); real-voice held-out is not run yet (one use spent so far, D29).
- Qdrant Edge query target met: p99 under 0.5 ms at 1,000 points (D36, `bench/edge_bench.py`).

Next session, in order:

1. **Harness:** after each step, `eval/replay.py` drains every turn the step produced; a step that produced more than one turn is BAD with `split: n`. Check: the real-voice dev replay reports splits instead of shifted questions. Run `python3 eval/run.py --audio audio-real`.
2. **Endpointing for real voices (D26):** candidates to measure on the real-voice dev set: a longer VAD hangover (0.35 s to about 0.6 s), or a minimum line (a fragment under about 1 s waits for more speech). Metric: split steps and first-audio p50; accept the one that removes splits for the least latency. Then add "Quadranth" to `normalize` in `robot/asr.py` (knowledge-1).
3. Real-voice held-out run (use 2, count it in DECISIONS), then M1.4 (knowledge and sight to acceptance) and M1.5 (milestone gate).
4. MAXN thermal test (15 minutes of load in the enclosure; the detector run peaked at 66.3 °C).
5. M2: design gate on `research/m2-design.md` with the detector numbers (`spike/detector`, rebased on `main` 2026-10-08, builder report in `research/detector.md` there), then object memory.
6. The 3080 box LoRA (brief B1 written, `boxes/3080/README.md`): **not started, and not needed yet.** No measured brain miss justifies training (D5): the open failures are endpointing, ASR of "Qdrant", and the harness. Revisit after M1.5.

Running jobs: none. caffeinate runs on the Mac.

## Robot access

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN (192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. Deployed: `154ba4924a5c`. Models: `python -m tools.models` verifies `models.json`.
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

- C0, C1: harness and architecture rethink. C2: M1.1 (`reviews/20261008-010719-8012-review.md`). C3: M1.2 (`reviews/20261008-020746-59698-review.md`). C4: M1.3 quality work (`reviews/20261008-084259-59432-review.md`). C5: repo hygiene, Edge benchmark, 4B re-run, recorder check (D34 to D36).

## Unmet targets

All CLAUDE.md targets unmeasured at acceptance scale except Edge query (met, D36). Interim (dev, 47 turns, no speaker, MAXN): first synthesized audio 1.47 s p50 against 1.2 s; decode 36.0 tok/s meets 30. Held-out answers 15/26 synthetic; real voices split at pauses (D36).

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
- [ ] **M1.3 Decision run.** Synthetic dev 41/47, no swap, 1,886 MB headroom (D27, D28, D35). Real voices: harness and endpointing first (D36).
- [ ] **M1.4 It talks.** Knowledge shard and current-camera questions to M1 acceptance, with dev fixtures and scored replays. Knowledge shard is built (`knowledge/build.py`, Qdrant v1.19.0 server snapshot restored into Edge 0.8.0).
- [ ] **M1.5 Milestone gate.**

## Human checklist (when Dylan is at the robot)

1. Audio hardware: approved; get a directional dynamic USB microphone and any small USB speaker. Meanwhile the Mac is the microphone and speaker (`tools/talk.py`).
2. Calibrate `SCENE_CHANGE` on a lit, static scene.
3. Camera: watch for the USB port fault (D32).
4. The 3080 box: hold (see Next, item 6).

## Facts from Dylan

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice. Room lights may be off at night.
- 2026-10-07 night: "Don't stop at good"; targets are a floor; keep improving models and capabilities.
- 2026-10-08: review session; hand off at a sensible point, no new milestone work.
