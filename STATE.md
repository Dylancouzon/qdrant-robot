# State

Updated 2026-10-10. Checkout: /Users/dylanc/Documents/GitHub/qdrant-robot. Branch: spike/llm-experiments. The authorized Gemma/Qwen full-stack comparison is complete and reviewed. The closing commit and push are next. Intent parsing and tool execution optimization remain next session only. The live preview remains paused.

## Read first

Read CLAUDE.md, research/lessons.md, research/gemma-fit.md, research/experiments.md, and the final Gemma entries in DECISIONS.md. Read research/answer-evidence.md for the next session. Main preserves accepted runtime 011f522, planning 26fed40, and archived rejected experiments.

## Outcome and acceptance

Dylan authorizes Gemma with CPU Kokoro and accepts about 24 tok/s if quality improves substantially. He overrides the preliminary stopping rule and requests current Qwen/CUDA as the primary baseline. Qwen/CPU is the separate placement-policy control. Incidental main-runtime bugs stay unchanged and go into research/edge-cases.md. This session changes private instrumentation and evidence records only.

Each arm completes 47 recorded questions and 120 bounded oracle stress questions, both footers, and clean shutdown. Native quality exits are one because required steps fail. Comparison completion checks pass; model/product acceptance does not. All 26 staged robot/*.py files match the accepted release byte-for-byte. Core private script, fixture, and boot hashes match across arms.

| Deployment (J) | Active headroom minimum, MiB | Decode median, tok/s | First WAV p50/p95, s | Recorded judged/speech/joint passes | Stress judged/speech/joint passes |
| --- | --- | --- | --- | --- | --- |
| Current Qwen/CUDA Kokoro | 558.38 | 29.143 | 1.587/2.088 | 39/44/36 of 47 | 108/105/93 of 120 |
| Gemma LiteRT/CPU Kokoro | 1026.28 | 24.648 | 4.902/7.557 | 31/46/29 of 47 | 81/100/61 of 120 |
| Qwen/CPU Kokoro control | 992.20 | 28.674 | 3.377/4.998 | 39/44/36 of 47 | 104/104/88 of 120 |

Keep current Qwen/CUDA. Gemma gains two recorded answers and loses 10; sight scores 15/26 versus Qwen 23/26. CPU Qwen preserves recorded judgments but adds 1.790 s p50/2.910 s p95 first-audio latency. Its stress run loses four net judged answers and five net joint passes, with unverified cause. Gemma adds another 1.526/2.558 s versus CPU Qwen. The 24 tok/s allowance does not waive the quality miss.

All arms pass the sampled 500 MB reserve, equal to 476.84 MiB. Active tree VmSwap peaks at 113.74 MiB for current Qwen and zero for both CPU arms. Recorded system swap in/out is 139/24,093 pages for current Qwen, five/seven for Gemma, and 20/42 for CPU Qwen. Stress in/out is 40/5,408, 10/one, and 11/three.

Every arm misses the measured zero-turn-paging target. Recorded turn/playback windows with paging are 36/48, nine/48, and 10/48; stress windows are 23/120, five/120, and five/120. One recorded question splits into two turns, so each recorded denominator is 48. Nominal 250 ms sampling brackets these windows; process attribution remains unknown. The page totals cover entire workloads, including gaps.

Detection during synthesis/playback is current Qwen 14.31/15.03 fps, Gemma 14.94/15.06, and CPU Qwen 14.96/15.06. Every arm measures below the 15 fps detection target during synthesis under instrumentation. Sustained physical detection remains unqualified. Detection during Qwen generation is unmeasured; Gemma generation averages 15.01 fps.

The model stack includes YOLOE-26S, face/crop encoders, BGE, in-process Edge, Parakeet/Silero, TTS, camera fixtures, history, and audio queues. CPU voice uses six intra-op/one inter-op threads and uninterrupted generation; current Qwen/CUDA retains pause/resume. Gemma idle prefill is a no-op. Both receive the same 672-pixel JPEG; Qwen caps image tokens at 256, while LiteRT uses native 70/140/280 adapters. Diagnostics use 128 output tokens without speech; product replies retain 2,048 context/64 output/one sentence.

Live device and browser-preview overhead remain unqualified. WAV readiness and paced playback do not establish physical audible latency. Recorded sessions reset normally; stress repeats the same six-turn fixture 20 times in one session. This repetition establishes neither unique occurrence provenance nor arbitrary long-conversation quality.

## Evidence and review

Public numeric audit: bench/results/2026-10-10-gemma-full-stack.json. Detailed measurements and limits: research/gemma-fit.md. Private raw evidence: build/gemma-fit-20261010/full-stack/jetson-evidence/{qwen-cuda-retry,gemma-cpu,qwen-cpu}. Native receipts, logs, telemetry, providers, commands, hashes, original rows, judgments, WAVs, and speech sidecars are retained. Private media, prompts, replies, voices, and stores remain ignored.

Gemma uses revision b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1, full 2,588,147,712-byte bundle SHA256 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c, and LiteRT 0.18.0. Actual Jetson NVIDIA Vulkan supplies generation. The preliminary screen remains separate: Jetson Gemma nine/12, WSL Qwen seven/12, WSL CPU Gemma six/12. Standalone 29.69 tok/s had other components stopped. WSL preparation and CPU screening accelerate compatible work; software Vulkan fails there. Native TensorRT unchanged weights exceed physical RAM.

The design review reviews/20261010-140209-99264-design.md returns GO WITH CHANGES/native three. Its execution findings are resolved before runs. Adapter smoke passes native zero, including cancellation/drain, caption abort, subsequent replies, provider/thread settings, and close. Physical camera health passes native zero: 64 frames over five seconds including startup, mean brightness 99.96. Main FileCamera timestamps, missing recall evidence, and VAD/ASR splitting remain logged gaps.

The initial baseline stops before replay answers with signal 15/wrapper 143 because descendant telemetry is incomplete. PPid discovery passes a parent/child check before one infrastructure retry. Preserve qwen-cuda-interrupted; no quality failure is retried. All speeds include nominal 250 ms telemetry; collector median wall time is 79 ms for current Qwen and 94 ms for Gemma. Uninstrumented speed and early baseline sysfs GPU-clock coverage remain unmeasured.

Dylan selects Claude Code Opus 5.5 instead of the default Sol task reviewer and chooses background execution. Canonical claude-opus-5-5 is verified; frozen three-vote gpt-6-sol answer scoring stays unchanged. Reviews review-mv2tghdr-pd4tj0 and review-mv2tozcr-uzq6p8 return PASS WITH CHANGES. Their findings are resolved, and two reviewer count errors are corrected with evidence. Final review review-mv2tsr0d-ads48c returns PASS with no blockers; preserve reviews/20261010-opus55-full-stack-final-review.md and both earlier verbatim reports. Its small wording nits are resolved without changing results.

Required source checks pass native zero in 94.40 s, build/gemma-fit-20261010/full-stack/checks.log. All six raw replay files pass tools/results.py completion and exact-judgment checks. The aggregate JSON is an explicit format exception and must be read directly. The closing commit hook remains required.

## Machines and terminal jobs

Jetson: ssh robot, /home/qdrant/qdrant-robot, shared/gpu.lock. Boot remains 09b4bb27-f975-441c-9d00-7af446ec7de6. Current releases/7f67670fa91e and previous releases/6781adbb7189 remain unchanged. Power remains MAXN_SUPER mode two. Source ec7eae92a682 is staged from d2f929d without deployment; accepted venv e633f5c9aa5b supplies components. Post-run source/model/binary hashes, links, and boot verify; Jetson has 84.60 GB free.

Remote experiment root: /home/qdrant/qdrant-robot/shared/experiments/gemma-fit-20261010/full-stack. Units qr-gemma-full-qwen-cuda-20261010-retry, qr-gemma-full-gemma-cpu-20261010, qr-gemma-full-qwen-cpu-20261010, and qr-gemma-full-clocks-20261010 are terminal with MainPID zero. Native quality runs last 1,389.38/1,882.52/2,279.27 s. Each stage retains native-exit.json, native.log, memory.jsonl, tegrastats.log, and isolated runtime evidence. Adapter smoke/camera units are terminal/native zero. No owned inference process remains.

All WSL jobs are terminal: ssh dylan@192.168.1.74, /home/dylan/qdrant-robot-box, gpu.lock. All Mac judges, speech transcription, publication, and check jobs are terminal. All three Claude forwarding children are terminal. Final native Claude session d7dd1c51-8dec-4078-adf3-be0ce63ef6a9 completes. Existing caffeinate PIDs 36781 and 65618 remain running; hooks/authentication/model selection are verified. No unrelated service changed.

Preserve remote stores and private evidence. Use rsync -aS for sparse files and exclude tmp/memory/cache during collection. Do not relaunch preview, change production stores/release links, alter global swap, shrink models, tune prompts, or retry quality failures.

## Changes and Git

Changed paths: STATE.md, DECISIONS.md, research/gemma-fit.md, research/lessons.md, research/edge-cases.md, research/experiments.md, bench/judge-cache.jsonl, bench/results/2026-10-10-gemma-full-stack.json, and four full-stack design/review records. No tracked runtime, fixture, or configuration change. The comparison review passes and all blockers are resolved. Standing project approval permits the closing commit and push. Main and deployment stay unchanged; checkpoints a33528a and d2f929d are already pushed.

Exact next command: git diff --check. Stage the listed record paths, inspect the staged diff, and commit through tools/githooks/pre-commit. Save its native receipt in build/gemma-fit-20261010/full-stack/commit.log, then push origin spike/llm-experiments. Record terminal commit/push receipts before ending the session.

## Next session: intent parsing and tool execution optimization

research/answer-evidence.md preserves the reviewed seven-session/30-turn plan and selected Location/Owner requirements. Compare explicit rules with current BGE source scores, keeping accepted Qwen fixed across parser arms. Measure source labels, entity/owner binding, action arguments/execution, and answers separately. Identity, consent, and mutations stay code-owned. Location capture, owner-aware keys/speaker binding, combined answers, and isolated knowledge/log paths need design review. Same-owner grouping and background isolation remain parked under D148.

Final live acceptance remains unqualified: physical audible 1.2 s p50/2.0 s p95, held-out 90% per capability, zero stranger identity claims, 30 tok/s decode, sustained 15 fps detection, Edge 10 ms p99, and complete live-stack reserve. The sampled model-stack reserve passes here; zero-turn paging and aggregate synthesis detection have measured misses. M4 also needs offline cold start, restart/deletion, and eight active hours.
