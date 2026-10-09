# TensorRT Edge-LLM preparation and implementation checkpoint

The native Brain adapter and scheduling/privacy changes pass the full local checks. Official Orin runtime loading and native request serialization passed separately. Model preparation remains pending. There is no completed INT4 checkpoint, engine, model answer, cancellation-during-inference result, or memory-fit claim.

The current WSL unit is `p2-trt-quantize-native-retry.service`, invocation `b9ec1e261ba04407938c9be35eec3f1d`, flock PID 128539, and Python PID 128544. It started at 16:46:49 EDT. It uses the verified official CUDA extension, the original model/calibration settings, and fresh output `checkpoints/int4-awq-native-retry`. No CPU quantizer is running. D118's counseled CPU route remains a fallback; D119 selects this corrected GPU retry after new progress disproved the unchanged-progress premise.

- Source: NVIDIA/TensorRT-Edge-LLM v0.11.0, commit `95515c2f87fba8982db5a519f9022277667b3cc9`, Apache-2.0.
- Base: google/gemma-4-E2B-it revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`, 10,246,621,918-byte model.safetensors, SHA256 `2db5482b20d746879bb3ef79b5203e9075a2e2b98f54ec7c2f281c1477ddc550`.
- Assistant: google/gemma-4-E2B-it-assistant revision `2d874ef7d29f9a30599a1e4b3c1cbc9595f005df`, 157,565,344-byte model.safetensors, SHA256 `93682eb1c97639d18f007704dc880bd74cbe530adaf7b1bb561213863fdad2a6`.
- WSL directory: `/home/dylan/qdrant-robot-box/experiments/p2-trt-edge`.
- Setup unit `p2-trt-setup.service` completed native zero. Official `[tools]` dependencies include torch 2.13.0+cu130, transformers 5.14.1, and ModelOpt 0.45.0. `import torch` reported CUDA available. Environment pins live in `environment.txt`.
- Download unit `p2-trt-download.service` completed native zero. Artifacts live in `checkpoints/base` and `checkpoints/assistant`. Logs: `setup.log`, `download.log`, `checkpoint-sha256.txt`.
- Original quantization unit `p2-trt-quantize.service`, invocation `18d4965055764fb3ab0736a737db9df9`, flock PID 59725, Python PID 59730, start 2026-10-09 13:37:49 EDT.
- Command: `/usr/bin/flock /home/dylan/qdrant-robot-box/gpu.lock /home/dylan/qdrant-robot-box/experiments/p2-trt-edge/venv/bin/tensorrt-edgellm-quantize llm --model_dir checkpoints/base --mtp_draft_dir checkpoints/assistant --output_dir checkpoints/int4-awq --quantization int4_awq --device cuda`.
- Unit uses MemoryMax 22G, journal rate limit 200 messages per 30 seconds, HF_HOME inside the owned experiment, and PYTHONUNBUFFERED=1. No execution deadline.
- Last observed unit memory: 1,079,480,320 bytes. GPU 353 MiB and zero utilization. ModelOpt warned that official pinned transformers 5.14.1 is untested. No OOM appeared before connection loss.
- Heartbeat SSH exited 255: `Timeout, server 192.168.1.74 not responding.` Recovery at 13:49 EDT confirmed unchanged boot ID `5f4af7d6-879e-48eb-979a-45e715f1d626`, unchanged unit/PIDs, and continued native execution.
- At 13:47:26, the official quantizer inserted 1,840 quantizers. At 13:47:28, `awq_lite: Caching activation statistics...` began. Image calibration selected official MMMU automatically.
- The CLI default is 512 samples, but the official image calibration path used 128 images. The first activation-cache pass completed 128/128 in 13 minutes at 14:00:29, then `awq_lite: Searching parameters...` began its second 128-image pass. No completed 512-sample calibration is claimed.
- ModelOpt could not find the installed `venv/bin/ninja` because the unit PATH lacked that directory. It selected its documented CPU fallback for optional `modelopt_cuda_ext`. The native run continues unchanged. Future export units include the venv and CUDA binaries in PATH.
- Gemma base has no `mtp_num_hidden_layers`, so the generic quantizer's accepted `--mtp_draft_dir` does not merge this assistant. Official export has a dedicated Gemma pair path through `--mtp --mtp-draft-dir checkpoints/assistant`; it validates the paired tokenizer, vocabulary, and KV sharing. That export remains unexecuted.
- Recovery GPU measurement: 10,016 MiB, 100% utilization. Unit memory: 8,177,119,232 bytes; unit swap: 266,240 bytes. Python worker CPU 643%, RSS 6,699,960 KiB. Native exit remains pending; no output checkpoint exists yet.
- Kernel logs contain journald cache flushes under memory pressure and `dxgkio_make_resident: Ioctl failed: -12`. No native CUDA OOM or killed process was observed. Evidence lives in `kernel.log`, `quantize.log`, and `quantize-unit.txt`.

Official support source lists CPU export and Ampere compute capability 8.0 or newer for quantization. `packaging/variants.toml` lines 157–169 match Orin L4T R39.2, CUDA 13.2, SM87, and TensorRT SONAME 10. Jetson TensorRT 10.16.2 satisfies that source ABI row; runtime loading and engine acceptance remain unexecuted. The WSL Ubuntu 26.04 stack has no exact published inference wheel row. No platform checks changed, and no Jetson operations occurred.

Initial uv acquisition used its normal download cache; installed dependencies and sources remain isolated. Future acquisition uses an experiment-owned UV_CACHE_DIR. A premature quantizer help call during active installation saw partial torch and failed ImportError. The completed setup subsequently passed torch import; the real unit uses the completed environment.

At the initial preparation checkpoint, no repository product files changed. The implementation checkpoint below now contains a native adapter. Model inference and target-native engine acceptance remain pending.

## Native search diagnosis at 16:19 EDT

The same quantizer remains active. Python CPU time increased from 03:44:08 to 03:45:50 during this inspection. GPU utilization stayed at 99%, with 9,998 MiB allocated. Unit memory stayed near 8.24 GB, and unit swap stayed at 266,240 bytes. No checkpoint or native error appeared. The search pass still reports zero completed images. These counters prove active execution, but they do not prove completed parameter-search work.

Official ModelOpt `model_calib.py:1075-1274` searches 11 alpha candidates from zero through one at 0.1 intervals. Each eligible linear computes the original output, then repeats its full input forward for every candidate. Each candidate computes a full squared-error tensor. Gemma E2B has 35 text layers; the earlier inserted-quantizer count of 1,840 also includes other quantizers and does not establish 1,840 searched linears. `_calibrate_multimodal` calls `model(**kwargs)` once per image with `use_cache=False`. It does not generate autoregressive tokens. Its tqdm advances only after a complete model forward. AWQ module search counters advance only after all candidates for that module. Those live Python counters cannot be read through the current native logs.

The optional-extension warning calls its fallback CPU, but `tensor_quant.py:604-642` keeps tensor device placement. It executes PyTorch float conversions, round, clamp, and scale operations without a CPU transfer. Thus the warning does not establish CPU-only quantization. The fallback adds FP32 temporary tensors and GPU synchronization near the 10 GB device limit. Resource counters and source make a slow native search plausible; they cannot locate the current layer or distinguish residency overhead from another hot path. Kernel ptrace_scope is one. Reading `/proc/59730/syscall` was denied. No py-spy or gdb exists. No privilege or live environment change was attempted.

The native job remains preserved. A usable export remains pending its checkpoint.

## Target runtime preparation for the lead

PyPI metadata returned the official CPython 3.12 AArch64 wheel:

- Filename: `tensorrt_edgellm-0.11.0-cp312-cp312-manylinux_2_39_aarch64.whl`.
- Size: 447,070,745 bytes.
- SHA256: `9e6722a5a250d0ba18665911a908aecfc9684722b9d56d944efe31fe6c889d9b`.
- URL: https://files.pythonhosted.org/packages/c2/07/32efeb227b4b4c952b051ab9b990b21146756296b5ee65450de827cc5072/tensorrt_edgellm-0.11.0-cp312-cp312-manylinux_2_39_aarch64.whl

Official installation uses an isolated `python3 -m venv --system-site-packages` and `pip install "tensorrt-edgellm[server]==0.11.0"`. Outside its source checkout, `import tensorrt; from tensorrt_edgellm import runtime; runtime.load()` validates native payload selection. Lead owns that target check.

The wheel's checkpoint-direct builder supports `--spec-type gemma4_mtp`, `--draft-model-dir`, and `--components llm,visual`. The shared dense operations support both INT4 AWQ checkpoint formats. Gemma-specific configuration validates paired tokenizer IDs, vocabulary, hidden dimensions, and KV sharing. The official source therefore supports one wheel-native build route for the requested pair. Its runtime does not consume the maintained C++ ONNX engines. Avoid compiling that second runtime route unless the first fails concretely.

Proposed target command after the checkpoint exists, not yet executed:

```sh
tensorrt-edgellm-build --model-dir checkpoints/int4-awq --engine-dir engines --components llm,visual --spec-type gemma4_mtp --draft-model-dir checkpoints/assistant --max-batch-size 1 --max-input-len 2048 --max-kv-cache-capacity 4096 --max-verify-tree-size 4 --max-draft-tree-size 4
```

Portable ONNX export supports `--components thinker,visual,mtp_draft --mtp --mtp-draft-dir checkpoints/assistant --externalize-weights int4_ffn`. The assistant remains a separate FP16 checkpoint. Export units must include the owned venv and CUDA binaries in PATH. Neither export nor engine build has run.

## Raw FP16 checkpoint cannot bypass INT4 calibration through weight placement

`experimental/builder/ops/functional/core.py:352-374` chooses INT4 only from existing packed checkpoint tensors. It recognizes `.qweight` or U8 `.weight` with `.weight_scale`; otherwise it chooses FP16. `ops/backend.py:941-970` routes FP16 weights to a FP16 linear, and prequantized INT4 weights to `int4_linear`. `core/weight_policy.py` only controls engine input and runtime weight placement. The CLI's dense choices are `auto`, `nvfp4-qdq`, and `fp16`; it offers no raw-FP16-to-INT4 mode. Therefore `--externalize-weights int4_ffn` cannot create an INT4 engine from the original Gemma checkpoint. The usable AWQ checkpoint remains required. No second WSL model job started.

Lead reports the official Jetson wheel setup passed native zero at 16:19:48. It loaded `_native/payloads/jetson-orin-jp72-cu13-sm87` with TensorRT 10.16.2.10. That target-native runtime check establishes loading, while model engine build and memory fit remain pending. The selected first engine limits are batch one, input 2,048, KV capacity 4,096, and draft/verify four. Those limits describe a proposed build, not measured capability.

## Read-only native stack evidence

Lead qualified WSL root access through `wsl.exe --distribution Ubuntu --user root`. A separate `diagnostics-venv` installed py-spy 0.4.1. Three bounded, function-only `py-spy dump --pid 59730` calls completed native zero. No locals, tensor contents, signals, or global ptrace setting changes were used. Receipts live in WSL `diagnostics-stack-1625.txt`, `diagnostics-stack-1626.txt`, and `diagnostics-stack-1629.txt`.

The main thread executes ModelOpt `_tensor_quant` at lines 616 and 635, reached through the AWQ candidate forward at `model_calib.py:1234`. The enclosing model is Gemma text MLP at `modeling_gemma4.py:1089`, then text decoder layer at line 1433. These different instruction locations prove execution inside the eager quantization hot path. They do not reveal a layer index or a completed search module. The image progress remains zero.

At 16:29, GPU clocks were 1,950 MHz, memory clocks 9,251 MHz, power 136 W, GPU utilization 99%, memory utilization zero, and allocation 9,999 MiB. Kernel logs after 14:00 contain no new allocation or residency errors. Available counters do not prove paging or eviction.

Gemma double-wide MLP weights can be 1,536 by 12,288. Each full FP32 copy is 72 MiB. Eager quantization can hold the FP32 input, multiplied input, and clamp output together, totaling 216 MiB, before other scales, FP16 pre-scaled weights, and activations. Current device allocation leaves about 241 MiB. This establishes a concrete transient-memory concern. The native extension kernel uses an FP16 `empty_like` output and float register arithmetic, avoiding those full FP32 intermediate tensors and host checks of GPU scalar values. Its output for this shape is 36 MiB. Correcting the future unit PATH can therefore change both synchronization and memory cost without a platform patch. A retry requires the lead's resource judgment; this worker preserved the active run.

## Product API mapping and continuation blocker

The official high-level `experimental.server.LLM` supports OpenAI-style text/image messages through `chat` and `generate_stream`. `StreamDelta.text` and `token_ids` provide text and exact generated token IDs. Its cancellable iterator closes its native stream channel and joins the generation worker; `LLM.close` drains work and releases device memory. This maps to Brain answer streaming, captioning, cancellation before TTS, and shutdown. Native `LLMRuntime.count_prompt_tokens` with chat templating disabled can count raw prior text. The HTTP server exposes templated Anthropic input counts, but no raw tokenization endpoint.

Prefix reuse supports text-only Gemma MTP. Official `kv-cache-reuse.md` says speculative image requests bypass reuse and run cold. Thus Brain's image prefill cannot promise the existing image-prefix acceleration with the paired assistant.

The speech pause/resume contract currently has a main-flow mismatch. Brain appends an unfinished assistant message and resumes the same answer. The pinned native renderer sets `continue_final_message` to false at `cpp/chatTemplate/chatTemplate.cpp:722`. The pinned Gemma template appends `<turn|>` after a final assistant message, and `add_generation_prompt` adds a new model turn. Neither the documented high-level stream API nor HTTP protocol exposes final-message continuation. Passing the prior through those APIs therefore represents a closed answer followed by a new turn. The lead resolved this mismatch by selecting uninterrupted native generation during CUDA Kokoro synthesis. The implementation removes pause/resume and image-prefill calls. It uses no prompt truncation shim or upstream patch.

## Corrected GPU retry and implementation checkpoint

The first resource-based retry, invocation `ad37d6efebc341c6a76330472b32dadd`, completed activation calibration at 128/128 in 11:04. It began parameter search at 16:44:54, and loaded the precompiled CUDA extension in 1.4 seconds at 16:45:00. The worker mistakenly combined reconciliation and interruption in one command, and stopped this run before assessing that new progress. Its stop receipt records SIGTERM 15. This is an operator sequencing error and an interrupted run, not a failed native AWQ search. No output checkpoint existed. The fresh D119 retry preserves those receipts and uses a distinct output directory. Future assessments and mutations use separate tool calls.

Original full receipts are in Mac `build/p2/logs/trt-interrupted-original`. Verified extension receipts are in `build/p2/logs/trt-cuda-extension`. Retry resource receipts are in `build/p2/logs/trt-native-retry`. The prematurely stopped retry's final receipts remain in WSL `interrupted-native`. Current unit metadata is WSL `quantize-native-retry-unit.txt`, with journal copies going to `quantize-native-retry.log`. All these paths remain ignored.

The stable product diff changes `robot/brain.py`, `robot/main.py`, `robot/test_brain_trt.py`, `robot/test_speak.py`, and `robot/test_people.py`. The lead owns the core runtime pin in `pyproject.toml` and `uv.lock`. No commits or shared configuration changes were made by this worker.

Brain loads the official low-level `LLMRuntime` from the immutable release's core package. It expects `shared/experiments/p2-trt-edge/engines/llm`, `engines/visual`, `checkpoints/int4-awq`, and `checkpoints/assistant`. The lead will copy the verified preparation result to that canonical checkpoint path. Constructor validation reads base, draft, and visual configuration before native GPU loading. It requires the selected batch/input/KV/verify/draft limits and a single-image profile with 512 total and per-image soft tokens. Those limits are engineering settings, not measured capability.

Context uses native templated text counting with the image placeholder kept at its original position. Native counting rejects decoded media buffers. The adapter reads the built visual per-image limit and adds the full limit plus two delimiters for each image. It reserves the requested output count, drops only complete old exchanges, and fails if current evidence cannot fit. Pinned `Gemma4ViTRunner.cpp:118,383,411,485-486` establishes the image limit and expansion. The pinned HF processor defaults to 280 tokens, while this native path uses the built engine profile. Actual expanded prompt counts remain to be checked during target inference.

The worker reserves serial generation until the native thread retires. Stream closure cancels its channel and joins it before returning. Shutdown also cancels and joins a producer whose consumer is paused. A clean terminal chunk stays uncancelled. Caption interruption closes its stream. The Robot keeps one generation active through speech synthesis, and cancels it if synthesis fails. Identity deletion clears conversation and cached-look history before retrieval can build the current prompt; the privacy regression covers the current and following turn.

Scoped checks passed with nine tests and one asset-dependent skip. The skipped check requires LFW and face models; the Robot/Edge privacy regression passed. Full `tools/gate.py checks` passed native zero in 15.88 seconds, including lint, complexity, dead-code checks, all tests, module assertions, and workflow self-tests. Log: `build/p2/logs/trt-full-checks.log`. The ignored worktree `.venv` link reads the coordinator's Python 3.12 environment; pytest and Ruff used temporary uv overlays. No shared environment installation occurred.

The lead separately verified installed Orin native API shapes and serialized a valid JPEG/text request with ordered source evidence. Those probes loaded no engine. The adapter remains an implementation checkpoint pending engine build, actual answers, generation cancellation, image count validation, and integrated resource measurements.

Official source permits `--device cpu`: the generic loader moves the model to the requested device, fake quantization has a CPU tensor path, and INT4 packing has a native PyTorch CPU path. No CPU model operation was executed. CPU feasibility and resource fit therefore remain unqualified until the counseled fallback is selected and run.

## Review fixes and transfer reconciliation at 16:54 EDT

The task review found that scene changes removed assistant messages, leaving history that context could not evict as complete exchanges. `_look` now preserves complete exchanges, while current-image authority and the scene-change marker remain. The existing native budget regression forces a scene change and verifies oldest-pair eviction.

Lead authorized the necessary existing continuous-workload adaptation in `eval/continuous.py` and `eval/test_continuous.py`. The workload no longer polls a llama child process. Detector failure, required Robot thread health, and pending-work stall supervision remain. The fake Robot contains no child process. Focused native and continuous checks passed 28 tests in 1.92 seconds. Final stable full checks passed native zero in 15.30 seconds, with receipts at `build/p2/logs/trt-full-checks-stable.log`.

The assistant transfer preparation command lost SSH before its completion receipt. A subsequent read-only reconciliation also timed out. Transfer archive completeness and calibration progress are unknown at this checkpoint. The corrected GPU unit remains preserved; no CPU job, restart, or model mutation occurred. Bundle preparation will resume only after checking existing remote files. The bundle excludes checkpoint cache directories and base model weights, includes paired assistant weights and both models' tokenizer/config/license metadata, and records exact revisions, file sizes, and SHA256 values.

## Verified paired assistant transfer bundle

Mac `build/p2/inputs/trt-transfer/assistant-metadata.tar` is 222,033,920 bytes, SHA256 `9da354befc24230d158db2d2687e376265a42687d091c1dc7754605a3a64bd35`. Its adjacent JSON manifest records 15 file sizes, SHA256 values, and pinned model revisions. Local verification checked archive SHA, every member size, and every member SHA. The bundle includes assistant FP16 weights plus both checkpoints' configs, tokenizers, model cards, and base chat template/processor configuration. It excludes base weights and all cache directories. Both pinned README front matter declares `apache-2.0` and links `https://ai.google.dev/gemma/docs/gemma_4_license`; those model cards provide the license receipt.

Five final interrupted-native receipts now exist locally at `build/p2/logs/trt-interrupted-native`. The live b9ec retry remains active with 8,481,689,600 bytes unit memory and zero unit swap at this read. Its journal confirms complete tensor loading and activation-cache start. No completed activation/search count or output checkpoint is yet reported. No inference or export claim is made.

## Pause and handoff receipt

Final read-only WSL receipt is `build/p2/logs/trt-handoff/status.txt`, with complete journal/kernel copies and SHA manifest beside it. WSL timestamp is 2026-10-09 16:56:16 EDT; boot remains `5f4af7d6-879e-48eb-979a-45e715f1d626`. Unit `p2-trt-quantize-native-retry.service` remains active/running, invocation `b9ec1e261ba04407938c9be35eec3f1d`, flock PID 128539, Python PID 128544. Unit memory is 8,481,345,536 bytes, unit swap zero. Host swap is 6.2 GiB of 7.0 GiB, which does not attribute paging to this unit. GPU allocation is 10,004/10,240 MiB, utilization 100%, memory utilization zero, power 139.58 W. Those counters do not prove completed calibration progress.

The latest explicit progress remains 1,951/1,951 tensors loaded, 1,840 quantizers inserted, and activation-cache start at 16:53:40. No completed activation/search sample count is logged, and the output directory remains absent. The job is left running without a deadline. No CPU preparation, extra GPU job, engine build, model inference, or restart occurred. Product files are frozen for the lead's second review. Final full checks passed native zero in 15.30 seconds.

Resume with the following read-only reconciliation before any mutation:

```sh
ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 dylan@192.168.1.74 'cd /home/dylan/qdrant-robot-box/experiments/p2-trt-edge && date && cat /proc/sys/kernel/random/boot_id && systemctl --user show p2-trt-quantize-native-retry.service -p ActiveState -p InvocationID -p MainPID -p MemoryCurrent -p MemorySwapCurrent -p ExecMainStatus && journalctl --user -u p2-trt-quantize-native-retry.service --all -n 12 --no-pager && find checkpoints/int4-awq-native-retry -maxdepth 2 -type f -printf "%p %s\n"'
```

Keep reconciliation and mutation in separate calls. A missing output directory before export is an observation, not a failed preparation claim. Verify native exit, complete model/config artifacts, quantization metadata, per-file SHA values, finite calibration, and unchanged coverage before transfer. Lead owns the Jetson build and canonical `checkpoints/int4-awq` staging. Native answers, image counts, cancellation during generation, integrated fit/audio, quality, and latency remain unproved.

Official source pin remains `95515c2f87fba8982db5a519f9022277667b3cc9`. The bundle manifest carries base revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`, assistant revision `2d874ef7d29f9a30599a1e4b3c1cbc9595f005df`, Apache 2.0 model-card license proof, and all 15 file hashes. Bundle and interrupted receipts are copied and verified locally. Monitoring now stops for the requested pause.
