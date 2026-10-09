# State

Last updated: 2026-10-09, by the lead. Rewrite, do not append.

## Active task

F0e: prepare frozen challenge speech and a deployed-decoder oracle before the baseline (D91–D93). Branch spike/overnight-2026-10-09 is at pushed34ccfcf, six reviewed checkpoints. Main remains eb746fe.

Acceptance: generate all63 scheduled utterances as16kHz mono signed16 WAVs with the six existing heldout synthetic voices. Freeze each utterance hash, voice, command, WAV hash/size/duration, Mac/software provenance, source visits hash, and original data-freeze hash. Use a separate eval/challenge-audio-20261009/ folder; original eval/challenge-20261009/ stays byte-identical. Validate all audio and endpoint gaps with eval.continuous.preflight before any model execution. No baseline outputs or retrieval/model tuning yet.

Decode all six frozen AVI clips on Jetson and save decoder builds, byte hashes, sequential per-frame pixel hashes, metadata/counts, and reverse-index identity checks. Require710/710 matches under the deployed decoder,15fps, and expected dimensions. This is preparation, not a model benchmark. Preserve the Mac truth freeze; pixel differences between platform decoders do not change source bytes or rubrics. A small bench/fixture_decode.py can make this reproducible; no new dependency or product change.

Run preparation with per-command watchdogs: say/afconvert60s each, Mac full prep outer300s process group, remote launch45s, deploy300s, collect/push120s. Decoder native work needs an external worker-group watchdog and progress per source. Estimated audio under20MB, decode logs under100KB. Diagnose failures before one infrastructure retry. No overall experiment deadline (D83).

Running jobs: no models or benchmark units running. Decoder helper deployed as cd60be65ee79. qr-f0e-decoder completed successfully with an external90s child-group watchdog; all710 reverse-indexed frames match sequential pixels. Per-source indexed checks and shared/results/YYYY-fixture-decode-ID.jsonl supply progress. All four workers finished; no nesting. Lead owns this preparation and all remote changes. Mac caffeinate PID37805 remains awake, log reviews/overnight-awake.log. Claude/Codex auth and tools/githooks verified; latest observed Codex quota07:20UTC was35% weekly used. Claude remaining usage unknown. Six heldout voices are installed. Use .venv/bin/python3.12 for Mac eval, not system3.9.

Jetson boot09b4bb27-f975-441c-9d00-7af446ec7de6; currentcd60be65ee79, previousf96b251e7518. qr-f0d-smoke-a finished exit0 after90.099s, started08:15:26UTC. Recheck release/services before a new remote job. WSL remains idle for this work; its disney-demo-qdrant container belongs to another project and stays untouched.

Completed: F0 diagnostic14/24 original versus21/24 sufficient evidence, seven wins/zero losses (D87). Only three adequate-evidence failures, below eight-failure training trigger; prioritize observations/retrieval. F0b source572/572 pixels and all concurrent budgets pass (D90). F0c freezes48 questions/three600s visits, six clips,15 auxiliary statements,57 files/39,679,699bytes (D91). FreezeSHA e0e389ff0774a32d746482b27039d1a2ce3c75e86e66f8a6846a7b56fd1879b9. All Objectron/COCO/prior eval sources are excluded from training; participant/physical grouping unavailable.

F0d evaluator104 tests/full checks pass14.96s, pre-commit15.10s;26 focused tests1.55s. Jetson90s development smoke: one Robot, two visits/four spoken/two show events,1,440,000samples,4/4 switch/hold pixel matches, max chunk/event lateness0.153/0.097s under0.5s. Some replies miss requests; no quality claim. System paging55in/55out pages; active-labelled47in/1out, sampled runtimeVmSwap0. At least1,258MiB available. Activity labels are instants and page deltas span intervals; attribution remains unresolved. Mac/Jetson OpenCV5.0.0 use avcodec61.19.101/62.28.101 and share zero/90 pixel hashes despite identical AVI bytes. Use a Jetson oracle before baseline.

Evidence: bench/results/2026-10-09-continuous-smoke-1.jsonl, paired tegrastats,2026-10-09-f0d-operations.jsonl; reviews/20261009-042113-94477-review.md PASS. Prior F0/F0b reviews and results remain linked in D87/D90. D89 prevents Mac gate telemetry uploader crashes through ORT_DISABLE_TELEMETRY=1 before imports; retain every failure exit and watchdog.

Changed paths: STATE.md, new bench/fixture_decode.py, and eval/challenge-audio-20261009/. All63 WAVs generated successfully, with hashes/voice recipes/freeze; unchanged original57 files audited. All WAVs/endpoint gaps pass eval.continuous.preflight. Decoder tool ruff/vulture pass; all104 checks passed15.19s. Audio freezeSHA be7cc335a41c3e1d39980a681828e04290083569afa6e31f14e0ad1c36c0ca82;63 WAVs8,366,664bytes, maximum7.567s. Jetson six sources15fps/480x640,710/710 indexed matches. Evidence:2026-10-09-fixture-decode-1791535339564674223.jsonl, paired tegrastats,2026-10-09-f0e-operations.jsonl. research/lessons.md contains avenues and pitfalls. research/edge-cases.md carries verify regeneration, source error propagation, cross-decoder hashes, and paging attribution. Builders/trainers must not read challenge answers or baseline failures.

Next command: commit and push F0e preparation after PASS reviews/20261009-044433-22776-review.md. Original1,800s baseline follows with unchanged Robot, fixed absolute pacing, no reset/restart. Exact prompt-token totals remain unavailable; no context increase claim.

Unmet: source event contract, continuous baseline, D75 unseen probes, active-turn paging attribution, production evidence gains, sustained quality, and physical audible latency. research/one-voice.patch remains unapplied. No checkpoint closes held-out quality or M4.

## Where to read first

- research/capability-plan.md: the next autonomous session, priorities, source exclusions, worker roles, required gates, and evidence-based stopping rules (D79, D80, D83).
- research/lessons.md: every avenue explored and every pitfall, with decision links (CLAUDE.md rule: keep it current). Read it after this file.
- DECISIONS.md D35 to D75 (today's work); research/v1-plan.md (the adopted v1 plan); research/booth-ux.md (focus, screen, turn-taking); research/assistant-design.md; research/grounding.md (brain bake-off); research/edge-cases.md (logged, not fixed); research/faces.md, research/m2-design.md, research/m3-design.md, research/wakeword.md, research/sight.md, research/endpointing.md; research/one-voice.patch (retrieval-into-brain variant, not applied).
- [Design gate](gates/design.md) checks alternatives and over-engineering. [Task review](gates/review.md) rules 6–8 cover overfitting, proportion, and edge cases. [Milestone gate](gates/milestone.md) checks acceptance and architectural drift. Explicit commands are in the plan.

## Robot access

- 3080 box: `ssh dylan@192.168.1.74` (key auth; WSL2 Ubuntu 26.04; RTX 3080 10 GB; no passwordless sudo). X1 complete (D75). P1 found the GPU idle. Use `/usr/lib/wsl/lib/nvidia-smi` and `~/qdrant-robot-box/venv` (not `.venv`). Use its user-space CUDA 13.2.86 setup and llama.cpp 9c2e0e4; research/lessons.md records commands and partial answer parity. Acceptance numbers stay on the Jetson.

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN (192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. P1 read-only check at 2026-10-09 05:42 UTC: current release 4387936b8ee9, no robot/benchmark service running. Recheck before execution. Models: `python -m tools.models` verifies `models.json`.
- Acceptance run from the Mac: `python3 eval/run.py [--model M] [--oracle | --audio audio-real] [cases]` deploys, replays, collects, judges, and checks speech. Real-voice fixtures: `tools/record.py <cases> [--check]`.

## Finding your way in the evidence

- Compact history: `python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6`. It keeps judged answers, keyword checks, and evidence scores separate, with machine, release, mode, and incomplete judging visible. Inspect individual raw rows only for the question being resolved; README.md documents filters and supported formats.
- `<result>.judged.jsonl`: one verdict per turn (`pass`, `why`). `*.tegrastats`: memory, clocks, temperatures, named `<job>-<date>-<time>.tegrastats`; a result's summary row names its file. Files without a date are from before 2026-10-08 04:00.
- `tools/gate.py checks` runs ruff, vulture, pytest, the module self-checks (`python -m robot.<module>`), and the tool selftests. The pre-commit hook runs it.

## Robot facts (2026-10-08)

- L4T R39.2.0, Ubuntu 24.04.4, Python 3.12.3, headless. CUDA 13.2.2, cuDNN 9.20, TensorRT 10.16.2 from apt. llama.cpp 9c2e0e4 built with `GGML_CUDA_NO_VMM=ON` in `shared/src/llama.cpp`. Details: `research/stack.md`.
- Power: MAXN_SUPER (D31): GPU 1,020 MHz, EMC 3,199 MHz, CPU 1,728 MHz. Qwen3-VL-2B decode 36.0 tok/s, prefill 1,492 tok/s. The 15W thermal test peaked at 59.9 °C; the MAXN thermal test is pending.
- RAM 7,485 MB; about 6,000 MB available idle (D20). 8 GB swap file. NVMe about 130 GB free.
- Camera: mounted upside down, frames rotated 180° in `robot/camera.py`; 16 fps at 1280x720 MJPG. The USB hub disabled its port once under MAXN (D32): watch for recurrence; a reopen watchdog is unowned. Microphone: the camera's (ALSA `plughw:CARD=Light`). No speaker: answers are saved as WAVs.
- Services: `l6-robot.service` stopped and disabled (D18); `memory-robot-clock.service` kept.

## Git

Dylan requests commits and pushes throughout this overnight session. Working branch: spike/overnight-2026-10-09, from main eb746fe, tracking origin/spike/overnight-2026-10-09. Main is unchanged. Commit each reviewed task with its evidence and push this branch. Remote origin is github.com/Dylancouzon/qdrant-robot (private).

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
| M2 | It remembers | Recalls removed objects, similar instances, and evicted conversation, including after a restart. Names an object by voice ("this is my phone": crop multivectors, MaxSim), recalls it by name, labels the view, deletes on "forget my phone", and stops remembering ignored kinds. D61 removed left/right from the product direction; historical fixtures remain. 90% per capability; Edge search 10 ms p99; M1 speech targets held |
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
3. Objects (M2): show, name, remove, rotate, and return real objects (phone, mug, bag); record recognition and recall as fixtures.
4. Spoken session end to end with the speaker: every capability, interruptions, a long pause mid-question.
5. Calibrate `SCENE_CHANGE` on a lit, static scene; watch for the camera USB port fault (D32).

Without a human: 30-minute live soak done (D47: stable; closes the M1 30-minute check without speech); hours-long soak next. Clips: `shared/clips/live-items-1.avi` (90 s, Dylan handling items, unscripted). Live sessions: snapshot with thirds first, timed cues to the end, record only after Dylan says ready.

## Facts from Dylan

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice. Room lights may be off at night.
- 2026-10-07 night: "Don't stop at good"; targets are a floor; keep improving models and capabilities.
- 2026-10-08: review session; hand off at a sensible point, no new milestone work.
