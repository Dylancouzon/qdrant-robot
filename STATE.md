# State

Last updated: 2026-10-09, by the lead. Rewrite, do not append.

## Active task

F0b: commit and push qualified paced video input before the independent challenge and continuous baseline (D82, D88). Baseline is spike/overnight-2026-10-09 at 056f6db, pushed. F0's diagnostic is complete: original 14/24, sufficient 21/24, seven wins and zero losses. Three residual failures are below the eight-failure training trigger; prioritize observations, retrieval, and dialogue (D87).

F0b acceptance: preserve still-image FileCamera behavior; expose source frames at their recorded cadence; preserve stored file orientation; return the newest due frame after a slow consumer; hold the final frame without silently looping; release capture resources when switching or closing; reject invalid metadata/failed decoding. Image/video switching and concurrent latest/show access must stay safe. Keep the camera owned by its caller so replay Robot restarts do not close it.

Design gate GO WITH CHANGES: reviews/20261009-025338-83534-design.md. Apply its concurrent-caller requirement before implementation.

Alternatives: (A) pull due frames from an indexed video through latest() under a lock, with sequential reads for adjacent frames and seek only after a missed interval; (B) a paced reader thread that continuously decodes and keeps the latest frame. Choose by source timestamp accuracy, whole latest() p50/p95 (including lock wait), returned-frame age, memory, and observed source rate on the Jetson. A avoids a new thread and join lifetime; B may be needed if seek costs disturb production consumers. This qualifies an input path, not detector rate or integrated capability.

Frozen measurement: concurrent detector at 15 Hz, watcher each 0.3 s, and speech-start reader each 1 s, with a 0.5 s induced detector pause at 15 s. For each caller require latest() p95 <= one source-frame interval and returned-frame age p95 <= two intervals. Every returned frame must match an independently sequential-decoded reference for its assigned index; report actual indices, source fps, skipped frames, counts, call latency, and RSS. Aim for the clip's nominal cadence; report each reader's limit. Only this qualification decides whether to test B. Preserve stored orientation; the old clip benchmark rotates by 180 degrees, so its raw orientation must be recorded before semantic use.

Frozen scope: robot/camera.py, robot/test_camera.py, bench/camera_source.py; lead-owned eval/replay.py only for closing the shared source after all replay sessions. No model, prompt, memory, detector, voice, or OS changes. The design gate must pass before implementation. Builders never edit STATE.md or DECISIONS.md. Budget: under 2 MB code/results, existing 90 s shared/clips/live-items-1.avi only, no download. This clip is development-only; independent challenge sources remain unfrozen.

Jetson deploy at 07:06 UTC: release d7ed8b31a024, previous 51bdbb62cea6 retained; same boot, no qr units, 112 GB free, 6,037 MiB available. No model or benchmark job remains after qr-f0-evidence finished at 06:36:28 UTC. WSL GPU was idle at session reconciliation; its Ollama daemon and other project's container remain untouched. Recheck services/release before remote work.

Running jobs: Mac review gate finished PASS in 258.16 s; no Jetson qr job remains. qr-f0b-camera-source on d7ed8b31a024 ran 07:06:39–07:07:21 UTC, MainPID 250134, with per-second progress and successful unit exit. Result: bench/results/2026-10-09-camera-source-1791529599845132270.jsonl; paired tegrastats f0b-camera-source-20261009-030639.tegrastats; operational watchdogs in 2026-10-09-f0b-operations.jsonl. Builder /root/f0_video completed and is idle. Mac awake PID 37805, repo directory, caffeinate -dimsu, reviews/overnight-awake.log. Auth and hooks remain verified.

Changed paths: lead STATE.md, DECISIONS.md, research/sight.md, tools/gate.py and native diagnosis, and the new design review. Builder paths are active. Lead added replay source cleanup on success/failure; model lifecycle remains unchanged. D87 result review PASS: reviews/20261009-024234-70640-review.md. F0 evidence: bench/results/2026-10-09-bakeoff-evidence-probe-1791527749.jsonl and .judged.jsonl, operation/rubric records, and f0-evidence-20261009-023549.tegrastats. F0b full checks failed after 78 tests passed: the same ORT telemetry HTTP worker aborted at native shutdown. D85 workaround is intermittent; 030541.ips confirms the same worker. Official v1.30 source/docs show API suppression leaves its uploader alive. Gate now sets ORT_DISABLE_TELEMETRY=1 before imports; full checks passed in 13.29 s with clean exits (D89). F0b camera tests and local harness pass. Use .venv/bin/python for Mac model scoring; system Python 3.9.6 lacks zip(strict=True).

Unresolved: fresh 48-question challenge, 30-minute continuous baseline, source event contract, D75 unseen probes, and live active paging. research/one-voice.patch remains unapplied. F0's standalone upper bound establishes no deployed gain, held-out quality, integrated memory, or physical audible latency.

F0b measured: all 572 returned frames match independently decoded pixels. Latest() p95 detector/watcher/speech 15.38/14.11/15.07 ms, age p95 15.56/33.54/15.31 ms; each meets 66.67/133.33 ms limits. Union 14.8 fps from 15 fps source with six skipped indices; 83.34 MiB process peak RSS. Source-only qualification; integrated model throughput, memory, and semantic performance remain open. Carry detector source-error propagation in research/edge-cases.md (D71).

Next command: stage F0b code/evidence and D89 correction, commit after the required pre-commit checks, and push spike/overnight-2026-10-09. Review PASS: reviews/20261009-030935-4181-review.md; D90 adopts option A. Then freeze the independent challenge and source event contract. Verify the old raw clip orientation before semantic use.

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
