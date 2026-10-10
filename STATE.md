# State

Updated 2026-10-10. Native Gemma AWQ engines build successfully on the Jetson. Runtime initialization fails with CUDA out of memory before any answer. Preserve this exact blocker and the failed extraction attempt. No further prompt tuning, quantization, export, deployment, adoption, or main merge occurs.

## Active task and acceptance

Lead worktree: `/Users/dylanc/orca/workspaces/qdrant-robot/jetson-trt-testing`, branch `spike/jetson-trt-testing`, source base `f86d463` with reviewed adapter `0e5a484`. Native testing follows coordinator D117, D115-D119/D133, and `research/p2-briefs/trt-edge.md` at `/Users/dylanc/Documents/GitHub/qdrant-robot`. The coordinator's root F1 source remains rejected.

Acceptance: reuse and verify the completed WSL archive; build official checkpoint-backed native engines; run text/image checks and unchanged frozen packets; record exact exits, quality, cold/warm latency, decode, memory, paging, and tegrastats. Transfer/verification/build pass. Initialization fails native exit 1; all answer checks and successful inference metrics are blocked. This is a testing checkpoint, not successful qualification.

Changed paths: STATE.md, DECISIONS.md, research/lessons.md, research/jetson-trt.md, and sanitized native receipts in bench/results. Scripts, inputs, native logs, telemetry, configs, and failed artifacts remain ignored under build/p2/logs/native-20261010. No product code changes.

## Preserved product and Git

Protected UI worktree: `/Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface`, branch `spike/mac-audio-interface`, clean at `011f522`. Its STATE owns D147 acceptance and D148 proposals. Deployed release `7f67670fa91e`, previous `6781adbb7189`, production memories, backups, and preview remain preserved. Main and other worktrees remain unchanged.

Standing project approval permits scoped commit/push after records checks and task review. Configured hooks remain `tools/githooks`. Records-only commit does not require product/full-suite tests. Records checks and Sol 6.1 task review PASS (159.79 s/native 0). Review: reviews/20261010-110537-96895-review.md. The gate approves only this testing checkpoint and exact blocker. Authentication is valid; remaining usage is unavailable through auth commands. Existing caffeinate processes belong to other sessions and remain running.

## WSL preparation and frozen comparison

[Checkpoint validation](bench/results/2026-10-10-wsl-checkpoint-validation.json) verifies 2,433 base and 50 assistant tensors with finite float values (E). The original quantizer native exit remains unavailable. Preparation and ONNX export were not repeated.

Archive: `/Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/inputs/trt-transfer/gemma4-e2b-int4-awq-20261010.tar`, 8,437,452,800 bytes, SHA256 `aaf6b5170b427700b048e969d052e0cd8d40a11068e87782e35936c9974c4697`. Transfer exits 0; Jetson archive and all 16 manifest files verify exactly.

[WSL prompt screen](bench/results/2026-10-10-wsl-gemma-prompt-screen.json): three prompts tie at 7/12 on BF16 Transformers (E). Native inputs retain the unchanged default 12 packets, 128 output tokens, 2,048-token context, and clock image. The original cases hash is `2e62ade166a8c52eb37f09281763d1cc022172d251a0917d75a7f4df0062f588`. Native answers: zero; answer quality and paired differences remain U.

## Native results and blocker

See [native receipt](bench/results/2026-10-10-jetson-gemma-awq-native.json), [measurements](bench/results/2026-10-10-jetson-gemma-awq-native.jsonl), [findings](research/jetson-trt.md), and [lessons](research/lessons.md).

Installed official Edge-LLM 0.11.0 wheel selects Orin JP7.2/CUDA13/SM87; TensorRT is 10.16.2.10. D117 profile: batch one, input 2,048, KV 4,096, draft/verify four, image total/per-image 512. Default checkpoint-backed placement remains unchanged. LLM/MTP/visual engines build native exit 0 in 751.99 s (J).

Engine bytes: base 89,958,500; draft 5,644,932; visual 38,628,444. LLM configs/plans live directly under engines/, while the historical product adapter expects engines/llm. Standalone testing uses the real layout. Adapter integration remains unqualified and requires that path correction before adoption.

Native constructor fails during allocation: `RuntimeError: CUDA runtime error in cudaMalloc(&data, memoryCapacity): out of memory`. Native process exits 1 after 1.04 s (J); no smoke or development answer starts. The failed run provides no cold/warm answer latency, decode rate, or integrated memory result.

Config/source arithmetic requires 8,047,141,376 bytes (7,674.35 MiB) for base checkpoint bindings, including 4,697,620,480 bytes of PLE. The board reports 7,485.45 MiB total (J). No base storage aliases exist; scaled embedding and unscaled LM head have different recipes. These requirements explain the allocation failure; the allocator did not log its requested byte count. Unchanged retries or smaller KV cannot recover this weight-only deficit.

Build telemetry: minimum available 2,740.83 MiB; child VmHWM 4,570.43 MiB; sampled child VmSwap zero, but system paging 349 in/333 out pages and unit swap peak 1,212,416 bytes (J). These build measurements prove neither inference fit nor absent paging. Failed initialization has five samples and 5 in/0 out pages; attribution remains unknown. Kernel probe reports no entries in the captured failure window.

## Jobs and recovery

Robot alias `robot`; boot `09b4bb27-f975-441c-9d00-7af446ec7de6`. Isolated directory: `/home/qdrant/qdrant-robot/shared/experiments/p2-trt-edge/native-20261010`. All children are terminal; GPU lock is free. Retained named user units have no restart and keep exact outcomes:

- `qr-trt-native-verify-20261010`: invocation `786b305cd5c04a6ead24c48aa67be294`, PID 436596 reaped, native 1. Log-size RLIMIT also limited extraction to 64 MiB. Its partial inputs remain inputs-verify-failed/.
- `qr-trt-native-verify-retry-20261010`: invocation `a773ef3518f14217a689d4e0992af016`, PID 436920 reaped, native 0. Bounded pipe capture replaces the process-wide file limit; archive/member verification passes.
- `qr-trt-native-build-20261010`: invocation `5cff9cee0dae41f487c23e61d5095fbb`, PID 437120 reaped, native 0. Official `tensorrt-edgellm-build --components llm,visual --spec-type gemma4_mtp` with D117 settings and original paired checkpoints.
- `qr-trt-native-infer-20261010`: invocation `a3b89398c80e4adc93b971282505f3d8`, PID 441139 reaped, native 1. Command: isolated `venv/bin/python native-20261010/infer.py`; native constructor fails before generation.

Each stage preserves manifest, native.log, native-exit.json, memory.jsonl, and tegrastats.log. Collected files are under ignored build/p2/logs/native-20261010/collected. The original archive, all successful engines, failed inputs, and private source receipts remain preserved. Initial budget was 32 GB within 101 GiB free; no shared cache or model cleanup occurred.

Gate PID 96895 and its Codex children have exited; no owned jobs run. The reviewed native checkpoint is retained on this testing branch under standing commit/push approval. Exact next command: `git status --short --branch`; then inspect this branch before any new work. Native stage receipts use their own JSON/JSONL schema and need direct checks; tools/results.py handles the existing replay/bakeoff history. The next model/runtime intervention needs a changed weight-placement hypothesis; current native quality, sustained conversation, cancellation, integrated fit, and every final acceptance target remain open.
