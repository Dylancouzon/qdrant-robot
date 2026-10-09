# State

Updated 2026-10-09 by the lead. Dylan requests a pause after a reviewed, clean checkpoint. Keep the healthy named WSL quantizer running, preserve handoff details, then stop agent work. Main remains unchanged.

## Active task

P2-T builds Gemma4E2B INT4AWQ with its paired MTP assistant under official TensorRT Edge-LLM0.11.0 (D111-D119). Architecture work follows a decision, runnable code, and existing validation. Dylan selected gpt-6.1-sol/low builders. Native Orin runtime loading and request serialization pass; checkpoint, engine, and model inference remain pending.

The adapter replaces the product llama child with one native runtime. It keeps Edge, source provenance, retrieval, identity, consent, and deletion in the Robot process. It streams generation through speech because the native template cannot resume an unfinished assistant message. Cancellation joins the producer. Native text counts and compiled image bounds preserve context limits. Existing CUDAKokoro stays qualified.

Checkpoint acceptance requires actual Jetson text/image replies and synthesized speech through Robot, existing regressions, review, and preserved native receipts. Local/API checks do not prove inference, fit, cancellation during generation, quality, latency, or adoption. Keep all final targets visible. Production memory remains untouched; candidate runs use owned memories.

## Jobs and machines

- Mac builder /root/trt_continue finished its handoff and stopped monitoring. It owns build/p2/trt-edge, spike/p2-trt-edge, base4d73264. Prototype0e5a484 is committed/pushed after PASS review and hook14.98s/native0. Focused checks passed9/one LFW-data skip; fullchecks passed15.88s/native0. Lead read brain/main/tests and pinned dependencies. Log: build/p2/logs/trt-full-checks.log.
- Mac Sol6.1 initial review57998 FIX/native3 is preserved. Scene-history eviction was fixed with complete exchanges and regression. Necessary continuous evaluator child-poll deletion preserves thread/detector/stall supervision. Corrected review67521 PASS102.05s/native0; final fullchecks15.30s/native0. Both receipts are archived in coordinator reviews. No engine/adoption claim.
- WSL corrected GPU retry started16:46:49EDT. Unit p2-trt-quantize-native-retry.service; invocationb9ec1e261ba04407938c9be35eec3f1d; flock128539/python128544. Directory: ~/qdrant-robot-box/experiments/p2-trt-edge. Command: flockgpu.lock venv/bin/tensorrt-edgellm-quantize llm --model_dir checkpoints/base --mtp_draft_dir checkpoints/assistant --output_dir checkpoints/int4-awq-native-retry --quantization int4_awq --device cuda. Logs: quantize-native-retry.log/quantize-native-retry-unit.txt. Exact models/MMMU128, verified extension, ownedPATH/CUDA/cache, MemoryMax22G/MAX_JOBS2. Final16:56:16 receipt: sameactiveunit, memory8481345536B/unitSwap0, GPU10004MiB.1951/1951 tensors loaded16:53:32; activation cache began16:53:40. No completed calibration/search samples, checkpoint, or CPU unit yet. Assistant bundle is verified onMac. Boot5f4af7d6-879e-48eb-979a-45e715f1d626 unchanged. Other-project Docker/Ollama remain untouched. Estimated prep20–50GBU;777GB free.
- WSL original unit18d496505 was interrupted for eager quantization resource correction. Extension compiled58.2s and passed actual FP16 CUDA INT4 comparison/native0. The next unitad37 completed128/128 activations, began search, and loaded the extension1.4s before a premature operator stop. Preserve both as INTERRUPTED without checkpoint, never failed search/completed export. See D116-D119 and receipts below. One infrastructure retry is now active. CPU preparation remains counseled fallback for concrete resource/search failure, not elapsed time.
- Jetson boot09b4bb27-f975-441c-9d00-7af446ec7de6, current/previouscd60be65ee79. Lead reconciled17:01; no qr/model unit,99GB free. Official isolated wheel loads exact OrinJP72CUDA13sm87/TRT10.16 payload/native0. API docs and actual JPEG/text serialization/native cancel flag pass via immutable workflow. No model engine was loaded. Target GPU lease is free.
- Mac auth works; usage is unavailable. Hooks are tools/githooks. Caffeinate37805 remains active. Luna /root/gemma_awq_artifact finished read-only research: checked official catalogs list no ready E2B INT4AWQ artifact. QAT-q4_0-unquantized is halfprecision source, not a verified AWQ shortcut. Astra164038 selects CPU fallback conditionally; new activation completion disproves the unchanged-progress premise. No additional design gate is required for that resolved resource choice.

Next session command: SSH to dylan@192.168.1.74, then run `systemctl --user show p2-trt-quantize-native-retry.service -p ActiveState -p InvocationID -p MainPID -p MemoryCurrent -p MemorySwapCurrent` and `journalctl --user -u p2-trt-quantize-native-retry.service --no-pager -n 12` in separate read-only calls. Check boot/job/checkpoint integrity before any restart. If export completes, hash and stage it as Jetson checkpointint4-awq with the verified paired assistant; build official llm+visual/GemmaMTP engines via tools/jetson.py onOrin, then actual text/image/speech/cancellation/fit and existing paired workloads. If preparation fails, preserve native receipts and apply counseled CPU fallback only on concrete failure. No elapsed-time stop. Agent work is paused at Dylan's request; named WSL job continues.
## Changes, findings, and evidence

TRT productpaths: robot/brain.py/main.py/test_brain_trt.py/test_speak.py/test_people.py. Necessary existing evaluator adaptation: eval/continuous.py/test_continuous.py deletes obsolete llama-child health polling; native worker failures remain covered by required Robot threads and stalls. Lead-owned pyproject.toml/uv.lock pins core TensorRT0.11.0 for Linuxaarch64 only; wheel447070745B/SHA9e6722a5 matches the verified asset. Server extras and compatibility switches are absent. Build profile is batch1/input2048/KV4096/draft&verify4/image512total512per-image(U). Official default externalization preserves checkpoint-backed PLE/embeddings and INT4FFN (D117). This does not establish integrated fit.

Receipts: bench/results/2026-10-09-p2-trt-interrupted-original-manifest.json plus raw logs/stacks; cuda-extension-manifest.json/log/unit/script; native-api.json/run/script; native-serialization.json/run/script; paired tegrastats. Latest retry interruption evidence is copied to build/p2/logs/trt-interrupted-native. Final job status/journal/kernel/hash manifests and report are archived in bench/results/2026-10-09-p2-trt-handoff*. Verified222033920B assistant bundle remains build/p2/inputs/trt-transfer/assistant-metadata.tar, SHA9da354befc24230d158db2d2687e376265a42687d091c1dc7754605a3a64bd35;15 sourcefiles plus manifest. Review164038 records resource counsel; D119 corrects premature interruption. Read research/lessons.md after every compaction.

The split prototype9141a7b/4f6b920 remains reviewed and pushed on spike/p2-observer-dialogue. Integrated release78094c49f711 completes47 oracle turns but scores26/47 judged,30/47 keyword, with observed worker swap883100kB. Correct observations sometimes yield false dialogue replies. All47 archived WAVs independently transcribe within0.35WER/native0 on Mac; good rendering does not repair answer quality. Source-role39packet comparison scores21/39 in both arms, two recall wins/two absence/social losses. Reject adoption and another full replay for zero gain (D114). Owned debug unit/forward/model/telemetry jobs were reaped16:17; source branch is clean.

Granite Q4/Q8 fixed12packet diagnostics both score9/12(E); keep Q4 without1.45GB extra weights. Upstream KokoroFP16 fails actual Jetson warmup before turns; keep qualified FP32 CUDA. Preserve both FP16 failures; require counsel before a third route. Primary/raw/source-role/voice/model artifacts are in bench/results, with judgments separate from keyword scores.

## Prior decisions to carry

D110/F1j freeze completed/pushed1eda511. D111 supersedes its narrow implementation priority after Dylan requests architecture changes. Frozen answer contract and visual manifest remain research/answer-path.md and research/f1j-visual-inputs.json. Reopening requires a changed intervention.

D87 sufficient-source diagnostic improved2B14/24 to21/24, seven wins/zero losses; three failures remain below the training trigger. F0f/D96 qualifiedcd60 continuous baseline completes1800.187s/63utterances/72turns; judged10/48. First synth2.291/3.228s p50/p95; detector min13.408fps; headroom1062.56MiB; paging attribution remains unresolved. These are workload-specific development results, not acceptance or a cross-workload regression.

F1h oracle prototype54 to58/95 judged, but unchanged F1i47 recorded-audio comparison42 to39 rejects adoption, zero wins/three recall losses. Preservecd60 and rejected releases. F1i90s smoke does not establish quality, physical latency, or paging safety. Sources: research/answer-path.md/brain-capacity.md/event-delivery.md/lessons.md and D97-D110. No new evaluation harness or fixtures are authorized without an existing-tool limitation.

## Git

Lead spike/overnight-2026-10-09 tracks origin. Related handoff records pass Sol79168 review141.38s/native0 and are committed with this status file. Obtain the exact handoff SHA from git log. Main eb746fe remains unchanged. Root handoff preserves D116-D121/STATE/research and verified preparation/API/speech records. All worktrees are clean after the reviewed commits. TRT branch0e5a484 is reviewed, committed, pushed, and clean. Primary/source-role branch4f6b920 is clean. Acquisition worktree changes were restored after ignored archival copies.

Standing project approval permits reviewed spike commits/pushes. Keep unqualified candidates out of main. Commit implementation checkpoint only after taskreview passes; ongoing model preparation is not completed architecture acceptance.

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
