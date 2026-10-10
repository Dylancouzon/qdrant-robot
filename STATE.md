# State

Updated 2026-10-10. Canonical checkout: /Users/dylanc/Documents/GitHub/qdrant-robot, branch spike/llm-experiments, based on main 5041aa9. This session covers only Gemma fit/quality experiments. Intent parsing and tool execution optimization are the next session's task. The owned live preview remains paused.

## Read first

Read research/gemma-fit.md, research/lessons.md, research/experiments.md, and the Gemma fit design/result entries in DECISIONS.md. Main consolidation preserves accepted runtime 011f522 and rejected experiment histories. Eight archive tags and the complete recovery bundle remain verified. Private history is build/reconciliation-20261010; native TensorRT evidence remains build/p2/logs/native-20261010.

## Gemma experiment checkpoint

Dylan authorizes Gemma with CPU Kokoro, accepts about 24 tok/s if quality improves substantially, and asks to use WSL whenever compatible. The invented Qwen TensorRT comparison remains withdrawn. The original handoff is research/answer-evidence.md. Scope does not include parser/tool implementation.

Pinned LiteRT 0.18.0 full multimodal Gemma runs on Jetson NVIDIA Tegra Orin Vulkan. Exact aarch64/x86 wheels and 2,588,147,712-byte model verify against frozen hashes. Model revision b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1; SHA256 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c. Official model card's 24.2 tok/s and 2,739 MB process-memory figures remain external evidence, separate from our runs.

Design review reviews/20261010-133237-60293-design.md returns GO WITH CHANGES/native 3. The brief resolves default variant, three net wins, product limits, safety fixtures, CPU provider/native cancellation, integration thresholds, and isolated staging before execution. Freeze default 12 of 36 development packets, original system/history/text evidence, context 2,048, max output 128, no thinking, temperature zero. These packets contain no stranger/ownership coverage.

Jetson GPU Gemma scores nine/12 (J); fresh WSL Qwen scores seven/12 (E); WSL CPU Gemma scores six/12 (E). All have native zero, 12 answers, completion footers, and exact-answer three-vote gpt-6-sol judgments. tools/results.py verifies complete counts and judgments. Jetson has two net wins and zero losses, below the frozen three-win threshold. Stop adoption before 64-token confirmation, CPU Kokoro adaptation, and integrated replay. No unchanged prompt retry, lower threshold, or third GGUF route. Native TensorRT arena remains larger than physical RAM.

Jetson 12 short replies decode at 29.69 tok/s median, with 0.453 s first-token median (J). Standalone minimum MemAvailable is 4,444 MiB in smoke and 4,581 MiB in packets. Every other robot model was stopped. Both runs record two system swap-out pages, including generation overlap; process attribution is unavailable. Full-stack fit, CPU speech, detection while talking, sustained conversation, zero-turn paging, and product/held-out quality remain unqualified.

Evidence: bench/results/2026-10-10-gemma-litert-screen.json publishes numerical outcomes, native commands/exits, hashes, memory, and paired judgments. Private source-packets.json restores the original from 5220bbb and verifies frozen source SHA256 d6267e6b03d07f517644b8f673d0e981fec353b81c2494966010bb27c8c0b4a3. Private build/gemma-fit-20261010 holds frozen packets/rubrics, upstream SDK copies, scripts, full model, and {wsl,jetson}-evidence raw replies, judgments, native receipts, logs, and telemetry. Original cache-directory failure native one and WSL software-Vulkan signal 11 remain preserved. No production data appears in the public audit.

Changed paths: STATE.md, DECISIONS.md, research/gemma-fit.md, research/lessons.md, bench/judge-cache.jsonl, the sanitized audit, and design/task review records. No tracked runtime, fixture, configuration, production model, release link, or memory change. Required checks pass native zero in 92.39 s (E). Task review passes native zero in 220.67 s (E), with no blockers: reviews/20261010-134937-83780-review.md. Commit/push are next.

## Jobs and recovery

All owned remote jobs are terminal. Jetson root /home/qdrant/qdrant-robot/shared/experiments/gemma-fit-20261010: qr-gemma-fit-sdk-20261010 native zero, qr-gemma-fit-model-20261010 native zero, qr-gemma-fit-smoke-gpu-20261010 native zero in 21.43 s, and qr-gemma-fit-packets-gpu-20261010 native zero in 19.40 s. Each stage's native-exit.json, native.log, memory.jsonl, and tegrastats.log preserve the exact command, PID, boot, and outcome. RemainAfterExit units show active/exited with MainPID zero.

WSL root /home/dylan/qdrant-robot-box/experiments/gemma-fit-20261010: qr-gemma-fit-prepare-20261010 native zero; qr-gemma-fit-smoke-gpu-20261010 native one; qr-gemma-fit-smoke-gpu-retry-20261010 native signal 11; qr-gemma-fit-smoke-cpu-20261010 native zero; qr-gemma-fit-packets-cpu-20261010 native zero in 33.69 s; qr-gemma-fit-qwen-control-20261010 native zero in 8.84 s. Logs/receipts use the matching stage directory. WSL selected llvmpipe software Vulkan; CUDA visibility did not qualify WebGPU acceleration. CPU supplied the compatible screen.

Mac relay session 65404 and judge sessions are complete. Local task review PID 83780/session 82898 is terminal, native zero/PASS in 220.67 s; log reviews/20261010-134937-83780-review.md.log. Required checks complete native zero in 92.39 s, log build/gemma-fit-20261010/checks.log. Fresh remote unit snapshots confirm every owned MainPID is zero, with original failed states preserved. Experiment disk usage is 3.5 GB Jetson and 4.5 GB WSL. Mac preview port 8765 remains closed. Existing caffeinate -dimsu PID 65618 stays running. Authentication and hooks were verified; tools/githooks remains enabled. Estimated additional storage stays below 8 GB per remote machine plus bounded logs. Preserve all evidence and model pins; there is no stalled process to recover.

## Product and rollback

Jetson boot 09b4bb27-f975-441c-9d00-7af446ec7de6; current releases/7f67670fa91e; previous releases/6781adbb7189. Production memories, accepted Qwen/CUDA-Kokoro runtime, shared models, and closed backup remain unchanged. Do not relaunch the preview for this experiment. WSL access is ssh dylan@192.168.1.74, project /home/dylan/qdrant-robot-box, lock gpu.lock. Jetson access is ssh robot, lock /home/qdrant/qdrant-robot/shared/gpu.lock. No other owner's services were changed.

Git: standing project approval permits scoped commit/push after task review and required checks. Commit this rejected-adoption experiment checkpoint to spike/llm-experiments, then push that branch. Keep main and product deployment unchanged. User limits this session to this checkpoint; do not continue into intent work.

## Next session: intent parsing and tool execution optimization

research/answer-evidence.md preserves the reviewed seven-session/30-turn plan and selected Location/Owner requirements. Compare explicit rules and existing BGE source scores first, preserving code-owned identity, consent, and mutations. Freeze accepted Qwen across parser arms. Measure source labels, entity/owner binding, action arguments/execution, and answer quality separately. Location capture, owner-aware keys/speaker binding, combined answers, and isolated knowledge/log paths need design review before building. Same-owner grouping and background isolation remain parked under D148.

Final targets remain unmet: physical audible 1.2 s p50/2.0 s p95, 90% per capability, zero stranger identity claims, 30 tok/s decode, sustained 15 fps detection, Edge 10 ms p99, 500 MB full-stack reserve, and no turn paging. M4 also needs held-out acceptance, offline cold start, restart/deletion, and eight active hours. Standalone Gemma results establish none of these acceptance claims.

Exact next command: git add the eight reviewed record/cache/audit files; git commit through tools/githooks; git push -u origin spike/llm-experiments. Record the successful Git checkpoint, then stop this session.
