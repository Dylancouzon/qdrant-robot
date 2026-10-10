# Native Gemma AWQ testing

The selected D117 engines build on the Jetson, but native initialization fails with CUDA out of memory before generation. Native answer quality, cold/warm answer latency, and decode speed remain unmeasured. The unchanged WSL BF16 reference still scores 7/12. Main preserves this testing result without model adoption; exact original records remain under the archive tag in the [experiment index](experiments.md).

## Inputs and native build

The completed WSL archive transfers with native exit zero. Jetson verification confirms its 8,437,452,800 bytes, full SHA256, and all 16 manifest files. Quantization and ONNX export were not repeated. The original WSL quantizer exit remains unavailable.

The installed official TensorRT Edge-LLM 0.11.0 wheel selects `jetson-orin-jp72-cu13-sm87` with TensorRT 10.16.2.10. Its direct builder preserves the D117 defaults for checkpoint-backed weights. The build uses batch one, input 2,048, KV 4,096, draft/verify four, and image total/per-image 512. The actual minimum image profile is four.

The complete native build exits zero in 751.99 seconds (J). The base, assistant, and visual plans contain 89,958,500, 5,644,932, and 38,628,444 bytes, respectively. Engine/config hashes are in the receipt. The native output puts LLM configs and plans directly under `engines/`. The historical adapter expects `engines/llm`, so product integration needs that path correction.

## Allocation failure

The named inference unit calls the installed native speculative runtime with the actual engine paths and both verified checkpoints. The constructor fails before smoke generation with the following error (J):

```text
RuntimeError: CUDA runtime error in cudaMalloc(&data, memoryCapacity): out of memory
```

The native child exits one after 1.04 seconds (J). This duration measures a failed initialization attempt. The run starts zero text/image answers and zero of the 12 frozen development packets. Successful load time, cold/warm token latency, decode speed, answer correctness, and integrated memory fit remain U. No judge runs without answers.

The generated binding metadata and official allocator source explain the capacity requirement. Each binding uses its shape and destination dtype, with 256-byte alignment. The source omits explicit storage aliases and creates a GPU-resident final weight arena. These are calculated requirements, rather than measured successful allocations:

| Component | Bindings | Required arena |
| --- | ---: | ---: |
| Base | 761 | 8,047,141,376 bytes, or 7,674.35 MiB |
| Assistant | 24 | 155,451,392 bytes, or 148.25 MiB |
| Vision | 210 | 305,635,328 bytes, or 291.48 MiB |

The board reports 7,665,096 KiB, or 7,485.45 MiB total RAM (J). The base requirement exceeds the entire board by 188.91 MiB. The PLE table alone requires 4,697,620,480 bytes, or 4,480 MiB. The embedding and LM head each require 768 MiB. Their shared checkpoint key does not permit storage sharing because embedding scaling differs. The base config contains zero storage aliases.

Checkpoint-backed placement keeps weights outside the serialized plan and prepares final-layout GPU weights during initialization. It does not establish streaming PLE access during generation. The allocator error does not emit its requested byte count. The source/config calculation supports the diagnosis without claiming an instrumented allocation size. A smaller KV cache, clean caches, or a prompt change cannot fix this weight-only deficit. This session makes no unchanged retry or new architecture choice.

## Telemetry and preserved failure

Build telemetry records minimum available RAM of 2,740.83 MiB, child VmHWM of 4,570.43 MiB, and peak junction temperature of 61.44 C (J). Sampled child VmSwap is zero, while system counters increase by 349 swap-in and 333 swap-out pages. The build unit reaches 1,212,416 swap bytes. These measurements concern building, with process attribution unresolved.

The failed initialization has five telemetry samples, minimum available RAM of 5,832.53 MiB, and five swap-in pages (J). These snapshots establish no inference headroom or absence of paging. The captured kernel window contains no entries; the CUDA allocation failure is preserved in native stdout.

The first verification attempt exits one because the wrapper's process-wide `RLIMIT_FSIZE` also limits checkpoint extraction to 64 MiB. Its log and partial inputs remain preserved. Bounded pipe capture replaces that limit. One infrastructure retry verifies and extracts the unchanged archive with native exit zero. The builder and initializer use no process-wide file-size limit.

All long jobs used named user units and the existing GPU lock. Every child is terminal, and the lock is free. Private scripts, inputs, logs, telemetry, configs, and failed artifacts remain ignored. Current release `7f67670fa91e`, rollback `6781adbb7189`, accepted UI source, production memories, and backups remain preserved. Repository consolidation changes main's history and records only. All product acceptance targets remain open.

## Sources and evidence

The [native receipt](../bench/results/2026-10-10-jetson-gemma-awq-native.json) records commands, units, invocations, exits, telemetry, artifact hashes, and private evidence hashes. The [measurement rows](../bench/results/2026-10-10-jetson-gemma-awq-native.jsonl) preserve the blocked stages. Private evidence lives under `build/p2/logs/native-20261010` and on the Jetson's isolated experiment directory.

The coordinator's D117 and selected brief remain the design authority. Installed CLI help, `WeightPolicy`, generated base/draft/visual configs, and allocator source at official revision `95515c2f87fba8982db5a519f9022277667b3cc9` supply the mechanics. Saved source copies identify `externalWeightManager.cpp:54-65,258-287,612-699` and `tensor.cpp:162-173`.
