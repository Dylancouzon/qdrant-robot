# State

Last updated: 2026-10-09, by the lead. Rewrite, do not append.

## Active task

F0f: reviewed continuous baseline checkpoint (D91–D96). Branch spike/overnight-2026-10-09 is at pushed0a76aaa, eight reviewed checkpoints. Main remains eb746fe. Lead owns runtime, evidence, STATE, and DECISIONS. All four workers finished; no active builders.

Acceptance: original three600s visits,48 scored questions,15 auxiliary statements, and six absolute source switches. One unchanged Robot/FileCamera, real VAD/ASR/retrieval/generation/TTS/detection, fixed sample-end pacing, no reset or restart. Require all69 event IDs/63 utterance IDs/three visit IDs,28,800,000 samples, valid source probes, required component liveness, no lost input, zero worker native exit before completion. Record missing/split/empty turns as failures. Score answers independently against frozen reviewer rubrics, and retrieval separately against expected source/statement IDs. Do not change sources, WAVs, pacing, rubrics, product models, prompts, or retrieval. Poor answers are measurement, not infrastructure reasons to rerun.

Preparation passed: D91 source freeze e0e389ff0774a32d746482b27039d1a2ce3c75e86e66f8a6846a7b56fd1879b9, all57 original files unchanged. D94 audio freeze be7cc335a41c3e1d39980a681828e04290083569afa6e31f14e0ad1c36c0ca82;63 WAVs8,366,664bytes, max7.567s, all preflight gaps pass. Jetson cd60be65ee79 decoder710/710 indexed matches, six15fps480x640 sources. Oracle2026-10-09-fixture-decode-1791535339564674223.jsonl SHA80623781c7a5ada65047df5e0246378635f0212ff3c2499c2e11a265922cf041, paired tegrastats,2026-10-09-f0e-operations.jsonl. Review PASS reviews/20261009-044433-22776-review.md; all104 checks15.19s, pre-commit15.00s. No production capability claim.

Running jobs: qr-f0f-baseline-a completed1800.187s, worker native exit0,63 utterances/72 turns/69 events/28,800,000 samples/12 of12 source probes. Nine split utterances include four scored questions and five auxiliary statements. Supervisor/unit exits1 for these recorded failures; this is completed measurement, not a passing benchmark. Unit finished09:19:23UTC; Mac watcherPID52038 ended normally. Runtime releasecd60be65ee79, previousf96b251e7518, boot09b4bb27-f975-441c-9d00-7af446ec7de6. No baseline retry or runtime/model change. Raw bench/results/2026-10-09-continuous-baseline-a.jsonl SHA f1acf67657bdaf3049b2715386bb38c5ab1077d8601c8ae24204c5a6045183c1, paired tegrastats,2026-10-09-f0f-operations.jsonl. Mac answer judgmentPID68387(exec session72107) and independent speech verificationPID68388(session69094) finished, both exit1 for recorded failures under separate process-group watchdogs650s/180s. Exact commands: .venv/bin/python -u -m eval.score_continuous RESULT eval/challenge-20261009/visits.jsonl eval/challenge-20261009/rubrics.jsonl; ORT_DISABLE_TELEMETRY=1 .venv/bin/python -u -m eval.speech RESULT. RESULT is the raw baseline path. No model units running after reconciliation09:23UTC;6,049MiB available,105GB disk free.

Baseline audit: all frozen hashes unchanged; chunk/event maximum lateness0.251/0.113s under0.5s. First synthesized audio from recorded speech end2.291s p50/3.228s p95(all72 outputs), detection13.408fps minimum/14.900median per turn. Minimum schedule headroom1,062.56MiB, allocatedswap105.25–108.5MiB, sampled runtimeVmSwap0. System paging89in/852out pages; fully-active intervals56in/16out, boundary0in/1out, idle33in/835out. Full speech-start to synthesized-end windows replace instant labels. System counters do not establish runtime attribution. No no-paging, physical audio, or15fps acceptance claim.

Progress/recovery: Mac watcherPID52038 completed; it ran build/overnight/watch-baseline.py, logs build/overnight/baseline-watch.log, and checked every30s using bounded45sSSH/55s local launcher commands. Lead inspects the watcher output each minute. Existing separate supervisor startup180s/source10s/schedule-stall10s/cleanup60s, full worker-group kill/reap10s. Healthy schedule has no total deadline(D83). Outer SSH/launcher45s, collect/push120s. Estimated additional logs/audio/memory under150MB. Preserve partial output on failure, diagnose before one infrastructure retry; stop named unit if supervisor itself stalls. Do not wait on the full service. Mac caffeinate PID37805 stays awake. Claude/Codex auth and tools/githooks verified; latest observed quota07:20UTC35%weekly used. Claude remaining usage unknown. WSL idle for this work; leave disney-demo-qdrant alone.

Completed earlier: F0 original14/24 versus sufficient21/24, seven wins/zero losses(D87). Three sufficient-evidence failures are below eight-failure training trigger; prioritize observation/retrieval, deferLoRA. F0b572/572 source pixels and concurrent budgets pass(D90). F0d90s integrated development smoke passes delivery/counts/native-exit checks(D93); some replies miss requests. System paging55in/55out pages, active-labelled47in/1out, sampled runtimeVmSwap0, at least1,258MiB available. Activity labels mark instants while page deltas span intervals; attribute using full recorded turn windows. Mac/Jetson FFmpeg builds differ; use deployed oracle. D89 suppresses Mac gate telemetry uploader before imports while preserving every failure exit.

Changed paths: STATE.md, DECISIONS.md, research/lessons.md, bench/judge-cache.jsonl, baseline raw/judged/scoring/speech JSONLs, paired tegrastats, operations audit, and archived audit source. Scoring tools were reviewed and pushed0a76aaa after115 clean checks14.89s and pre-commit14.90s. No runtime/model/source/rubric/pacing changes. tools/results.py rejects continuous/decoder formats; targeted raw audits remain explicit. Builders/trainers must not read challenge answers or baseline failures.

Judged result:10/48, including visual detail6/12, older observation0/9, topic reference0/9, correction0/6, absent evidence1/6, plain chat3/6. All44 structurally valid scored questions have three-vote verdicts; four splits fail directly. Six correction and four topic-reference source IDs appear, but source presence does not establish sufficient facts. Older-source delivery is unknown on allnine questions, so confirmed source recall is a lower bound. All72 unique nonempty WAVs transcribe within0.35WER; strict speech54/72 preserves18 split-turn failures. No score closes a target.

Completed review: Sol6.1 F0f baseline evidence PASS reviews/20261009-052607-74465-review.md. No blocking findings. research/lessons.md records results and prior review correction. research/edge-cases.md carries decoder/paging gaps.

Next command: commit and push the reviewed F0f baseline, then read/apply qdrant-advisor and inspect installed Edge0.8 stubs for F1 design. Counts/source/resource audit passes as measurement with failures. Review the completed baseline evidence, commit, and push before designing F1. No checkpoint closes held-out quality or M4.

Unmet: paired candidate comparison, source event contract, D75 unseen probes, active-turn paging attribution, production evidence gains, sustained quality, exact prompt-token totals, and physical audible latency. research/one-voice.patch remains unapplied. No context increase or training qualification yet.

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
