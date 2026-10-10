# State

Updated 2026-10-10. Checkout: /Users/dylanc/Documents/GitHub/qdrant-robot. Branch: main. Closure review and checks are complete. Main fast-forwards from 5041aa9 to ac878a9. Active task: push main and the archive tag, verify remote targets, and retire the completed spike branch. Dylan explicitly authorizes this merge. Intent parsing and tool execution optimization start next session only. The live preview stays paused.

## Read first

Read CLAUDE.md, this file, research/lessons.md, and research/experiments.md. The completed model comparison is research/gemma-fit.md. The next-session plan is research/answer-evidence.md. The latest DECISIONS.md entries record model retention, review resolutions, and session reconciliation.

## Settled architecture and findings

Keep Qwen3-VL-2B on llama.cpp, CUDA Kokoro with first-phrase pause/resume, and the accepted detector, voice-input, recognition, and Edge layout. Main preserves accepted runtime 011f522 and planning 26fed40. No runtime, prompt, model, fixture, configuration, or deployment change is adopted.

| Deployment (J) | Minimum active headroom, MiB | Decode median, tok/s | First WAV p50/p95, s | Recorded judged answers | Stress judged/joint passes |
| --- | --- | --- | --- | --- | --- |
| Current Qwen/CUDA Kokoro | 558.38 | 29.143 | 1.587/2.088 | 39/47 | 108/93 of 120 |
| Gemma LiteRT/CPU Kokoro | 1026.28 | 24.648 | 4.902/7.557 | 31/47 | 81/61 of 120 |
| Qwen/CPU Kokoro control | 992.20 | 28.674 | 3.377/4.998 | 39/47 | 104/88 of 120 |

Each arm completes 47 recorded questions and 120 bounded oracle stress questions, both footers, and clean shutdown. Native quality exits are one because required steps fail. Gemma loses eight net recorded answers and adds speech latency. CPU Qwen reduces paging but adds 1.790 s p50/2.910 s p95 first-audio latency; its stress losses have unverified cause. CPU policy also removes generation pauses, so this comparison measures the complete voice policy.

All arms pass the sampled 500 MB model-stack reserve and miss zero-turn paging. Recorded paging windows are 36/48, nine/48, and 10/48; stress windows are 23/120, five/120, and five/120. A split question creates 48 actual recorded turns. Nominal 250 ms samples bracket turn/playback windows; counters cannot identify the responsible process. Every arm measures below 15 fps during synthesis under instrumentation. Live device/preview overhead, physical audible latency, and sustained physical detection remain unqualified.

The full audit is bench/results/2026-10-10-gemma-full-stack.json. The preliminary screen is bench/results/2026-10-10-gemma-litert-screen.json; its standalone speed and WSL scores remain separate. Development measurements establish no held-out or eight-hour acceptance. Main FileCamera timestamps, missing recall evidence, and VAD/ASR splits stay logged in research/edge-cases.md, without fixes.

## Reconciliation and evidence

Pre-merge main is 5041aa959234e8f57d868a794345e9108f41c879. The authorized fast-forward merges the experiment and closure records at ac878a9. Robot, tools, eval, and configuration match main. README links the model finding and next-session plan. The experiment index places Gemma under completed avenues; lessons separate preliminary screening, measurement pitfalls, and the full-stack result.

Local archive tag archive/2026-10-10/llm-experiments preserves checkpoint 18d46e8504f692905ff3e35888ea8ae58c9da63c. The head manifest research/archive/experiment-heads-20261010.json indexes it with the eight earlier archive heads. All nine tag targets and Git connectivity verify. Private evidence stays ignored under build/gemma-fit-20261010 and build/reconciliation-20261010; no evidence moves or deletions occur.

Closure verification build/gemma-fit-20261010/closure/verification.json confirms 42 private evidence hashes, all six complete replay files with exact judgments, local document links, and archive heads. Raw full-stack evidence remains build/gemma-fit-20261010/full-stack/jetson-evidence/{qwen-cuda-retry,gemma-cpu,qwen-cpu}. It includes commands, native receipts, logs, telemetry, providers, script/model/fixture hashes, rows, judgments, WAVs, and speech sidecars. Private prompts, replies, images, voices, stores, and credentials stay ignored.

Completed comparison review reviews/20261010-opus55-full-stack-final-review.md passes with no blockers. Dylan selects Claude Code Opus 5.5 for this session, with background execution; frozen gpt-6-sol answer scoring stays unchanged. The comparison commit hook passed native zero in 93.29 s. Closure review reviews/20261010-opus55-session-closure-review.md approves the reconciliation. Its pending-status findings are resolved by the appended decision receipt and the final status rewrite on main before the push. The closing commit hook passes native zero in 93.49 s. Commit ac878a9 completes native zero; closure/commit.log and closure/commit-receipt.json retain the output, command, and timing.

## Machines and jobs

Jetson: ssh robot, /home/qdrant/qdrant-robot, shared/gpu.lock. Boot 09b4bb27-f975-441c-9d00-7af446ec7de6, current releases/7f67670fa91e, and previous releases/6781adbb7189 verify unchanged. Power remains MAXN_SUPER mode two. Staged source ec7eae92a682 and accepted venv e633f5c9aa5b remain available. Remote evidence stays in shared/experiments/gemma-fit-20261010/full-stack.

Units qr-gemma-full-qwen-cuda-20261010-retry, qr-gemma-full-gemma-cpu-20261010, qr-gemma-full-qwen-cpu-20261010, and qr-gemma-full-clocks-20261010 are inactive with MainPID zero. Earlier smoke/camera and interrupted-stage receipts remain preserved. All WSL experiments are terminal; access ssh dylan@192.168.1.74, /home/dylan/qdrant-robot-box, gpu.lock. All Mac experiment/scoring/check jobs and prior review children are terminal. Existing caffeinate PIDs 36781 and 65618 remain running; do not stop unrelated processes.

## Changes, review, and Git

Committed closure paths: README.md, STATE.md, DECISIONS.md, research/experiments.md, research/lessons.md, research/archive/experiment-heads-20261010.json, and reviews/20261010-opus55-session-closure-review.md. This status rewrite records the actual main checkout and passing checks. Claude job review-mv2u98bh-dldcy5 and forwarding child opus_closure are terminal, native zero. Native Claude session 4a302712-4fab-4552-ab13-61c7675b34ab completes. Preserve the verbatim closure report under reviews/. User authorization and standing project approval permit committing these records, fast-forwarding main, and pushing. Preserve archive tags before retiring the completed spike branch. Stop after closure; implement no next-session work.

Exact next command: commit this status-only receipt through the hook. Then git push --atomic origin main refs/tags/archive/2026-10-10/llm-experiments. Verify both remote targets before deleting the remote and local spike/llm-experiments branch. Record final terminal receipts and set the next-session command to cat research/answer-evidence.md.

## Next session: intent parsing and tool execution optimization

Start with cat research/answer-evidence.md and reconcile main, deployed release, and jobs. Keep accepted Qwen fixed across parser arms. Compare explicit rules with independent scores from existing BGE embeddings before considering a trained classifier. Freeze development questions, source IDs, seeds, and judgments before candidate answers.

Measure source labels, entity/owner binding, action arguments/execution, answers, and independently transcribed speech separately. Location capture, owner-aware keys and speaker binding, combined answers, and isolated knowledge/log paths need design review. Qualify those features separately and keep them identical across parser arms. Identity, consent, deletion, and other mutations remain code-owned. Same-owner grouping and crop-background isolation stay parked under D148.

Final live targets remain unmet or unqualified: physical audible 1.2 s p50/2.0 s p95, held-out 90% per capability, zero stranger identity claims, 30 tok/s decode, sustained 15 fps detection, Edge 10 ms p99, and complete live-stack reserve without turn paging. The sampled model-stack reserve passes; zero-turn paging and aggregate synthesis detection have measured misses. M4 also needs offline cold start, restart/deletion, and eight active hours.
