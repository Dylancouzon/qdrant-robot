# State

Updated 2026-10-09 by the lead. D127/D128 selective visual memory and verified names ship on protected spike/mac-audio-interface7a7f3db. Sol38457 PASS;22 focused checks pass. Jetson currentc182f8518376, previousb2b36d9718da; cd60 remains retained. Dylan restarted live testing. WSL quantization continues independently; main unchanged.

## Active task

Dylan reports orange ??? after object naming, missing recognized-person labels, and tiny background boxes. He confirms persistent visual memory should include only named or explicitly tracked objects; other objects stay temporary. Dylan explicitly preserves ignore/unignore rules across restart in the existing Things shard. Completed on protected spike/mac-audio-interface7a7f3db, deployedc182f8518376, never root rejected F1 source. Existing models/Edge/consent/deletion/rollback stay fixed. No full suite, full-suite hooks, or automated live tests; Dylan owns live testing. Topic research/mac-audio-interface.md and research/booth-ux.md; D43/D45/D51/D54/D56/D59/D64/D67/D124-D128.

Implemented D127/D128: source-frame object/face labels,64px-at1280 unknown-size gate, bounded existing-worker preview, text-only conversation, named source crops, RAM current sightings, pre-limit named/legacy visual filtering, and persistent independent ignore rules. No ambient visual writes or historical purge. Consent, thresholds, deletion, models, and configuration stay fixed. Sol3476 design conditions resolved;22 model-free checks pass6.62s/native0, changed-path Ruff/syntax pass, Sol38457 PASS176.21s/native0. Two optional edges are in research/edge-cases.md. Receipt bench/results/2026-10-09-selective-visual-memory.json. Physical qualification remains Dylan-owned.

## Jobs and machines

- Mac preview server PID48631 runs root .venv/bin/python /Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface/tools/talk.py --release c182f8518376; URL http://127.0.0.1:8765, log build/p2/logs/interface-server.log, PID file build/p2/logs/interface-server.pid. Chrome tab1202942054 is retained. Dylan approved stopping old qr-live-mac-f25e12d13bbc.service; its resources reaped and GPU lock was free. Page reopened Idle, microphone off, then Dylan selected Start. New qr-live-mac-1c5eb3448bee.service is Listening/active/view_ready true. Preserve his session. No agent live test. Receipt bench/results/2026-10-09-selective-visual-memory.json.

- Lead transport check qr-live-mac-transport-192903 finished: existing wake-3 recorded speech returned 75,759 PCM samples/3.156625s; independent Mac speech checker hears the embedded-Qdrant answer. Client native0; exact listening readiness; owned unit/tunnel/model/telemetry reaped, GPU lock free, cd60 unchanged. Evidence: bench/results/2026-10-09-mac-audio-transport.json and paired script/journal/WAV/tegrastats. Baseline logs BrokenPipeError on deliberate disconnect; no Robot edits or physical latency claim.

- Sole Mac builder /root/mac_audio_interface completed Sol6.1/high in /Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface. Protected source7a7f3db is reviewed, committed, pushed, and clean. Changed product paths: robot/main.py/focus.py/view.py/people.py/memory.py/things.py, focused tests, tools/talk.html, README. Original similar-instance/rename/restart/delete checks remain. Local22 checks pass6.62s; Sol38457 PASS176.21s. Lead read full diff. No full suite/hooks, agent live test, or WSL mutation. Lead owns shared records/deployment.
- Mac builder /root/trt_continue finished its handoff and stopped monitoring. It owns build/p2/trt-edge, spike/p2-trt-edge, base4d73264. Prototype0e5a484 is committed/pushed after PASS review and hook14.98s/native0. Focused checks passed9/one LFW-data skip; fullchecks passed15.88s/native0. Lead read brain/main/tests and pinned dependencies. Log: build/p2/logs/trt-full-checks.log.
- Mac Sol6.1 initial review57998 FIX/native3 is preserved. Scene-history eviction was fixed with complete exchanges and regression. Necessary continuous evaluator child-poll deletion preserves thread/detector/stall supervision. Corrected review67521 PASS102.05s/native0; final fullchecks15.30s/native0. Both receipts are archived in coordinator reviews. No engine/adoption claim.
- WSL corrected GPU retry started16:46:49EDT. Unit p2-trt-quantize-native-retry.service; invocationb9ec1e261ba04407938c9be35eec3f1d; flock128539/python128544. Directory: ~/qdrant-robot-box/experiments/p2-trt-edge. Command: flockgpu.lock venv/bin/tensorrt-edgellm-quantize llm --model_dir checkpoints/base --mtp_draft_dir checkpoints/assistant --output_dir checkpoints/int4-awq-native-retry --quantization int4_awq --device cuda. Logs: quantize-native-retry.log/quantize-native-retry-unit.txt. Exact models/MMMU128, verified extension, ownedPATH/CUDA/cache, MemoryMax22G/MAX_JOBS2. Latest read-only live diagnosis: same active unit/invocation/PID, memory8546201600B and unit swap0; no checkpoint directory. CurrentGPU10014/10240MiB at100%; paired py-spy local samples show different model layers and alpha settings inside first search sample. Search is advancing, not stuck; no ETA. Receipt bench/results/2026-10-09-wsl-awq-live-progress.json; raw locals stay ignored in build/p2/logs/wsl-live-locals-*.json. Activation collection completed 128/128 in 12:16; AWQ parameter search began and loaded the extension in 0.3 s. Search reports 0/128; checkpoint directory remains absent. Empty exit timestamp means pending, not native success. Host has 16 GiB available RAM and 6.2/7 GiB occupied swap; active paging is unmeasured. Assistant bundle is verified on Mac and now staged/extracted on Jetson. All 15 source files match hashes; base metadata is present, while base weights and engines remain pending. Boot5f4af7d6-879e-48eb-979a-45e715f1d626 unchanged. Other-project Docker/Ollama remain untouched. Estimated prep20–50GBU;777GB free.
- WSL sharing: this job holds /home/dylan/qdrant-robot-box/gpu.lock and occupies nearly all GPU memory. Another project may use separate directories and environments for light CPU work. GPU work must wait or acquire this same lock; separate folders do not isolate the GPU. Preserve this unit and other-project services. Dylan has resumed agent work. Latest successful receipt: bench/results/2026-10-09-p2-trt-resume-restored.json.
- WSL original unit18d496505 was interrupted for eager quantization resource correction. Extension compiled58.2s and passed actual FP16 CUDA INT4 comparison/native0. The next unitad37 completed 128/128 activations, began search, and loaded the extension1.4s before a premature operator stop. Preserve both as INTERRUPTED without checkpoint, never failed search/completed export. See D116-D119 and receipts below. One infrastructure retry is now active. CPU preparation remains counseled fallback for concrete resource/search failure, not elapsed time.
- Jetson boot09b4bb27-f975-441c-9d00-7af446ec7de6 unchanged. Deploy from protected candidate through tools/jetson.py: currentc182f8518376, previousb2b36d9718da, retainedcd60be65ee79. Six changed runtime hashes match;15 unchanged runtime/config hashes match cd60. Deployment loaded no model. Dylan then started qr-live-mac-1c5eb3448bee.service. Preserve it. TRT qualification still has no engine/inference result.
- Restricted-session resume failed before either connection; preserved in bench/results/2026-10-09-p2-trt-resume-access.json. Dylan restored full access. Both native SSH exits are now zero; boot IDs and baseline match. Receipt: bench/results/2026-10-09-p2-trt-resume-restored.json. Native stacks locate official compiled fake_tensor_quant_with_axis under CUDA launch; CPU time increases, while first search sample remains pending. Preserve the job. Assistant staging passes all 15 hashes and native exit zero. Native diagnostics and staging receipts: bench/results/2026-10-09-p2-trt-resume-diagnostics/manifest.json and p2-trt-assistant-staged.json.
- Last session Mac auth worked; usage was unavailable. Hooks are tools/githooks. Owned follow-up caffeinate2784 stops at handback; PID/log build/p2/logs/interface-followup-caffeinate.*. Owned prototype70737 stopped; previous interface helper34954 stopped at handback; log/PID: build/p2/logs/interface-caffeinate.pid. Owned resume caffeinate76612 stopped after staging; previous owned helper37805 stopped for the pause. External awake helper remains untouched. Luna /root/gemma_awq_artifact finished read-only research: checked official catalogs list no ready E2B INT4AWQ artifact. QAT-q4_0-unquantized is halfprecision source, not a verified AWQ shortcut. Astra164038 selects CPU fallback conditionally; new activation completion disproves the unchanged-progress premise. No additional design gate is required for that resolved resource choice.

P2-T continuation command: SSH to dylan@192.168.1.74, then run `systemctl --user show p2-trt-quantize-native-retry.service -p ActiveState -p InvocationID -p MainPID -p MemoryCurrent -p MemorySwapCurrent` and `journalctl --user -u p2-trt-quantize-native-retry.service --no-pager -n 12` in separate read-only calls. Check boot/job/checkpoint integrity before any restart. If export completes, hash and stage it as Jetson checkpointint4-awq with the verified paired assistant; build official llm+visual/GemmaMTP engines via tools/jetson.py onOrin, then actual text/image/speech/cancellation/fit and existing paired workloads. If preparation fails, preserve native receipts and apply counseled CPU fallback only on concrete failure. No elapsed-time stop. Resume is authorized and access is restored. Assistant staging is complete. Next exact command remains the read-only WSL service/journal reconciliation above; build waits for a valid quantized checkpoint. Do not infer completion or restart from elapsed time.
Interface next action: hand back the clean reviewed update and leave Dylan live session running. If he reports an issue, inspect only relevant private logs and resume the same sole builder on7a7f3db. Use the protected candidate for future deployment; never root rejected F1 source. Server48631, Chrome1202942054, currentc182f8518376, previousb2b36d9718da. Latest user unit qr-live-mac-1c5eb3448bee.service is Listening. No full suite or agent live test.
## Changes, findings, and evidence

TRT productpaths: robot/brain.py/main.py/test_brain_trt.py/test_speak.py/test_people.py. Necessary existing evaluator adaptation: eval/continuous.py/test_continuous.py deletes obsolete llama-child health polling; native worker failures remain covered by required Robot threads and stalls. Lead-owned pyproject.toml/uv.lock pins core TensorRT0.11.0 for Linuxaarch64 only; wheel447070745B/SHA9e6722a5 matches the verified asset. Server extras and compatibility switches are absent. Build profile is batch1/input2048/KV4096/draft&verify4/image512total512per-image(U). Official default externalization preserves checkpoint-backed PLE/embeddings and INT4FFN (D117). This does not establish integrated fit.

Receipts: bench/results/2026-10-09-p2-trt-interrupted-original-manifest.json plus raw logs/stacks; cuda-extension-manifest.json/log/unit/script; native-api.json/run/script; native-serialization.json/run/script; paired tegrastats. Latest retry interruption evidence is copied to build/p2/logs/trt-interrupted-native. Original pause status/journal/kernel/hash manifests and report remain in bench/results/2026-10-09-p2-trt-handoff*. The 18:01:51 sharing reconciliation is preserved separately in bench/results/2026-10-09-p2-trt-sharing-reconcile/. Verified222033920B assistant bundle remains build/p2/inputs/trt-transfer/assistant-metadata.tar, SHA9da354befc24230d158db2d2687e376265a42687d091c1dc7754605a3a64bd35;15 sourcefiles plus manifest. Review164038 records resource counsel; D119 corrects premature interruption. Read research/lessons.md after every compaction.

The split prototype9141a7b/4f6b920 remains reviewed and pushed on spike/p2-observer-dialogue. Integrated release78094c49f711 completes47 oracle turns but scores26/47 judged,30/47 keyword, with observed worker swap883100kB. Correct observations sometimes yield false dialogue replies. All47 archived WAVs independently transcribe within0.35WER/native0 on Mac; good rendering does not repair answer quality. Source-role39packet comparison scores21/39 in both arms, two recall wins/two absence/social losses. Reject adoption and another full replay for zero gain (D114). Owned debug unit/forward/model/telemetry jobs were reaped16:17; source branch is clean.

Granite Q4/Q8 fixed12packet diagnostics both score9/12(E); keep Q4 without1.45GB extra weights. Upstream KokoroFP16 fails actual Jetson warmup before turns; keep qualified FP32 CUDA. Preserve both FP16 failures; require counsel before a third route. Primary/raw/source-role/voice/model artifacts are in bench/results, with judgments separate from keyword scores.

## Prior decisions to carry

D110/F1j freeze completed/pushed1eda511. D111 supersedes its narrow implementation priority after Dylan requests architecture changes. Frozen answer contract and visual manifest remain research/answer-path.md and research/f1j-visual-inputs.json. Reopening requires a changed intervention.

D87 sufficient-source diagnostic improved2B14/24 to21/24, seven wins/zero losses; three failures remain below the training trigger. F0f/D96 qualifiedcd60 continuous baseline completes1800.187s/63utterances/72turns; judged10/48. First synth2.291/3.228s p50/p95; detector min13.408fps; headroom1062.56MiB; paging attribution remains unresolved. These are workload-specific development results, not acceptance or a cross-workload regression.

F1h oracle prototype54 to58/95 judged, but unchanged F1i47 recorded-audio comparison42 to39 rejects adoption, zero wins/three recall losses. Preservecd60 and rejected releases. F1i90s smoke does not establish quality, physical latency, or paging safety. Sources: research/answer-path.md/brain-capacity.md/event-delivery.md/lessons.md and D97-D110. No new evaluation harness or fixtures are authorized without an existing-tool limitation.

## Git

Lead spike/overnight-2026-10-09 tracks origin. UI source7a7f3db is reviewed, committed, pushed, and clean on spike/mac-audio-interface. Deployedc182f8518376; previousb2b36d9718da and retainedcd60. Root changes are records only; rejected F1 source and matching tests stay together. Earlier UIa7eeae3/b2b and audio dcb1e38/55c0ede remain in history. TRT0e5a484 and source-role4f6b920 remain clean reviewed spikes. Main eb746fe is unchanged. Root records D127/D128, review/check/deploy evidence, and WSL live-progress receipt; obtain checkpoint SHA from git log. No model acceptance is claimed.

D127/D128 implementation7a7f3db is reviewed, committed, pushed, and deployed. Dylan owns active live testing. WSL named quantization stays unchanged. Standing project approval permits reviewed spike commits/pushes; preserve main and rollback releases.

## Robot access

- 3080 box: `ssh dylan@192.168.1.74` (key auth; WSL2 Ubuntu 26.04; RTX 3080 10 GB; no passwordless sudo). X1 complete (D75). P1 found the GPU idle. Use `/usr/lib/wsl/lib/nvidia-smi` and `~/qdrant-robot-box/venv` (not `.venv`). Use its user-space CUDA 13.2.86 setup and llama.cpp 9c2e0e4; research/lessons.md records commands and partial answer parity. Acceptance numbers stay on the Jetson.

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN (192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback. Releases: /home/qdrant/qdrant-robot/releases/<hash>; shared models/memory/results. Currentc182f8518376, previousb2b36d9718da, retainedcd60/rejected038099d89da2. Dylan active qr-live-mac-1c5eb3448bee.service; preserve it. Verify models with python -m tools.models.
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
