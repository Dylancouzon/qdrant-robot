# Jetson software stack: what works on this robot

As of 2026-10-07, measured on our robot (L4T R39.2.0, Ubuntu 24.04, Python 3.12, 15W mode). Labels: J measured here, E elsewhere, U unverified.

## Summary

- CUDA 13.2.2, cuDNN 9.20, and TensorRT 10.16.2 install from NVIDIA's JetPack apt repo (`r39.2`): `cuda-toolkit-13-2 libcudnn9-cuda-13 libcudnn9-dev-cuda-13 tensorrt python3-libnvinfer python3-libnvinfer-dev`. About 27 GB of disk. Driver 595.78. (J)
- PyPI `onnxruntime-gpu` 1.30.0 (aarch64) has no sm_87 kernels: `cudaErrorNoKernelImageForDevice`. (J)
- `onnxruntime-gpu` 1.24.0 from `https://pypi.jetson-ai-lab.io/sbsa/cu130/+simple/` works on the Orin GPU and lists TensorRT, CUDA, and CPU providers. Install with `--index-strategy unsafe-best-match`. (J)
- The Jetson AI Lab index has no `jp7` Orin channel; JetPack 7 Orin uses the `sbsa/cu130` channel. (J)
- The course robot's torch 2.13.0+cu130 has no sm_87 build: it warns and runs without the GPU. (J, from its journal)
- Power: MAXN_SUPER since 2026-10-08 (D31, D32): GPU 1,020 MHz, EMC 3,199 MHz, CPU 1,728 MHz, applied by the on-device UEFI capsule `TEGRA_BL_3767_super.Cap` after setting TNSPEC and COMPATIBLE_SPEC to `jetson-orin-nano-devkit-super-` (the QSPI flash from an x86 host was not needed). Before it, BPMP capped EMC at 2,133 MHz and the GPU at 624.75 MHz. (J)

## Thermals (15W, closed enclosure, stock fan)

- 15 minutes of continuous llama-bench (Qwen3-VL-2B, pp512 plus tg128 in a loop, GPU busy 74% mean): junction temperature peaked at 59.9 °C, prefill and decode stayed within 0.3% from first to last run, VDD_IN 10.9 W mean and 14.3 W peak, no new over-current events (`oc3_event_cnt` stayed at 14,949, counted earlier since boot, probably during the six-core build). Evidence: `bench/results/thermal-15w.tegrastats`. (J)

## Memory budget (bench/memory_budget.py, MemAvailable drop per component, J)

| Component | Before limits | After limits |
| --- | --- | --- |
| bge-small, ORT CUDA (includes the process's CUDA context) | 370 MB | 442 MB |
| Kokoro, ORT CUDA | 608 MB, +576 MB after 39 phrase lengths | 441 MB, +211 MB |
| Parakeet int8 plus Silero, CPU | 1,218 MB | 880 MB |
| llama-server, Qwen3-VL-2B Q4_K_M | 2,511 MB | 2,067 MB |
| Available with everything loaded and exercised | 460 MB | 2,016 MB |

- llama-server keeps a host-RAM prompt cache, 8 GiB by default (`--cache-ram`): long replays pushed the robot 1.4 GB into swap. Now `--cache-ram 0`, `-c 2048`, `-ub 256`.
- ORT's CUDA arena keeps a block per input shape. `kSameAsRequested` alone made Kokoro grow more (+1,340 MB); arena shrinkage after each run (`memory.enable_memory_arena_shrinkage`) bounds it with no speed loss (RTF 0.13).
- Parakeet int8 on the CPU: no memory arena and no weight prepacking (one copy of the weights).
- Qwen3.5-4B Q4_K_M was killed by the OOM killer at load (4.6 GB anonymous RSS).

## Speech timings

| Model | Runtime | Result | Label |
| --- | --- | --- | --- |
| Kokoro v1.0 fp32 ONNX | ORT 1.24 CUDA EP | 489 ms for 3.18 s of audio (RTF 0.15), CPU busy with a build | J |
| Kokoro v1.0 fp32 ONNX | ORT CPU | 2,242 ms for 3.18 s (RTF 0.71) | J |
| Kokoro v1.0 int8 ONNX | ORT CPU and CUDA | RTF 2.4 to 4.6: int8 ops fall back badly | J |
| Kokoro v1.0 fp16 ONNX | kokoro-onnx 0.6.1 | fails ("zero-size array") | J |
| Kokoro v1.0 fp32 ONNX | ORT 1.24 CUDA EP, `cudnn_conv_algo_search=HEURISTIC`, alone | 0.16 s for a two-word phrase, 0.23 s for six words, RTF 0.13 | J |
| Kokoro v1.0 fp32 ONNX | ORT TensorRT EP | blocked: `SplitToSequence` output has no shape, and ORT's symbolic shape inference fails on the model | J |

## llama.cpp (commit 9c2e0e4, CUDA 13.2, sm_87, 15W, `-fa 1`)

| Model | Prefill pp512 | Decode tg64 | Label |
| --- | --- | --- | --- |
| Gemma 4 E2B Q4_0 (2.63 GiB) | 758 tok/s | 19.5 tok/s | J |
| Qwen3-VL-2B Q4_K_M (1.03 GiB) | 941 tok/s | 22.9 tok/s | J |
| Qwen3.5-2B Q4_K_M (1.18 GiB) | 723 tok/s | 21.2 tok/s | J |
| Qwen3-VL-2B Q8_0 (1.70 GiB) | | 18.9 tok/s | J |

- `jetson_clocks` adds about 3%. Disabling CUDA graphs costs 7%.
- Decode is overhead-bound, not bandwidth-bound: 65% more weight bytes cost only 19% more time, so about 27 of 43 ms per token is fixed per-kernel cost at 625 MHz. Speculative decoding and kernel fusion (TensorRT Edge-LLM) attack that cost; Super clocks took Qwen3-VL-2B decode to 36.0 tok/s (D32).
- The default build aborts in `cuMemAddressReserve` (CUDA VMM pool) on the first image: build with `-DGGML_CUDA_NO_VMM=ON`. (J)
- Gemma 4 E2B with its audio mmproj loads and accepts audio ("experimental" warning). Server RSS with 4,096 context: about 3.5 GB. (J)

## Sources

- https://repo.download.nvidia.com/jetson/common r39.2
- https://pypi.jetson-ai-lab.io/sbsa/cu130/+simple/onnxruntime-gpu/
- https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1
