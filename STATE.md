# State

Last updated: 2026-10-09, by the lead. Rewrite, do not append.

## Active task

F0c data freeze complete (D91); F0d harness complete with review PASS (D93); next: prepare challenge audio/deployed-decoder oracle, then baseline (D79–D83, D87, D90). Branch spike/overnight-2026-10-09 is at pushed 18cf16a; F0c is committed and clean. Six reviewed checkpoints preserve status, F0 preparation/results, paced video qualification, fresh data, and supervised continuous measurement.

F0d scope: implement the absolute continuous audio harness in research/continuous-eval.md. Design GO WITH CHANGES reviews/20261009-034911-54216-design.md; sample-end audio timing, timestamp association, separate-process supervision/post-exit footer, subprocess failure tests, and fixed 90 s smoke are incorporated. F0c data is complete. Prior evaluator scope: sources, provenance, exclusions, and fixtures only. Allowed paths eval/challenge-20261009/, eval/prepare_challenge.py if needed, and ignored build/f0c-sources/. No robot, existing fixtures, STATE, DECISIONS, configuration, remote jobs, or model changes. Timed continuous harness needs a separate design gate before implementation. No training because F0 left only three correct-evidence failures, below its eight-failure trigger.

Acceptance: 48 scored questions in three complete 16-question visits; distinct source scenes, physical objects, names, and wording from development. Cover visual detail, older observations, topic references, corrections, absent facts, and plain conversation. Freeze source groups/hashes, primary URLs/licenses, preprocessing/orientation/cadence, exact frame/time evidence, independent rubrics, category counts, and schedule before baseline or tuning. Three 600 s visits run in one unchanged Robot process, without reset/restart. Auxiliary statements may be unscored but must be logged. Preserve D60/D68/D70: no unsupported identity/enrollment or personal attribution across the 20 s anonymous conversation boundary. General fictional facts can remain shared.

Source exclusions: all existing eval sources, the used live-items clip, all prior COCO, and Objectron cup/camera IDs listed in research/capability-plan.md. Group splits by whole capture/object/participant, never neighboring frames. Challenge sources, expected answers, and baseline failures are evaluator/reviewer-only; all later builders/trainers receive explicit exclusions. If physical-instance disjointness cannot be verified, report its limit and do not claim it. No new spending. Use official sources only; skip unsuitable terms. Start with a few sources, check sizes before fetching, expand by coverage.

Acquisition budget: 300 MB ignored raw cache, 60 MB final fixtures; each tracked video under 15 MB. Prefer small real footage with distinct visible objects, and deterministic upright constant-rate derivatives if needed. Save original hashes and exact conversion command. Network requests have finite connect/read timeouts, per-download progress, and a 300 s process-group watchdog. A timed-out download is incomplete; inspect partial files and diagnose before one retry. Sources without verified visual facts or grouping cannot freeze. No benchmark/model load on WSL or Jetson during this data task.

Running jobs: no remote jobs. Mac builder /root/f0d_harness completed eval/continuous.py, eval/test_continuous.py, and the small make_wavs output option; qr-f0d-smoke-a finished exit0, MainPID251543 then0, release f96b251e7518, started08:15:26 UTC. Command -m eval.continuous with fixed90s dev schedule; result shared/results/2026-10-09-continuous-smoke-1.jsonl and unit journal. Completion confirmed90.099 s, four structurally complete utterances, two show events, two visits, 1,128 chunks. Some replies missed requests; no quality acceptance claimed. Raw318,550bytes/1,254rows. supervisor startup180s/source10s/schedule stall10s/cleanup60s, reap10s. Lead read all code and tests. Full checks passed with 104 tests in 14.96 s; 26 scoped tests passed in 1.55 s. Task review PASS reviews/20261009-042113-94477-review.md. Evaluator /root/f0c_data finished its data task; six official Objectron book/bottle MOV files downloaded successfully, 108,057,253 bytes plus indices under build/f0c-sources/, no partial downloads or running acquisition. H264 preparation groups 21391/21487 were stopped after lead rejected the repeated-hold movie; interrupted artifact retained in ignored cache, no final movie. Full raw clips are 4–10 s; six short CFR MJPG AVI derivatives are complete. Curl uses connect 10 s, max-time 120 s, outer process-group 300 s; progress bars. Firecrawl credits remain exhausted; official web fallback works. Prior /root/f0_evaluator and /root/f0_video finished. Mac caffeinate PID 37805 keeps the repo session awake; log reviews/overnight-awake.log. Claude/Codex auth and tools/githooks were verified. Latest Codex quota observed at 07:20 UTC is 35% weekly used; Claude usage unverified.

Jetson prep reservation: lead ran qr-f0d-source-prep through tools/jetson.py on d7ed8b31a024, extracting two 3 s upright MJPG clips from existing live-items-1.avi. Source-only, no models. Estimated output under 5 MB; shared/results/2026-10-09-f0d-smoke-source-* and unit journal supply progress. Outer prep child-group watchdog 90 s; unit finished 07:56:54 UTC exit0 after two seconds. Collected two clips, 3,437,964 bytes, and decoded hashes to eval/dev/continuous-smoke-20261009/. Four synthetic WAVs are complete (2.03–3.732 s), and nine smoke files are hashed in its freeze.json. Integrated90s smoke passed source/scheduler requirements on f96b251e7518: four/four switch/held pixels, 1,440,000samples, max chunk/event lateness0.153/0.097s <=0.5s, exit0 after90.099s. System schedule paging55in/55out pages; active-labelled47in/1out, runtime sampledVmSwap0. At least1,258MiB available. Global paging is observed and attribution remains unresolved. Replies include request-following misses, so no quality claim.

Jetson: same boot 09b4bb27-f975-441c-9d00-7af446ec7de6, current f96b251e7518, previous d7ed8b31a024. Source unit qr-f0b-camera-source finished successfully at 07:07:21 UTC. Recheck release/services before any remote change. WSL remains reserved by nobody; its other project's container stays untouched.

Completed evidence: F0 original 14/24 versus verified sufficient 21/24, seven wins, zero losses; prioritize observations/retrieval (D87). F0b all 572/572 pixels match; each concurrent reader meets 66.67 ms latest and 133.33 ms age p95; union 14.8 fps from 15 fps source (D90). Source-only, no integrated claims. Reviews: 20261009-024234-70640-review.md and 20261009-030935-4181-review.md. Raw F0/F0b and operation records are in bench/results/.

Check blocker resolved: D85 API telemetry suppression left the ORT 1.30 uploader alive. D89 sets ORT_DISABLE_TELEMETRY=1 before gate runtime imports. Full checks and pre-commit exited cleanly with 78 tests, 13.29/13.46 s. Diagnosis: bench/results/2026-10-09-native-shutdown-diagnosis.jsonl. Product inference/dependencies unchanged. Use .venv/bin/python for Mac scoring, not system Python 3.9.

Changed paths: lead STATE.md, research/continuous-eval.md, and design receipt; all F0c artifacts are committed. Worker completed eval/continuous.py, eval/test_continuous.py, and minimal eval/make_wavs.py output argument; lead added eval/dev/continuous-smoke-20261009/ and collected source-prep tegrastats. Six AVI files total 22,965,906 bytes; 710 indexed fixture frames matched the sequential oracle on Mac. Lead inspected all raw contact sheets and all 48 expected facts. Current-value rubrics, the original-workshop reference, and book-price absence scope are corrected. Verify passed, including 710 frame matches. Fixed fixture-relative show paths and added timed data validation while preserving legacy audio assertions. Full checks passed with 78 tests in 12.35 s. All 57 fixture files and 15 dialogue hashes audited. Freeze SHA256 e0e389ff0774a32d746482b27039d1a2ce3c75e86e66f8a6846a7b56fd1879b9; no model or baseline outputs. D91 records the freeze and independent review PASS at reviews/20261009-034031-43247-review.md. research/lessons.md contains current findings. Carry source-error propagation in research/edge-cases.md (D71); evaluator must fail if source/detector processing stops before any continuous baseline.

Unmet: source event contract, continuous challenge baseline, semantic live-clip orientation, D75 unseen probes, active paging, production evidence gains, and physical audible latency. research/one-voice.patch remains unapplied. No checkpoint closes held-out quality or M4.

Frozen data interface: visits.jsonl has three visits with start_at_s 0/600/1200, duration_s 600, and absolute at_s for every show/say event; separate rubrics.jsonl by step ID, sources.json provenance, and frame-evidence.jsonl. Exclude all Objectron from training because participant/physical IDs are absent. No baseline outputs before rubrics freeze. Lead inspected all six raw contact sheets: distinct book covers/bottle scenes. Lead rejected an encoded 1,800 s movie of repeated holds; use six short CFR clips and existing final-frame hold at scheduled show events. Prefer MJPG AVI; any new codec must verify indexed pixels and latency.

Next command: commit and push reviewed F0d with its code, tests, dev smoke, and evidence. Then prepare63 challenge WAVs in a separate frozen folder and a Jetson decoder oracle without changing D91 files; run the original1,800s schedule once for baseline. launched command used -m eval.continuous eval/dev/continuous-smoke-20261009/visits.jsonl --audio eval/dev/continuous-smoke-20261009/audio --output /home/qdrant/qdrant-robot/shared/results/2026-10-09-continuous-smoke-1.jsonl. Inspect progress at least each minute; collect, check limits/exit, then task review, commit, and push. Design the continuous harness and source event contract before code changes; acceptance measurements stay on Jetson, and helper checks stay bounded.

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
