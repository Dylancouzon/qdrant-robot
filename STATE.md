# State

Last updated: 2026-10-09 02:05 EDT, by the lead. Rewrite, do not append.

## Active task

P1 planning is complete (D82). Implementation starts in the next autonomous session at F0 in research/capability-plan.md. Read D79 through D82 and research/lessons.md first. Raise the capability ceiling for sustained conversation, perception, and recall on 8 GB, with Qdrant Edge central. All deployed inference stays on the Jetson.

Dylan makes Jetson, WSL 3080, and Mac available for the next few hours. Sol is reviewer (explicit `--model gpt-6.1-sol`); Sol 6.1 low agents are fresh implementation workers; Luna does research. Use WSL wherever it accelerates work. Saved and independent real video supports nighttime comparisons. Physical camera/audio/echo checks remain separate. Measured OS changes on dedicated robot hardware are authorized with SSH and rollback preserved.

P1 review: Astra counsel GO WITH CHANGES resolved; Sol 6.1 PASS in reviews/20261009-015822-12641-review.md. The receipt names the exact plan SHA256. No model, runtime, OS, fixture, or raw benchmark changes occurred. Planning files: research/capability-plan.md, research/lessons.md, STATE.md, DECISIONS.md, and the two reviews. H1 baseline: fcfd32a.

Current options are hypotheses, not locked choices. Reassess after the first paired result and at least hourly (D81). Record exact evidence, decision, and reopening condition for each route. Preserve at least 75 minutes for final evaluation; drop unfinished optional branches before using that time.

| Route | Current status and selection condition |
| --- | --- |
| Source-linked Edge events and dialogue | Preferred first build: recency-only captions and lost conversation constrain the foundation. Compare direct retrieval before summaries. |
| Response distillation plus LoRA | Candidate: only if correct-evidence answers still fail and tiny train/export/image inference succeeds. Teacher targets plus LoRA already constitute response distillation. |
| Stronger pretrained detector | Candidate: compare nano/small at matched false positives on independent real frames. Diverse views and focused descriptions address distinct recognition/detail gaps. |
| Detector training | Deferred until reliable annotation, coverage, and a residual detector failure justify it. |
| Larger VLM/runtime or split text/vision | Open alternatives: qualify compatibility, measured quality, integrated headroom, and latency; earlier failures are evidence, not permanent bans. |
| OS/provider capacity changes | Eligible when a measured bottleneck blocks capability; no assumed RAM gain from service removal or disabling swap. |
| Logit/feature distillation | Deferred until response distillation exposes a specific limitation worth the extra alignment and resource cost. |

Still unresolved: D75's M2 gain from 39 to 44/74 is development-only until its unseen probes run; research/one-voice.patch remains unadopted. Live conversation paging has no established cause. Keep these limits visible during the new comparisons.

First evaluator brief: current FileCamera reads still images, so qualify paced video input before using external footage. Encode the 30-minute challenge in one continuous runtime instance; test restarts separately. Keep source groups and final answers out of training. Prior Objectron exclusions and the COCO manifest gap are in the plan.

Running jobs: none from P1; all researchers and reviews finished. Final read-only check at 06:05 UTC found Jetson release 4387936b8ee9, no robot/benchmark jobs, and the WSL GPU idle with no model loaded. WSL Docker daemon works; GPU-container passthrough is untested. Recheck jobs, release, ownership, and access before execution. H1's native pytest shutdown failure remains unresolved.

Next command: `python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6`, then F0's source contract, evaluator brief, and bounded training/export preflight. Do not repeat the broad brain/prompt sweep without a changed hypothesis. This session ends after committing the reviewed planning records.

## Where to read first

- research/capability-plan.md: the next autonomous session, priorities, source exclusions, worker roles, and stopping rules (D79, D80).
- research/lessons.md: every avenue explored and every pitfall, with decision links (CLAUDE.md rule: keep it current). Read it after this file.
- DECISIONS.md D35 to D75 (today's work); research/v1-plan.md (the adopted v1 plan); research/booth-ux.md (focus, screen, turn-taking); research/assistant-design.md; research/grounding.md (brain bake-off); research/edge-cases.md (logged, not fixed); research/faces.md, research/m2-design.md, research/m3-design.md, research/wakeword.md, research/sight.md, research/endpointing.md; research/one-voice.patch (retrieval-into-brain variant, not applied).
- gates/review.md rules 6 (overfitting), 7 (proportion), 8 (v1: log edge cases).

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

Standing approval to commit and push (CLAUDE.md). Remote `origin` = github.com/Dylancouzon/qdrant-robot (private). Working branch: main, starting P1 at fcfd32a. V1-E and H1 are merged and pushed. Commit only the reviewed planning documents and lead records in this session.

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
