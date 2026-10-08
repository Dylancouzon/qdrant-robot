# Models for the Jetson Orin Nano Super 8 GB

As of 2026-10-07. Labels: **J** measured on an Orin Nano 8 GB, **E** measured elsewhere, **U** unverified. M0 replaces these with our own numbers.

## Summary

- The 8 GB is shared by CPU and GPU. Headless leaves about 7.6 GB. The desktop costs 757 to 865 MB. Add an NVMe swap file as a safety net, but no swap may happen during a turn.
- A 2B-class (V)LM at INT4 runs at 30 to 60 tok/s (**J**). A 4B model is about 15 to 20 tok/s (**E**, scaled from Orin NX) and leaves little room for the rest.
- Small LLMs handle one tool call well and multi-turn tool use badly. Qwen3-1.7B: about 83 to 87% on BFCL simple, 17% multi-turn (**E**). Design for one-shot tool calls; resolve times and dates in code, not in the model.
- The CLIP ViT-B/32 used in the course robot is weak for "this exact object". DINOv2, SigLIP 2, and PE separate instances far better.

## Language and vision-language models

TensorRT Edge-LLM 0.11.0 ships aarch64 Python 3.12 wheels with an Orin (SM87) configuration. Its Orin support matrix lists JetPack 7.2, CUDA 13.2, and TensorRT 10, which likely matches this robot's L4T R39.2. Qwen3-VL-2B and Cosmos-Reason2-2B are in its supported model list. Sources: https://nvidia.github.io/TensorRT-Edge-LLM/latest/user_guide/getting_started/installation.html, https://nvidia.github.io/TensorRT-Edge-LLM/latest/user_guide/getting_started/supported-models.html


| Model | Speed and memory | Runtime | Label |
| --- | --- | --- | --- |
| Qwen3-VL-2B INT4 | 36 tok/s decode, 1,750 tok/s prefill, 4,486 MB GPU memory | TensorRT Edge-LLM 0.10.0, JetPack 7.2, short prompts | J |
| Qwen3.5-2B (VLM mode) | 29.6 tok/s, 4,692 MB GPU memory | TensorRT Edge-LLM 0.10.0, JetPack 7.2, short prompts | J |
| Qwen3.5-0.8B | 59 tok/s | TensorRT Edge-LLM | J |
| Qwen3-1.7B INT4 | 36.5 tok/s | TensorRT Edge-LLM | J |
| Cosmos-Reason2-2B (Qwen3-VL-2B based) W4A16 | 60 tok/s, 4.3 GB peak, 420 ms image TTFT | TensorRT Edge-LLM | J |
| Cosmos-Reason2-2B W4A16 | 56 tok/s, 6.9 GB peak, 75 ms image TTFT | vLLM | J |
| Cosmos-Reason2-2B Q4_K_M | 38 tok/s, 114 ms image TTFT | llama.cpp | J |
| Qwen3-VL-4B | 31.7 tok/s on Orin NX; about 15 to 18 on Nano | TensorRT Edge-LLM | E |
| Gemma 3n E2B | 16.5 tok/s (one forum run) | Ollama | J |
| Gemma 4 E2B | 2.5 GB in LiteRT (the reference demo's LLM); no Jetson numbers found | | U |

Gotchas: Qwen3-VL-2B in FP16 nearly fills RAM; vLLM ran out of memory at launch on the Nano. The first image request takes 0.5 to 3 s.

## Speech

| Model | Finding | Label |
| --- | --- | --- |
| Whisper base.en, 20 s audio | 2.55 s; WhisperTRT about 3x faster at about 60% of the memory | J |
| Whisper tiny.en, 20 s audio | WhisperTRT 0.64 s, faster-whisper 0.85 s | J |
| Parakeet TDT 0.6B v3 | 35.6 ms FP16 on AGX Orin (audio length not stated); engine 706 MiB | E |
| Moonshine v2 Tiny (streaming) | 237 ms latency on a Raspberry Pi 5; 12.0% WER | E |
| Kokoro-82M | Runs on Orin Nano (forum); used in the Jetson AI Lab Reachy tutorial | J (no timing) |
| Piper | Runs on Orin Nano 8 GB | J (no timing) |
| Silero VAD, openWakeWord | CPU, about 150 MB together | U |

Hall noise: Whisper-Medium WER rose from 6.4% to 34.2% at 0 dB SNR (**E**). Use a close-talk push-to-talk mic; keep a touch fallback.

## Vision

| Model | Finding | Label |
| --- | --- | --- |
| YOLOv8n 640, TensorRT | FP16 4.43 ms, INT8 3.49 ms | J |
| RF-DETR Base | 14.8 ms FP16 | J |
| ViT-B/16 224, TensorRT FP16 | 19.9 ms | J |
| ViT-S at 364x490, FP16 | 30.75 ms on an Orin Nano 4 GB | E |
| SAM 3 | 462 ms on AGX Orin; too slow for live use | E |

Instance retrieval (ILIAS, mAP@1k, 5M distractors, **E**): CLIP-L 12.1, DINOv2-B 14.3, DINOv2-L 18.5, SigLIP2-L 25.3, PE-L 27.1. With a linear adapter: SigLIP2-L 37.3, PE-L 39.6. PeKit personalized objects: DINOv2-L 94.9 against CLIP-L 88.3. A patch-level rerank (MaxSim over patch tokens) helps most under clutter. These are large encoders on benchmark data; they do not establish small-encoder results on booth footage. DINOv2 has no text tower, so spoken image search needs caption text or an aligned text encoder.

## Closest existing stack (not proof that ours fits)

The Jetson AI Lab tutorial "reachy-mini-jetson-assistant" runs, on an Orin Nano 8 GB: Cosmos-Reason2-2B Q4_K_M (about 2.2 GB, llama.cpp in Docker), faster-whisper (CTranslate2 built with CUDA arch 8.7), Kokoro ONNX, Silero VAD, YuNet face tracking at about 15 Hz. It needs headless mode and an 8 GB NVMe swap file, leaves almost no headroom, and has no memory shards or retrieval encoders. Its jp6/cu126 wheels and Python 3.10 pins do not apply to this robot (Python 3.12, L4T R39.2). Qualify every wheel here: Python ABI, architecture, CUDA libraries, execution provider, and an actual GPU run. If GPU speech fails qualification, start with CPU Moonshine and CPU Kokoro ONNX and measure their contention with the LLM. Gotchas from it: pip CTranslate2 is CPU-only; install onnxruntime-gpu from the Jetson index (jp6/cu126); pin numpy 1.26.4 on Python 3.10.

## Sources

- https://nvidia.github.io/TensorRT-Edge-LLM/latest/user_guide/performance/performance-benchmarks.html (note: one Nano case where MTP speculative decoding lowered throughput and raised memory)
- https://nvidia.github.io/TensorRT-Edge-LLM/latest/user_guide/getting_started/support-matrix.html
- https://github.com/hokwangchoi/jetson-orin-nano-benchmarks
- https://forums.developer.nvidia.com/t/performance-inquiry-optimizing-qwen3-vl-2b-inference-for-2-qps-target-on-orin-nano-super/359639
- https://github.com/NVIDIA-AI-IOT/whisper_trt
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/44
- https://arxiv.org/abs/2602.12241 (Moonshine v2)
- https://vrg.fel.cvut.cz/ilias/ and https://arxiv.org/abs/2502.11748 (ILIAS)
- https://arxiv.org/abs/2502.02452 (PeKit)
- https://arxiv.org/pdf/2608.22472 and https://arxiv.org/pdf/2511.22138 (small-model tool calling)
- https://www.jetson-ai-lab.com/tutorials/reachy-mini-jetson-assistant
- https://www.ridgerun.com/post/saving-ram-memory-on-nvidia-jetson-with-agent-skills
