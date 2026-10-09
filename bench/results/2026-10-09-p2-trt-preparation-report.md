# TensorRT Edge-LLM preparation checkpoint

The official Gemma E2B and paired MTP checkpoints downloaded and passed SHA256 reads. Official INT4 AWQ preparation started on WSL. SSH recovered after an infrastructure interruption. The native quantizer remains active.

- Source: NVIDIA/TensorRT-Edge-LLM v0.11.0, commit `95515c2f87fba8982db5a519f9022277667b3cc9`, Apache-2.0.
- Base: google/gemma-4-E2B-it revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`, 10,246,621,918-byte model.safetensors, SHA256 `2db5482b20d746879bb3ef79b5203e9075a2e2b98f54ec7c2f281c1477ddc550`.
- Assistant: google/gemma-4-E2B-it-assistant revision `2d874ef7d29f9a30599a1e4b3c1cbc9595f005df`, 157,565,344-byte model.safetensors, SHA256 `93682eb1c97639d18f007704dc880bd74cbe530adaf7b1bb561213863fdad2a6`.
- WSL directory: `/home/dylan/qdrant-robot-box/experiments/p2-trt-edge`.
- Setup unit `p2-trt-setup.service` completed native zero. Official `[tools]` dependencies include torch 2.13.0+cu130, transformers 5.14.1, and ModelOpt 0.45.0. `import torch` reported CUDA available. Environment pins live in `environment.txt`.
- Download unit `p2-trt-download.service` completed native zero. Artifacts live in `checkpoints/base` and `checkpoints/assistant`. Logs: `setup.log`, `download.log`, `checkpoint-sha256.txt`.
- Quantization unit `p2-trt-quantize.service`, invocation `18d4965055764fb3ab0736a737db9df9`, flock PID 59725, Python PID 59730, start 2026-10-09 13:37:49 EDT.
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

No repository product files changed. The adapter remains blocked on usable model export and target-native inference. Continue the healthy native quantizer and monitor memory. Inspect official CPU/offload support before another attempt if CUDA preparation fails.

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
tensorrt-edgellm-build --model-dir checkpoints/int4-awq --engine-dir engines --components llm,visual --spec-type gemma4_mtp --draft-model-dir checkpoints/assistant --externalize-weights int4_ffn --max-batch-size 1 --max-input-len 2048 --max-kv-cache-capacity 4096 --max-verify-tree-size 4 --max-draft-tree-size 4
```

Portable ONNX export supports `--components thinker,visual,mtp_draft --mtp --mtp-draft-dir checkpoints/assistant --externalize-weights int4_ffn`. The assistant remains a separate FP16 checkpoint. Export units must include the owned venv and CUDA binaries in PATH. Neither export nor engine build has run.

## Raw FP16 checkpoint cannot bypass INT4 calibration through weight placement

`experimental/builder/ops/functional/core.py:352-374` chooses INT4 only from existing packed checkpoint tensors. It recognizes `.qweight` or U8 `.weight` with `.weight_scale`; otherwise it chooses FP16. `ops/backend.py:941-970` routes FP16 weights to a FP16 linear, and prequantized INT4 weights to `int4_linear`. `core/weight_policy.py` only controls engine input and runtime weight placement. The CLI's dense choices are `auto`, `nvfp4-qdq`, and `fp16`; it offers no raw-FP16-to-INT4 mode. Therefore `--externalize-weights int4_ffn` cannot create an INT4 engine from the original Gemma checkpoint. The usable AWQ checkpoint remains required. No second WSL model job started.

Lead reports the official Jetson wheel setup passed native zero at 16:19:48. It loaded `_native/payloads/jetson-orin-jp72-cu13-sm87` with TensorRT 10.16.2.10. That target-native runtime check establishes loading, while model engine build and memory fit remain pending. The selected first engine limits are batch one, input 2,048, KV capacity 4,096, and draft/verify four. Those limits describe a proposed build, not measured capability.
