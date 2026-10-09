# State

Last updated: 2026-10-09, by the lead. Rewrite, do not append.

## Active task

F1g is a rejected runtime experiment(D97–D105). Status cleanup passed Sol6.1 review. Commit/push its prototype and negative evidence on spike/overnight-2026-10-09. Branch/origin match26340e1, sixteen checkpoints; main stays eb746fe. Lead owns STATE, DECISIONS, integration, and machines. No delegated worker is active.

Current Jetson release is cd60be65ee79. Previous435518db9947 preserves the rejected candidate; olderfb9ba71bcf4e/d2955df8adf8 remain historical prototypes. Named-unit restoration completed. No qr unit or llama-server is active. Boot09b4bb27-f975-441c-9d00-7af446ec7de6; idleavailable6,036MiB/105MiB allocatedswap. Production shared/memory remains unopened; all measurements use run-owned memories.

Prototype changes: robot/main.py serializes eligible statement/caption indexing, selects source spans with frozen0.53/0.55 floors and observation past-only role, preserves ordinary code/identity/actions, logs exact final source spans. robot/brain.py enforces2K/64-output/256-image bound, drops lowest-ranked evidence then oldest complete history, records budget-call costs/prefill. eval/replay.py logs fields. Generic tests adapt privacy/ignore/sighting interfaces and verify bounds/source roles.137 local tests/full checks pass27.89s. No fixture/model/prompt/threshold/training change. The candidate is not adopted.

Unchanged47-step recorded-audio comparison: both releases complete47/47 in504.111s/518.102s, native1 preserves quality failures, clean group teardown, one split/48 outputs each. Baseline42/47 versus candidate41/47 judged, zero wins/one current-image reading loss with no stored source. Joint judged/single-turn/speech39/47→38/47; speech43/48 both. Keyword45/47→43/47 stays separate. Warm46 first synthp501.416→1.455s,p951.907→2.155s; all47p501.419→1.448s. No overall gain or speedup. Narrow instrumentation differs from baseline; no small causal timing claim.

Loaded sampled minimum headroom1,075/1,148MiB,minimum turn detect11.338/13.805fps. Loaded-interval system paging4,204in/39,057out versus4,045in/9,207out pages is unattributed to processes/turns. Candidate timing final maxima: first-stream delay1.099s,later streams0.122s,hear/VAD0.185s,budget0.059s,prefill1.143s. Reporter timing is unmeasured: observer wraps continuous Scheduler.report but this legacy replay uses reported(). No cause for the cold delay is identified.

Four delivered literal spans match complete source authority/hashes/final bounded prompts. Zero semantic observations reach generation in this workload because ordinary past-object code answers bypass it. F1f controlled source-to-answer22/32→30/32 remains valid, without general runtime gain. Reassess the ordinary answer path using D75/D77 and changed source selection; do not patch the one image case or expand calibration.

Initial candidatefb9 smoke fails frozen0.5s limit at46s with0.519s lateness; cleanup native-6 follows. Preserve incomplete raw/journal/tegrastats. Same retainedcd60 smoke completes90.100s/worker0,max0.197s. Strict smoke/native-6 remain unresolved adoption requirements. Astra counsel GO WITH CHANGES reviews/20261009-091830-51018-design.md applied narrow timing within the useful comparison; test-added tree mismatch caused exit3/no stamp. Adoption/final challenge/volume/safety expansion stopped(D105).

Evidence: bench/results/2026-10-09-replay-{1791552444,1791553079}.jsonl/ judged sidecars; rawSHA90e54d692eb02093948ff3fd362e1a56fe5816b4e7d4a08efd1bf5aa2ab17714/a2305a98db109f6e00dac5a9188fde86ee923dc8b4865a54985ade07d32464b6. F1g supervisor/console/telemetry/timing files, all-turn/speech-view/speech archives, operations.jsonl, archived executed runner/observer/paired-audit.py.txt bind inputs and all48WAVs each. Native0 paired audit passes; build/f1g preserves originals/WAVs. Failed initialPython3.9 judge strict zip is preserved; same-sourcePython3.12 retry completes. All judge/speech/check jobs finished.

Sol6.1 review FIX reviews/20261009-095148-87405-review.md independently reproduces all evidence and finds no blocking runtime/privacy/fixture-specific defect. Its sole blocker is contradictory STATE release/job/timing text; this rewrite resolves it. Carry fixed-input overflow killing worker/queue completion and unused retrieval on code turns in research/edge-cases.md. Do not fix them while this candidate is rejected. Focused cleanup re-review PASS reviews/20261009-095738-93704-review.md finished62.47s; the original blocker is resolved. No runtime repair or adoption claim.

Running jobs: none on Jetson or Mac after cleanup review. Commit/push under300s/120s is next. Mac caffeinatePID37805 active. WSL unused. Auth/hooks previously verified. Checks120s/stage,gates900s/group,deploy300s,collect/push120s,SSH45s outer/10s connect+keepalives,reap10s; healthy work has no total deadline(D83). Use .venvPython3.12 for product/judge/speech and systemPython only for stdlib orchestration. Preserve failures; diagnose before one infrastructure retry.

Adoption remains unmet: general/per-capability gain, strict smoke/native lifecycle, representative1,000queries per slot at4,500+multi-unit sources/20,000stress,M2/visitor/M3 safety,paging-free and sustained targets. Stop shipping this experiment. Next exact command: tools/gate.py review --model gpt-6.1-sol on STATE-only blocking cleanup, then commit/push the reviewed rejected checkpoint. Next architecture must improve evidence reaching ordinary answers with a paired general gain; compare alternatives before building. Read research/lessons.md,event-delivery.md,event-memory.md,D97–D105. tools/results.py rejects paired/continuous formats; targeted audits stay explicit.

## Completed overnight evidence

F0 diagnostic(D87): current14/24 versus sufficient21/24, seven wins/zero losses. Only three sufficient-evidence failures; deferLoRA under eight-failure trigger. F0b572/572 Jetson source pixels(D90); F0d90s integrated smoke qualifies timing/native completion(D93). D89 disables Mac check telemetry uploader before imports; every failure still fails. Original data/audio freezes remain unchanged(D91,D94). Jetson decoder710/710(D94).

F0f baseline complete/reviewed/pushed4d73264: Jetsoncd60,one process1,800.187s,63utterances/72turns/69events/28.8Msamples/12 of12probes,nativeworker0. Nine split utterances include four scored/five auxiliary failures; supervisor/unit1 preserves them. Never retry quality failures. Raw bench/results/2026-10-09-continuous-baseline-a.jsonl SHA f1acf67657bdaf3049b2715386bb38c5ab1077d8601c8ae24204c5a6045183c1; .judged/.scoring/.speech sidecars,2026-10-09-f0f-operations.jsonl,paired tegrastats, archived audit source. PASS reviews/20261009-052607-74465-review.md;115checks15.05s.

Baseline judged10/48: sight6/12,older0/9,topic0/9,correction0/6,absence1/6,chat3/6. Four scored splits fail directly;44valid three-vote judgments. Correction/topic source IDs do not prove sufficient facts; nine older sources have unknown prompt delivery. All72unique nonemptyWAVs transcribe within0.35WER; strict speech54/72 preserves18split-turn failures. No new language-training trigger established.

Baseline first synthesized audio2.291/3.228s p50/p95; detect13.408minimum/14.900medianfps; headroomminimum1,062.56MiB. Systempaging89in/852outpages,fully-active56in/16out,boundary0/1,idle33/835. Full speech/output windows classify intervals, without runtime attribution. SampledVmSwap0 proves no absence of paging. Physical latency,15fps,no-paging,quality targets remain unmet.

Unmet: source contract/integrated gain, D75 unseen probes, exact rendered prompt tokens, sustained quality, paging attribution, physical audible latency, and eight-hour active acceptance. research/one-voice.patch remains unapplied. tools/results.py rejects continuous/decoder formats; targeted audits stay explicit.

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
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. Current release cd60be65ee79; previous435518db9947 retains the rejected F1g candidate. No robot unit/model is active after F1g. Recheck before execution. Models: `python -m tools.models` verifies `models.json`.
- Acceptance run from the Mac: `python3 eval/run.py [--model M] [--oracle | --audio audio-real] [cases]` deploys, replays, collects, judges, and checks speech. Real-voice fixtures: `tools/record.py <cases> [--check]`.

## Finding your way in the evidence

- Compact history: `python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6`. It keeps judged answers, keyword checks, and evidence scores separate, with machine, release, mode, and incomplete judging visible. Inspect individual raw rows only for the question being resolved; README.md documents filters and supported formats.
- `<result>.judged.jsonl`: one verdict per turn (`pass`, `why`). `*.tegrastats`: memory, clocks, temperatures, named `<job>-<date>-<time>.tegrastats`; a result's summary row names its file. Files without a date are from before 2026-10-08 04:00.
- `tools/gate.py checks` runs ruff, vulture, pytest, the module self-checks (`python -m robot.<module>`), and the tool selftests. The pre-commit hook runs it.

## Robot facts (2026-10-08)

- L4T R39.2.0, Ubuntu 24.04.4, Python 3.12.3, headless. CUDA 13.2.2, cuDNN 9.20, TensorRT 10.16.2 from apt. llama.cpp 9c2e0e4 built with `GGML_CUDA_NO_VMM=ON` in `shared/src/llama.cpp`. Details: `research/stack.md`.
- Power: MAXN_SUPER (D31): GPU 1,020 MHz, EMC 3,199 MHz, CPU 1,728 MHz. Qwen3-VL-2B decode 36.0 tok/s, prefill 1,492 tok/s. The 15W thermal test peaked at 59.9 °C; the MAXN thermal test is pending.
- RAM 7,485 MB; about 6,000 MB available idle (D20). 8 GB swap file. NVMe about 105 GB free.
- Camera: mounted upside down, frames rotated 180° in `robot/camera.py`; 16 fps at 1280x720 MJPG. The USB hub disabled its port once under MAXN (D32): watch for recurrence; a reopen watchdog is unowned. Microphone: the camera's (ALSA `plughw:CARD=Light`). No speaker: answers are saved as WAVs.
- Services: `l6-robot.service` stopped and disabled (D18); `memory-robot-clock.service` kept.

## Git

Dylan requests commits and pushes throughout this overnight session. Working branch: spike/overnight-2026-10-09, from main eb746fe, tracking origin/spike/overnight-2026-10-09. Main is unchanged. Commit each reviewed task with its evidence and push this branch. Remote origin is github.com/Dylancouzon/qdrant-robot (private).

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
