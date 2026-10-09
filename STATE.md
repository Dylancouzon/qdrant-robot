# State

Updated 2026-10-09 by the lead. Main remains unchanged.

## Active task

P2 implements architectural choices, then validates runnable code on existing workloads (D111/D112). Do not reopen evaluation planning. Dylan selected gpt-6.1-sol/low for further builders this session; completed Opus work stays.

Primary prototype: Granite4.0-H-Micro3B Q4_K_M dialogue plus SmolVLM2-500M Q8 observer, pinned llama.cpp9c2e0e491a822adae1f0b1c831adb4160057d24f CUDA/sm87/NO_VMM. Dialogue4K/128/three sentences; current evidence before complete-history eviction; history survives scene changes; question-directed observation uses exact speech-start source/time. Edge/actions/identity/consent/deletion/source-owned storage remain code-owned. No new schema, retention, fixtures, or harness. Qualified KokoroFP32CUDA remains after upstreamFP16 failed.

Acceptance for this checkpoint: actual source-backed sight/text replies and synthesized speech through Robot on Jetson; existing regression checks; main-flow taskreview; complete failure/evidence receipts. Production adoption requires measured quality/resource/privacy/latency qualification and is not claimed. Current integrated sight errors/process swap prevent adoption, but architecture selection stays open: exact logs show correct observations followed by false dialogue answers (stop sign→book, redbus→apple, current room→priorcat). Per Dylan, diagnose generic prompt/tool integration and hybrid-state/pause behavior before attributing failures to the architecture or observer size.

## Jobs and machines

- Mac: Opus primary builder finished/native0 in build/p2/observer-dialogue (spike/p2-observer-dialogue, base4d73264), report/log build/p2/logs/hybrid-report.md and hybrid-builder.jsonl. Lead read diff; builder checks114passed/one LFW-data skip, ruff/vulture/modules pass. Lead capture-label check3passed/one LFW skip. Caffeinate37805 active. Hooks tools/githooks; Claude/Codex auth works; remaining usage unavailable.
- Mac: primary corrected taskreview133843 PASS116.10s/native0; prototype9141a7b pushed after fullchecks/hook pass. Sol6.1/low /root/forget_history completed P2-R source roles in brain.py/test_budget.py plus one necessary test_people assertion. Ninepassed/one LFWskip, ruff/module/diff pass; lead read diff. Correct worktree taskreview31407 completedPASS131.78s/native0, log build/p2/logs/evidence-role-review.log. An accidental root-cwd review PID89324 was interrupted/native130 before verdict; never counts as review. No source changed during correct review; receipt140847 archived in coordinator reviews. Source committed/pushed4f6b920 after fullhook15.22s/native0; prototype worktree cleaned.
- Mac: source-role drivers/judging completed. SSH forward89078 closed/native0; owned Jetson debug stopped and collected, journal bench/results/2026-10-09-p2-granite-debug-journal.log, 4.4G unit peak/zero unit swap while standalone. No model/telemetry job remains from P2. Source-role spike4f6b920 clean. Luna report distinguishes source insufficiency and ignored sufficient observations; no new observer-context mechanism built.
- Jetson: reconciled16:17 boot09b4bb27-f975-441c-9d00-7af446ec7de6, current/previouscd60 baseline; reconnect reconciliation34012 complete; noqr units/model/tegrastats;101GB free. Integrated split pilot780 completes47/nativequality1,26/47judged/30keyword; workerVmSwap883100kB is not active-paging proof. Spoken output archived tar/hash manifest, existing fullturn/journal/model/tegrastats retained.
- WSL: boot5f4af7d6-879e-48eb-979a-45e715f1d626. GPU model units reaped after Q4/Q8/observer diagnostic;363MiB/0% at cleanup. Prior TRT builder /root/trt_runtime completed its preparation checkpoint; Sol6.1/low /root/trt_continue owns continuation in build/p2/trt-edge, spike/p2-trt-edge, and ~/qdrant-robot-box/experiments/p2-trt-edge; no Jetson access/shared edits. Officialv0.11.0 commit95515c2f87fba8982db5a519f9022277667b3cc9; OrinJP7.2/CUDA13.2/sm87/TRT10 supported. WSL Ampere quantization/CPU export supported; WSL engines are not Jetson acceptance.
- WSL: setup p2-trt-setup PID56754/invocation508ef473, cwd owned experiment, uv pip install --python venv/bin/python -e ./source[tools], journal/setup.log. Checkpoint download p2-trt-download PID57429/invocation9ff84e8, pinned Gemma base3e22461f65e89153144f8adb70e3b8c2cc9845a7/assistant2d874ef (builder supplies full revision); snapshot_download to owned checkpoints. Both acquisitions finished native0; setup environment has officialtorch2.13.0/transformers5.14.1/modelopt0.45.0. Builder now verifies hashes/imports and prepares actual quantization; Quantization p2-trt-quantize PID59725/invocation18d496505, cwd owned experiment, flock gpu.lock, tensorrt-edgellm-quantize llm --model_dir checkpoints/base --mtp_draft_dir checkpoints/assistant --output_dir checkpoints/int4-awq --quantization int4_awq --device cuda (512/defaultcalibration), journal/quantize.log. GPU leased to this job;9701MiB free at launch. WSL recovered13:49 with unchanged boot; quantizer remained active throughout. AWQ inserted1840quantizers and caches activation statistics on officialMMMU. GPU10016MiB/100%; unitmemory8.18GB/swap266KB. Kernel memory-pressure/dxg make_resident ioctl-12 observed; no nativeCUDA OOM, killed job, or export yet. Reconciled16:17 sameboot/invocation/PIDs, still parameter search from14:00 withGPU99%/9998MiB/unit8.24GB. No checkpoint;777GB diskfree. Inspect concrete progress/callstack and official CPU fallback before changing a healthy job. Builder monitors/preserves kernel evidence; no restart/retry. Initial --help during partial torch installation failed ImportError, diagnosed as installation timing; retry only after completed setup. Dependencies~15GB/preparation20-50GB U, WSL798GB free initially. All GPU work holds existing gpu.lock; lead owns Jetson lease/queue.

Next exact command: root checkpoint review161809 PASS138.88s/native0; commit archived reviewed P2 records, and continue official WSL quantizer without restart. Jetson officialwheel setupqr-p2-trt-runtime-setup completednative0 at16:19:48; loaded matchingOrinJP72CUDA13sm87 payload/TRT10.16.2.10. Artifacts bench/results/p2-trt-runtime-load.json, setupscript/journal/environment/tegrastats. No Gemmaengine/inference claim. Directwheel builder supports GemmaMTP+INT4AWQ; selected next nativebuild maxbatch1/input2048/KV4096/draft&verify4/externalizedint4FFN, valuesU engineeringlimits. Wait forusablecheckpoint; builder checks documented nativeFP16→weightonlyINT4 alternative without changingAWQ. No duplicateC++route. Jetsonleasefree; no activeownedunit/model. Rootreview64658 completedPASS; runtime completion/status findings incorporated; unchangedcode. Collected preexisting smoke duplicates match trackedfixture hashes and moved to build/p2/collected-existing-smoke, not newbenchmarks. Acquisition-only branch restored fromHEAD after preserving localreceipts.

## Changes, findings, and evidence

Primary branch edits models.json, robot/brain.py, robot/main.py, robot/test_people.py. All four official asset hashes verified on both machines. Acquisition release58c6b6bf816a retained. Initial double deploy changed previous; lead explicitly restored cd60 previous, then used workflow rollback. Product runs resolve immutable releases before immediate baseline rollback.

Upstream KokoroFP16 first integration6283246e9253 failed before turns/native1: empty audio in kokoro_onnx.pauses._quiet_frames. Evidence bench/results/2026-10-09-p2-fp16-startup-failure.log plus acquisition/pilot tegrastats. Restore qualifiedFP32, do not retry quality or take a third FP16 approach without counsel. D112 records this decision.

WSL E diagnostic: existing12 frozen F1h source packets, GraniteQ4/Q8 both9/12 judged versus previousQwen2B8/12. Same three failed IDs; Q8 adds1.45GB weights without diagnostic quality gain, so keepQ4. Both12/12 requests; no integrated/held-out/sustained/adoption claim. Smol recognizes existing clock image:6output/153prompt tokens. Evidence bench/results/2026-10-09-p2-granite-{q4,q8}-wsl.jsonl/.judged.jsonl and p2-smol-clock-wsl.json. Owned judge cache/build request scripts under build/p2/inputs; shared cache untouched.

Primary design GO WITH CHANGES reviews/20261009-131139-20233-design.md requires evidence-first budgeting and question-directed speech-start observation; implemented. Old P2 evaluation matrix/dispatch is superseded; do not execute it. research/architecture-choice.md holds selected/fallback sources; research/lessons.md records outcomes/pitfalls. The prototype base4d has baseline captions/statements, not rejected F1i source spans; WSL fixed sufficient packets diagnose model interpretation separately.

Lead root changes CLAUDE/STATE/DECISIONS/research records and collected evidence. Primary and TRT builders stay on isolated branches. No commit until taskreview passes; commit/push spike branches afterward. Do not integrate an unqualified candidate into main.

## Prior decisions to carry

F1j freeze-only task D110 completed/committed/pushed1eda511, no runtime edits. D111 supersedes its narrow implementation priority after Dylan requests architectural changes. Frozen answer contract/visual manifest remain research/answer-path.md and research/f1j-visual-inputs.json; reopening needs a changed intervention.

D87 sufficient evidence improved2B14/24→21/24, seven wins/zero losses; three remaining failures below eight-failure training trigger. F0f/D96 continuous cd60 baseline completes1800.187s,63utterances/72turns/69events; judged10/48 (sight6/12,older0/9,topic0/9,correction0/6,absence1/6,chat3/6). Raw2026-10-09-continuous-baseline-a.jsonl and judged/scoring/speech/operations hold full provenance. First synth2.291/3.228s p50/p95; min detector13.408fps; headroom1062.56MiB; paging unattributed. Original targets remain unmet.

F1h oracle prototype54→58/95 judged (M238→42/74, visitor16/21both), but F1i unchanged47 recorded-audio regression42→39,zero wins/three recall losses rejects adoption. Preservecd60; rejected038099d89da2 and435518db9947/fb9ba71bcf4e/d2955df8adf8 retained. F1i90s smoke passed but does not establish quality/no-paging/physical acceptance. Sources: research/answer-path.md, brain-capacity.md, event-delivery.md, lessons.md, D97-D110, archived f1h/f1i audit/native receipts. Existing data is development after use. Production shared/memory remains untouched; all runs use fresh run-owned memories.

## Git

Lead spike/overnight-2026-10-09 tracks origin; last committed1eda511. Main eb746fe unchanged. Standing project approval permits reviewed task commits/pushes. Isolated spike/p2-observer-dialogue contains runnable prototype; spike/p2-trt-edge owns preparation for the compiled alternative; no usable export/engine yet. Keep reviewed artifacts and exact next action at each checkpoint.

## Robot access

- 3080 box: `ssh dylan@192.168.1.74` (key auth; WSL2 Ubuntu 26.04; RTX 3080 10 GB; no passwordless sudo). X1 complete (D75). P1 found the GPU idle. Use `/usr/lib/wsl/lib/nvidia-smi` and `~/qdrant-robot-box/venv` (not `.venv`). Use its user-space CUDA 13.2.86 setup and llama.cpp 9c2e0e4; research/lessons.md records commands and partial answer parity. Acceptance numbers stay on the Jetson.

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN (192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. Current releasecd60be65ee79 restored; previouscd60be65ee79 also baseline, rejected038099d89da2 retained. No owned GPU/model unit remains onJetson. Recheck before execution. Models: `python -m tools.models` verifies `models.json`.
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
