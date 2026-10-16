# Gemma and Qwen full-stack fit

Gemma LiteRT fits the complete Jetson stack with CPU Kokoro, but this deployment loses answer quality and adds speech latency. Keep the current Qwen/CUDA deployment. The Qwen/CPU control shows the cost and headroom of CPU speech with uninterrupted generation. These are development measurements, with no product adoption or held-out acceptance. Intent parsing and tool execution optimization remain the next session's task.

All numbers in the following tables are J, measured on our Orin Nano Super 8 GB. Each arm completes 47 recorded questions and 120 bounded oracle stress turns. Each native command exits one because required quality steps fail; all 167 questions, both footers, and clean shutdown are verified. The [numeric audit](../../bench/results/2026-10-10-gemma-full-stack.json) includes percentiles, sample counts, commands, hashes, providers, paging, clocks, temperature, and process-tree measurements. This custom aggregate JSON is an explicit exception to the raw run-ID JSONL convention. Read it directly; tools/results.py reads the six underlying replay JSONL files.

## Recorded performance

| Deployment | Active headroom minimum, MiB | Decode median, tok/s | First WAV p50 / p95, s | Reply queued p50 / p95, s | Detection during synthesis / playback, fps |
| --- | --- | --- | --- | --- | --- |
| Current Qwen/CUDA Kokoro | 558.38 | 29.14 | 1.587 / 2.088 | 2.499 / 3.968 | 14.31 / 15.03 |
| Gemma LiteRT/CPU Kokoro | 1026.28 | 24.65 | 4.902 / 7.557 | 5.684 / 12.328 | 14.94 / 15.06 |
| Qwen/CPU Kokoro control | 992.20 | 28.67 | 3.377 / 4.998 | 6.788 / 12.798 | 14.96 / 15.06 |

Decode uses 12 text-only evidence packets at 128 output tokens while every component stays resident. Product replies use 2,048 context tokens, 64 output tokens, and the existing sentence cap. First WAV means the first synthesized phrase is ready. Reply queued means generation and synthesis finish. Neither is physical audible latency. Detection rates combine recorded and stress intervals; they are aggregate rates, not sustained acceptance. Detection during Qwen generation is unmeasured. Gemma generation averages 15.01 fps.

All arms fall below 15 fps during synthesis under instrumentation: current Qwen/CUDA 14.31 fps, Gemma/CPU 14.94, and Qwen/CPU 14.96. The current Qwen/CUDA arm has the largest measured shortfall. This placement-policy comparison does not isolate its cause. Sustained physical detection remains unqualified.

## Answer and speech quality

| Deployment | Judged recorded answers | Speech matches | Joint unsplit passes | Judged diagnostics | Judged / speech / joint stress passes |
| --- | --- | --- | --- | --- | --- |
| Current Qwen/CUDA Kokoro | 39/47 | 44/47 | 36/47 | 8/12 | 108 / 105 / 93 of 120 |
| Gemma LiteRT/CPU Kokoro | 31/47 | 46/47 | 29/47 | 9/12 | 81 / 100 / 61 of 120 |
| Qwen/CPU Kokoro control | 39/47 | 44/47 | 36/47 | 8/12 | 104 / 104 / 88 of 120 |

| Capability | Current Qwen/CUDA | Gemma/CPU | Qwen/CPU control |
| --- | --- | --- | --- |
| knowledge | 6/6 | 6/6 | 6/6 |
| recall | 3/6 | 1/6 | 3/6 |
| sight | 23/26 | 15/26 | 23/26 |
| social | 7/9 | 9/9 | 7/9 |

CPU Qwen adds 1.790 s median and 2.910 s p95 latency to first synthesized audio versus current Qwen/CUDA. Gemma adds another 1.526 s median and 2.558 s p95 versus CPU Qwen. That exceeds the frozen CPU-control allowances of 0.3 s and 0.5 s.

Gemma has two paired recorded wins and 10 losses against current Qwen/CUDA. Its preliminary text-evidence gain does not survive this recorded vision comparison. All arms use the same frozen three-vote gpt-6-sol evaluator and exact-answer cache.

Qwen/CPU preserves recorded quality, but stress judged passes fall from 108 to 104 and joint passes from 93 to 88. Paired stress judgments lose four answers with zero wins; joint scoring loses six and wins one. Pause removal or run variation could explain these differences; the cause remains unverified.

Speech matches use independent Parakeet CPU transcription on Mac and the existing WER ceiling of 0.35. Joint passes require judged text, matching speech, and unsplit input. WER compares transcript words with generated text. Semantic audio grading remains unmeasured. One recorded question splits in each arm; its last subturn supplies latency, and joint scoring fails it.

## Complete headroom and paging

| Deployment | Recorded minimum / median, MiB | Stress minimum / median, MiB | Active peak tree swap, MiB | Recorded swap in / out, pages | Stress swap in / out, pages |
| --- | --- | --- | --- | --- | --- |
| Current Qwen/CUDA Kokoro | 715.49 / 794.76 | 558.38 / 628.23 | 113.74 | 139 / 24093 | 40 / 5408 |
| Gemma LiteRT/CPU Kokoro | 1045.34 / 1124.14 | 1026.28 / 1062.00 | 0.00 | 5 / 7 | 10 / 1 |
| Qwen/CPU Kokoro control | 999.09 / 1075.86 | 992.20 / 1049.24 | 0.00 | 20 / 42 | 11 / 3 |

MemAvailable measures headroom for the entire board. Resident components include the detector, face/crop encoders, BGE, in-process Edge, Parakeet, VAD, TTS, history, audio queues, and telemetry. CPU and GPU share RAM. Process RSS/PSS overlap driver allocations and cannot be added to GPU memory. Every arm passes the 500 MB reserve, which equals 476.84 MiB. Every arm misses the measured zero-turn-paging target, including both CPU arms with zero process-tree VmSwap. The counters cannot identify the responsible process.

| Deployment | Recorded turn/playback windows with system paging | Stress turn/playback windows with system paging |
| --- | --- | --- |
| Current Qwen/CUDA Kokoro | 36/48 | 23/120 |
| Gemma LiteRT/CPU Kokoro | 9/48 | 5/120 |
| Qwen/CPU Kokoro control | 10/48 | 5/120 |

Each recorded arm has 48 actual turns from 47 questions because one question splits. System counters bracket each turn and playback window with nominal 250 ms samples. These counts include that sampling boundary uncertainty. The paging totals in the preceding table cover each complete workload, including gaps between turns.

| Deployment | Robot ready, s | Component exercise minimum, MiB | First diagnostic minimum, MiB | Shutdown, s |
| --- | --- | --- | --- | --- |
| Current Qwen/CUDA Kokoro | 17.918 | 933.96 | 933.11 | 0.748 |
| Gemma LiteRT/CPU Kokoro | 22.262 | 2373.03 | 1406.30 | 0.953 |
| Qwen/CPU Kokoro control | 15.196 | 1438.30 | 1416.14 | 0.752 |

Startups are process-cold with uncontrolled existing operating-system caches. Gemma minimum headroom changes from 2,373 MiB during component exercise to 1,406 MiB during first text diagnostics, then 1,045 MiB during recorded vision. Full activation must precede fit conclusions. The auxiliary clock logger starts partway through the baseline; early baseline GPU-clock coverage is missing. Baseline collector wall time is 79 ms median per 250 ms interval, versus 94 ms for Gemma. These instrumented results do not establish uninstrumented performance.

## Frozen comparison and limits

The staged source ec7eae92a682 comes from d2f929d. All 26 robot/*.py files match the current release 7f67670fa91e byte-for-byte. Only private adapters and instrumentation change. Qwen/CUDA preserves its current first-phrase pause/resume. CPU Kokoro explicitly uses CPUExecutionProvider, six intra-op threads, and one inter-op thread, with uninterrupted generation.

Gemma idle prefill is a no-op; real turn latency includes conversation setup and inference. Both receive the same 672-pixel JPEG preprocessing. Qwen caps image tokens at 256; LiteRT exposes native 70/140/280 adapters without an exact 256-token control.

The existing Robot and replay supply 21 recorded sessions with their normal resets. The stress fixture flattens 20 repetitions of the existing six-turn m2-evict-color session into one 120-turn session. It performs no internal reset or restart. Its repeated green statement cannot establish unique occurrence provenance or arbitrary long-conversation quality.

Real face embeddings and crop batches one through eight are exercised through Recognition. Component warmups cover BGE lengths one through 29, ASR inputs one through 14 seconds, VAD, and TTS lengths one through 39 words. The longest TTS warmups exceed the product 18-word phrase cap and remain diagnostics.

Recurring still frames have fresh paced 30 Hz timestamps so recognition stays active. This private fixture adapter addresses a stale FileCamera timestamp during measurement; main stays unchanged. Physical camera health separately records 64 frames over five seconds, including startup, with mean brightness 99.96.

The browser preview stays paused. File fixtures replace live camera input. Playback sleeps for generated audio duration and does not use a physical speaker. Live device and preview overhead remain unqualified. Native cancellation drains callbacks before conversation deletion; caption abort, subsequent replies, CPU settings, and clean close pass the adapter smoke.

The initial Qwen/CUDA attempt stops before replay answers with signal 15/wrapper 143 because descendant telemetry is incomplete. The Jetson omits task/*/children. PPid-based discovery passes a real parent/child check before the single infrastructure retry. Preserve both receipts; no quality failure is retried.

All stores, temporary files, logs, and SDK caches are isolated. Production memories, current/previous links, accepted models, global swap, and the paused preview stay unchanged. Incidental main-runtime gaps are logged in [known gaps](edge-case-records-2026-10-15.md#full-stack-model-comparison-observations-2026-10-10).

Gemma misses the frozen four-net-win/no-capability-loss requirement, the joint baseline floor, and both 2.5 s p50/4.0 s p95 synthesized-audio ceilings. The 24 tok/s allowance applies only if quality improves substantially. Every arm misses the measured zero-turn-paging target. No arm establishes every final target. Physical audible latency, held-out 90% per capability, stranger identity safety, sustained 15 fps detection, and Edge p99 remain unqualified. Restart/deletion, offline cold start, and eight-hour M4 also remain unqualified.

## Earlier screen and sources

The [preliminary screen](https://github.com/Dylancouzon/qdrant-robot/blob/9751bb69b2f637b5a7cf7ed7d25ee9d8cab9cef7/bench/results/2026-10-10-gemma-litert-screen.json) scores Jetson Gemma nine/12, fresh WSL Qwen seven/12, and WSL CPU Gemma six/12. Its two wins miss the original three-win rule. Dylan explicitly overrides that stopping rule for this full-stack comparison. Standalone Gemma measures 29.69 tok/s with every other robot model stopped. WSL preparation and CPU screening accelerate compatible work; software Vulkan fails on WSL, so acceptance fit/speed stays on Jetson. Native TensorRT unchanged weights exceed physical RAM and remain excluded.

Gemma uses litert-community/gemma-4-E2B-it-litert-lm revision b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1, full 2,588,147,712-byte bundle SHA256 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c, and LiteRT-LM 0.18.0. Qwen uses the pinned Q4_K_M GGUF and Q8_0 vision projector; all component pins and installed providers are in the audit.

The [design review](../../reviews/20261010-140209-99264-design.md) returns GO WITH CHANGES; the final [Claude Code Opus 5.5 review](https://github.com/Dylancouzon/qdrant-robot/blob/9751bb69b2f637b5a7cf7ed7d25ee9d8cab9cef7/reviews/20261010-opus55-full-stack-final-review.md) passes. Required source checks pass native zero in 94.40 s. STATE.md records closing check and commit receipts.

Private evidence stays under build/gemma-fit-20261010/full-stack/jetson-evidence. It includes native receipts, bounded logs, telemetry, providers, source/model/script/fixture hashes, original rows, exact-answer judgments, output WAVs, and speech sidecars. No private prompts, replies, images, or voices appear in the public numeric audit.

Official upstream references: [model bundle](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm), [LiteRT 0.18.0 SDK source](https://github.com/google-ai-edge/LiteRT-LM/tree/v0.18.0/python/litert_lm), and [pinned package](https://pypi.org/project/litert-lm-api/0.18.0/). Prior decisions remain in DECISIONS.md; runtime history is in research/stack.md and research/jetson-trt.md.
