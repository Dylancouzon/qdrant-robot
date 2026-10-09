# Plan to raise the robot's capability ceiling

P2 supersedes the execution sequence below after Dylan's architecture-level correction. Its testing-first architecture-comparison draft is superseded before dispatch. Read STATE.md for the selected architecture/build task. F1j implementation is paused. The following P1 plan preserves its historical alternatives and evidence.

Planning date: 2026-10-09. Baseline: main at fcfd32a. This session produces the plan; the next session executes it. J means measured on this Jetson, E means measured elsewhere, and U means unverified. All proposed gains and resource budgets below are U. D79 records Dylan's scope and worker choice; D83 removes execution deadlines and preserves the review gates.

## Recommendation

Build a continuous, grounded conversational assistant around the existing 2B VLM and Qdrant Edge. Improve the evidence the robot sees, retain useful context beyond its short prompt, and specialize the model on that evidence. These changes address the shared causes of weak detection, recall, and conversation.

The desired demonstration is a sustained visit: discuss several objects, move them, change subjects, and return to earlier details. The robot should distinguish similar objects, remember the relevant evidence, and give natural follow-up answers. Its memory panel should expose the evidence behind its answer. Every deployed model and query stays on the Jetson.

Start with useful conversational memory, the evidence contract, a fresh challenge, and failure attribution. Prepare training and perception work in parallel. Choose subsequent work from measured gaps and qualification results. The session, experiments, training, and workers have no preset duration limit. Continue as long as needed, with progress checkpoints and complete validation. A large measured capability gain is the objective.

## Why this changes the previous approach

| Constraint from prior decisions | Concrete change to test |
| --- | --- |
| D74: five brains and nine prompt shapes mostly failed on missing or contradictory evidence. | Build searchable, source-linked visual and dialogue events. Measure evidence recovery separately from answer generation. |
| D75: fixed code answers scored 44/74; retrieval into the brain scored 38/74. These are different variants, not a controlled training result. | Compare the same 2B on original versus verified sufficient evidence. Train only on residual evidence-use and dialogue failures. |
| D27: old visual answers contaminate the present; scene changes discard assistant history. | Separate current visual state from historical observations and dialogue. Preserve linguistic continuity with source and time boundaries. |
| D39: 512 image tokens gave no reliable global gain. | Give a stable object crop detail when needed; compare it against the same token budget on the full frame. |
| D43/D64: missing boxes block teaching; only nano at 384x640 was tested. | Compare YOLOE-26s against nano at identical vocabulary and resolution before considering domain training. |
| D68/D76: 4B missed the memory floor; live conversation swaps. | Measure active paging in a continuous process. Test capacity enablers only against the complete robot. |
| D19: TensorRT export lacked an x86 NVIDIA host. | The 3080 now exists. Qualify exact export and runtime compatibility before any extended port. |

D75's 44/74 is development evidence, not a fresh acceptance result. D64's object recognition reached 15/22 phones and 15/35 teddies at zero tested false matches (E). Existing long-context claims cover 2K prompts and 64-token answers, not sustained conversation. See [lessons](lessons.md), [grounding](grounding.md), and [stack](stack.md).

## Execution order and machine ownership

| Phase and readiness | Lead and Mac | Jetson, one exclusive owner | WSL 3080, one exclusive owner |
| --- | --- | --- | --- |
| Qualify evidence and deployment | Freeze the evidence contract and worker interfaces. An evaluation worker prepares the fresh challenge and data manifests. | Reconcile release/jobs. Start the 30-minute continuous baseline once its fixtures are frozen. | Qualify a tiny adapter and export. Use the production evidence contract before bulk generation. |
| Build and compare qualified candidates | Implement event retrieval and dialogue continuity. Prepare perception candidates separately. | Finish baseline. Compare detector candidates and integrate the memory path when ready. | Generate verified training data and train if evidence-use and export gates pass. |
| Integrate the selected candidate | Select from development evidence and review the diff. Keep other useful work recorded for the next comparison. | Check integration, including the selected quantized adapter when qualified. | Export the selected checkpoint and release the GPU. |
| Validate, review, and release | Score, review, document, and preserve rollback. | Run the fresh challenge within a continuous 30-minute visit, then required regressions. | Analyze errors on development data; keep final acceptance isolated from tuning. |
| Continue against remaining gaps | Choose the next intervention from measured results. Repeat the relevant gates and comparisons. | Test the next candidate or extend endurance measurements. | Support justified data, training, runtime, and export work. |

Phases advance when their prerequisites pass. Complete evaluation and review for every adopted change. Reassess routes after paired results and at least hourly; checkpoints guide priorities without terminating healthy jobs. Stop or redirect an approach when evidence, a diagnosed blocker, or resource constraints justify it. Record the reason and reopening condition. For each new comparison, freeze fresh acceptance sources before tuning; used challenges become development evidence.

WSL is the default for data generation, annotation teachers, preliminary detector/brain comparisons, training, conversion, and CPU-heavy preparation. The Mac coordinates, checks code, and handles independent tasks while WSL is occupied. Do not serialize work onto the Mac when WSL can finish it faster. Keep WSL GPU jobs sequential; Mac exports or preparation can overlap training. Jetson-specific engines and all acceptance measurements stay on the Jetson.

## F0: Freeze the contract and choose the training branch

Read D74/D75 through `tools/results.py`, then inspect the failed development rows needed for attribution. Keep failure counts: absent/wrong observation, relevant evidence not retrieved, correct evidence ignored, dialogue continuity lost, and runtime delay/paging. Several causes can affect one turn; retain their evidence IDs.

Use 24 development questions across these causes. Compare current evidence with a verified sufficient evidence packet on the same model, settings, and question. This is an upper-bound diagnostic, not a deployable score. Exclude deterministic actions, identity rulings, and superseded direction questions. If at least eight correct-evidence questions still fail, specialize the model. Otherwise prioritize perception and retrieval, and skip a speculative language training run. This threshold selects scarce compute; it does not establish statistical significance.

An evaluation worker freezes a fresh 48-question challenge before tuning: three complete visits of 16 questions, with different objects, source scenes, names, and wording from development. Use the same fixed pacing for baseline and candidate; together the visits form a 30-minute continuous-process run. This supplies a useful overnight comparison, not full milestone acceptance. Include visual detail, older observations, references across topic changes, corrections, absent evidence, and plain conversation. Preserve old suites unchanged. Store sources, split groups, hashes, evidence answers, rubrics, and provenance. Keep final answers and baseline failure details with the reviewer, hidden from builders and training generation. Give training workers an explicit source-ID allowlist that excludes all challenge sources. Score the challenge only for the baseline and selected final candidate. Reserve separate unseen probes for D75's pending evidence-fix check.

Log a continuous-process baseline, without replay restarts: prompt tokens, pending work, stage times, MemAvailable, process memory, `pswpin`/`pswpout`, major faults, and tegrastats. Existing allocated swap is separate from new paging. Attribute live swap before claiming any specific queue or model caused it.

## F1: Make Qdrant the assistant's effective context

Before parallel implementation, freeze one record contract: event ID, source IDs, timestamp, visitor/session scope, kind, object references, searchable text, and expiry. Preserve D60/D68/D70 visitor and restart rules. Use a small 384-dimensional event shard if adding a named vector to the old shard needs migration. Keep source records authoritative and include the new shard in retention, deletion, backup, and rollback. Hydrate and validate source links on retrieval so stale derived records cannot resurrect forgotten content.

BGE currently truncates at 128 tokens (`robot/text_embed.py`). Embed short event units, then retrieve neighboring dialogue turns through their source IDs. Preserve complete turns in payloads; a long episode must not be silently truncated before embedding. Direct retrieval is the first implementation. Summaries are an extension only if reference resolution still fails.

Freeze the production answer path as well. Ordinary sight, memory, knowledge, and conversation questions use one generative answer path with verified evidence. Identity rulings and actions stay in code. D75 sends 31/74 M2 answers through its verbatim path, so an adapter must be evaluated with that path bypassed for ordinary answers. Otherwise, its effect is hidden.

Compare three arms: current production; improved evidence with the unchanged 2B; and the selected adapter with that same evidence. The latter two use identical context and generation limits. Replace and delete ordinary code-answer branches only when the selected generative arm beats production overall and preserves per-capability quality on the frozen comparison. If it loses, retain production and record the result; do not claim an adapter win from unused weights.

Replace recency-only scene recall with semantic retrieval over visual events and dialogue episodes. Keep current detections separate from historical evidence. Reuse BGE and existing Edge shards where feasible; do not add an embedding model as the first step.

Each retrieved event carries its source IDs, capture time, visitor scope, object/track references, observed or told facts, and uncertainty. Store original utterances and observations as authority. Derived summaries link to those sources and disappear when their sources are forgotten. An assistant's invented assertion never becomes observed evidence. Dialogue summaries preserve requests and references without turning spoken guesses into facts.

Use semantic candidates plus explicit object/time filters, then deduplicate and select a small evidence set. Preserve exact named-object lookup. Maintain a short dialogue window and retrieve older episodes, so topic changes do not erase the conversation. Do not copy the whole history into a larger prompt. Start at the existing 2K context; count the rendered prompt and reserve output space before generation. Test 4K only after integrated headroom and paging pass.

The measured alternative is compact episode summaries with source links; qualify it only after direct retrieval leaves a demonstrated reference-resolution gap. Edge 0.8.0 locally exposes named-vector queries, filters, vector updates, prefetches, and `Fusion.Rrf`; it has no `query_batch`. Fusion can combine candidates within a shard; merging independent shard results remains application work. No server migration is required.

Pair evidence quality with conversation output: allow one to three complete sentences and up to 160 tokens when useful. Separate caption generation from spoken reply stopping. Retain conversational replies across scene changes while marking visual statements as historical. Cancel stale generated speech when a new accepted turn supersedes it; bound replaceable visual work. Test injected interruptions first. Acoustic barge-in and echo handling still need physical validation.

Success: evidence recall@5 rises by at least 20 percentage points, or reaches 90%, on the fresh older-memory questions. End-to-end answers must also improve. No cross-visitor attribution, deletion regression, or promotion of generated claims to observed facts is allowed.

## F2: Improve visual evidence before teaching the brain

Run one controlled detector comparison: YOLOE-26n versus YOLOE-26s, the same 50 prompts, 384x640 input, TensorRT FP16, and the same tracking policy. Measure box recall by object size, occlusion, and held status at a matched false-positive rate. Calibrate on development data, then freeze thresholds. Record actual detector invocation rate separately from track updates.

The evaluation worker owns annotation and data splits. Copy the existing 90-second real-object clip through the project workflow. Start with 32 stratified frames across actions and backgrounds; visually verify labels and boxes. Expand toward 80, then further when coverage or uncertainty requires it. The full clip has already influenced development and cannot become fresh acceptance through a new frame split. Use independent capture groups and physical object instances for acceptance. For overnight acceptance, use Objectron videos absent from previous re-identification work, sampling cups, cameras, bottles, and books where available. Objectron covers real viewpoint variation; it does not establish clutter or hand-occlusion performance. An optional small EPIC-KITCHENS subset adds hand-object interactions if its terms and download limits fit this private experiment. Its automatic hand-object labels need manual verification before scoring. Prior COCO re-identification IDs were not saved, so COCO remains development-only unless the original sampling manifest can be recovered and exclusions proved. The existing `bench/reid.py` download path supplies Objectron video discovery. Freeze whole video/object groups before sampling; preserve annotation files and licenses. Estimate disk use and download selected sources; expand the dataset when coverage requires it. A missing or previously used source stays in development. Until independent sources are available, label the comparison development-only and withhold a generalization claim. Synthetic composites are training or development material only.

The first adoption threshold is at least 10 percentage points of real-object recall gain at matched false positives. The full robot must retain its 15 fps detection/tracking target, 500 MB headroom, and no active-turn paging. Quality-first tradeoffs can be measured, but a missed target remains visible and needs an explicit decision. Never describe interpolated tracks as 15 fps detection.

For objects already localized, compare a focused crop description against the full-frame description at the same image-token budget. Capture color, shape, distinguishing marks, and changes from stable keyframes. Run detailed VLM work during safe idle periods through the existing single inference slot. The question path can request a fresh observation when needed. A crop cannot recover an undetected object. Store these descriptions with frame/object sources in Edge.

Exclude the prior Objectron test videos. Cup IDs: `batch-37-28`, `batch-10-31`, `batch-33-34`, `batch-2-12`, `batch-16-47`, `batch-35-33`, `batch-3-4`, `batch-5-39`. Camera IDs: `batch-3-11`, `batch-7-44`, `batch-5-31`, `batch-12-32`, `batch-14-47`, `batch-10-48`, `batch-10-47`, `batch-7-24`. Record dataset version, URL, license, video/participant/object IDs, frame hashes, annotation origin, prior use, and split. Objectron uses C-UDA-1.0; EPIC-KITCHENS uses CC BY-NC 4.0. A source without suitable usage terms is skipped. Start with a few clips; check their sizes before downloading and expand by coverage needs.

Use diverse, stable views for taught-object multivectors, instead of three nearly identical timed crops. Compare recognition on new views at the existing false-match constraint. Do not auto-learn unconfirmed identities. Bound crop embedding work because D57 measured strong GPU contention.

Detector training is eligible if repeated in-vocabulary misses persist and reliable training coverage is available. Use a larger teacher for candidate annotations on training-only real frames, then visually verify boxes and negatives. Preserve the 50-class coverage with complete replay data; do not silently narrow the robot to a few demonstration props. The initial 32–80 annotated clip frames cannot supply that coverage alone. Box-only data uses `YOLOEPETrainer` and the matching detection configuration. `YOLOEPESegTrainer` requires segmentation labels. Pilot throughput and GPU memory, then evaluate checkpoints for development gains. Resolve annotation and export prerequisites before bulk training; retain the pretrained baseline for comparison. This is fine-tuning with verified pseudo-labels, not a claim of validated teacher distillation.

## F3: Train a small brain that uses evidence and converses

The primary training candidate is the existing Qwen3-VL-2B with a language-only LoRA adapter. QLoRA is a fallback requiring a separately verified four-bit loading path. Freeze its vision encoder and projector. Verify the actual trainable parameter names; a broad q/k/v/o match must not accidentally train vision layers. The same source-backed evidence format used in production must appear in training.

First perform a tiny training/export/load test. Pin the base checkpoint, tokenizer, processor, training packages, and llama.cpp revision. Train a few steps, export a PEFT adapter, convert it for llama.cpp, and make text and real image requests with the existing projector. Compare enabled versus disabled adapter outputs. Inspect tensor names, quantization, chat template, and source hashes. If adapter conversion fails, diagnose it and test a CPU merge followed by GGUF conversion. Resolve deployment before bulk training. Log unresolved blockers and route changes; require a changed intervention before retrying a failed method.

The official Qwen trainer supports LoRA but does not supply a four-bit loading path. Start with that trainer, FP16 mixed precision, rank eight, alpha 16, microbatch one, accumulation eight, 1,024 tokens, gradient checkpointing, an initial one-epoch pilot, and learning rate 0.0002. Verify assistant-only loss and freeze vision/projector parameters. Record and freeze the exact launcher and pinned package versions during preflight. Exact 10 GB fit and the complete adapter/projector export remain U. If this fails for memory, qualify an explicit Transformers/PEFT four-bit loader adaptation; do not pass an unsupported quantization flag to the official trainer. Use a separate training environment on WSL; preserve the working inference environment.

Generate facts and timelines programmatically, then ask the installed Gemma4:12B or Qwen3.5:9B teacher for varied questions and natural grounded answers. Use one loaded teacher at a time. Pilot 32 examples and calculate accepted examples per minute. Begin with 512 accepted examples, then expand coverage and diversity according to development results. Corpus size has no preset ceiling; source quality, measured learning, and available resources determine expansion.

Mix evidence questions with distractors and changed facts, multi-turn references and corrections, absent-evidence questions, grounded visual descriptions, and ordinary conversation. Include short and longer answers, not one fixed response style. Counterfactual colors/names force evidence use. Reject invented facts, unsupported ownership, malformed source references, near duplicates, and contradictory targets. Audit at least 50 stratified examples visually or against the fact generator. Teacher agreement alone is insufficient. Keep faces and personal identity training out of this corpus.

Split by source scene, physical object, generated world, and whole dialogue before paraphrasing or augmentation. Preserve a development split and a separate final challenge. Training never reads held-out answers, images, transcripts, or judge verdicts. Synthetic performance is a diagnostic; it does not establish real-object perception.

Run a 20-update throughput/VRAM pilot. Estimate remaining work from processed tokens, including evaluation and export. Train as long as development evidence supports progress. Use learning curves, convergence, regression, and resource health to decide when to stop or change the run. Save periodic adapters and select on development evidence-use and dialogue scores. Compare the adapter with the unchanged base using identical evidence and generation limits. Adoption requires at least 10 percentage points on correct-evidence answer accuracy, with no meaningful loss on current sight and ordinary chat. Confirm the selected quantized model on the Jetson; box answers are not acceptance numbers.

## F4: Capacity enablers and larger alternatives

The preferred architecture keeps one resident VLM. Compare it with two larger alternatives only after the evidence path is useful:

| Alternative | Potential gain | Decisive experiment and adoption condition |
| --- | --- | --- |
| TensorRT Edge-LLM with Qwen3-VL-4B INT4 and FP16 vision | More language capacity if its integrated memory use fits. | First qualify a 2B text/image control. Then build and measure 4B with every component active; require quality gains and the integrated resource floor. |
| A text conversational model plus asynchronous visual descriptions | Separate dialogue optimization from visual prefill and allow text-only training. | Compare on fresh visual questions, sustained dialogue, and stale-evidence failures. Measure both resident models or reload latency. Stop if the second model removes the memory benefit. |

TensorRT is a capacity hypothesis, not a promised speedup. NVIDIA publishes 32.3 tok/s for Nano 2B at 2K; the robot recorded 36 tok/s with llama.cpp under different conditions. NVIDIA lists the Qwen3-VL family, but no Nano 4B integrated result proves fit. Jetson runtime versions align with the current support matrix. WSL Ubuntu 26.04 and 10 GB VRAM do not match the documented Ubuntu 22.04/24.04 and recommended 24 GB export setup. Qualify a supported container first. Judge further toolchain work by measured potential and compatibility evidence.

Test upstream Kokoro FP16 and 2B Q8 KV as capacity enablers, one change at a time. Record loaded/exercised memory, paging, speech quality, and first-audio latency. The 4B Q8 KV trial already failed the memory floor. CPU Kokoro previously freed about 640 MB with a short phrase up to 0.83 s. None of these facts proves enough room for longer context. Use the simplest measured configuration that supports the capability gain.

Run one WSL GPU job at a time, with as many justified iterations as needed. Choose brain specialization, detector training, or runtime qualification from the largest measured gap and each route's prerequisites. Reassess alternatives at progress checkpoints. Continue perception and Edge memory work while unresolved training prerequisites are investigated. A completed training artifact alone does not justify adoption.

## Nighttime validation and OS capacity

Saved footage and independent real video support overnight perception, tracking, retrieval, conversation, and integrated resource comparisons. Replay source timing, resolution, and scene changes through the production file-source path. Score footage at its real cadence. Keep saved camera footage separate from external data, synthetic scenes, oracle text, and recorded speech in the report. External video increases diversity but does not reproduce the robot camera's optics, room lighting, microphone, or speaker.

Live camera focus/exposure, distant faces, booth noise, acoustic echo, and physical interruption quality remain daytime checks. No person must stay awake for this plan. Replay actual recorded speech when available and label synthesized audio separately. A quiet dark live frame must not replace the planned visual evidence.

Dylan authorizes OS changes on the dedicated robot hardware. Rank changes by measured capacity for the chosen capability. The Jetson already uses `multi-user.target`; its largest observed idle userspace services were journald at about 37 MB RSS and snapd at about 22 MB. Those figures do not establish hundreds of megabytes of reclaimable headroom. Record per-process PSS, service ownership, kernel/slab memory, `/proc/pressure/memory`, and active paging before selecting changes.

Audit OS capacity when memory blocks capability. Save prior settings and service states; compare one justified intervention at a time on the same active workload. Continue while measurements identify useful changes. Preserve SSH, networking, camera/audio services, thermal control, and the tested power mode. CPU affinity and cgroup limits are workload controls, not extra memory. Disabling swap is not evidence that the previous working set fits.

Prefer a separate Ubuntu 24.04 GPU container on WSL if the training/export package needs that supported userspace. Check Docker daemon access and GPU passthrough first. Keep the current WSL host and known inference environment working. JetPack already matches NVIDIA's current Orin runtime matrix; an OS reinstall or firmware flash has no measured benefit here. Any reboot requires a verified remote recovery path and a rollback record. If more capacity is needed, compare a CPU TTS configuration or fewer GPU execution providers against the current shared ORT CUDA sessions. Larger provider/runtime changes need a measured full-stack comparison because D68 attributed much of the apparent TTS footprint to shared CUDA kernel code. Native TensorRT already saved memory for detection; that does not establish savings for other models. Keep the measured winner only if longer dialogue or a stronger model benefits.

## What qualifies as a substantial improvement

Freeze these experiment rules before implementation. They supplement existing targets; they do not lower them.

- The fresh 48-question challenge should improve at least 20 percentage points over the paired baseline, or reach at least 90% by halving errors. Report each capability separately so easy conversation cannot hide failed perception or recall.
- A 30-minute continuous visit must retain earlier references through topic and scene changes, produce complete useful replies, and show no active-turn swap-in or swap-out. Minimum available memory remains 500 MB. Log prompt truncation and pending work, rather than treating a process that stayed alive as success.
- Compare actual detector recall and named-instance recognition at matched false claims. Zero false identity claims, consent, real deletion, restart behavior, and stored-evidence provenance remain fixed outcomes.
- First synthesized audio must not regress by more than 0.2 s p50 against the paired baseline. Record p95 and complete-answer duration. Keep physical audible latency and its 1.2/2.0 s targets separate until a speaker measurement exists.
- Run the old development and safety regression suites once after selecting the integrated candidate. A failed challenge remains a failed challenge; do not tune on it and reuse it as unseen evidence.

These are ambitious goals, not forecasts. Ship each validated improvement, then continue against the largest remaining ceiling gap. The 30-minute comparison and M4's eight-hour run are measurement protocols. Neither sets a work deadline. This plan alone does not close M4.

## Required gates

Removing execution deadlines preserves every gate and its criteria. The runner reads the linked files directly. Pass each model explicitly:

| Checkpoint | Command | Checks |
| --- | --- | --- |
| Before an architectural change | `python3 tools/gate.py design --model gpt-6.1-sol '<brief and evidence>'` | [Design rules](../gates/design.md): two real alternatives, simplest useful solution, over-engineering, duplication, and a Jetson comparison. |
| After each completed task | `python3 tools/gate.py review --model gpt-6.1-sol '<scope and evidence>'` | [Review rules](../gates/review.md): correctness, performance, unnecessary complexity, overfitting, scope, and optional edge cases. |
| At a milestone | `python3 tools/gate.py milestone --model gpt-6-astra '<milestone and evidence>'` | [Milestone rules](../gates/milestone.md): acceptance, architectural drift, over-engineering, and remaining capability gaps. |
| After two failed approaches or an architectural doubt | `python3 tools/gate.py design --model gpt-6-astra '<question and prior evidence>'` | Independent counsel on the approach and alternatives. |

The pre-commit hook runs deterministic checks. Command watchdogs remain operational safeguards; a timeout records an incomplete operation and requires diagnosis. It never establishes a failed capability hypothesis. Freeze each task's scope and acceptance before dispatch. Carry optional concerns without growing the task; fixed-outcome failures remain blocking. Log each route's evidence, decision, and reopening condition.

## Sol 6.1 low worker handoffs

Sol is the next session's independent reviewer. Use `gpt-6.1-sol` for that role and low-reasoning `gpt-6.1-sol` workers for scoped implementation, as Dylan requested. Pass the model explicitly to `tools/gate.py review`. Use Luna for research. No nested agents. The lead owns STATE, DECISIONS, integration, machine reservations, and acceptance. Respect D44: parallel builders need disjoint files and one Jetson owner.

| Worker | Allowed work | Required return |
| --- | --- | --- |
| Evidence and conversation | `robot/memory.py`, `robot/brain.py`, relevant tests; propose integration hooks for lead-owned `robot/main.py`. | Source schema, migration/rollback plan, scored retrieval comparison, token budgets, and deletion checks. |
| Perception | `robot/detect.py`, `robot/things.py`, relevant benchmarks/tests and isolated export assets. | Same-vocabulary detector comparison, audited data manifest, actual detection cadence, and model hashes. |
| Training | Isolated WSL training directory; one scoped training script and manifest; no shared runtime edits. | Export proof, accepted-data counts/hashes, trainable parameter names, throughput, peak VRAM, checkpoint, and paired scores. |
| Evaluation and integration | A fresh worker owns new fixtures, source manifests, and bounded harness additions. The lead owns `robot/main.py`, `robot/audio.py`, shared configuration, and deployment. | Hidden challenge answers for the reviewer, disjoint source allowlists, timed replay commands, and complete-job records. |

Use one scoped task per worker with a fresh brief rather than inherited full conversation. Replace workers at task boundaries or context pressure, with a written checkpoint and ongoing job ownership preserved. Respect the available concurrency limit; evaluation preparation finishes before its slot is reused. Each brief names baseline SHA, decisions, paths, interfaces, acceptance, machine ownership, progress signals, disk budget, and blocker conditions. Workers return changed paths, commands, exact evidence files, unresolved risks, and next command. Lead reads the diff before task review and deployment.

Record remote jobs with host, directory, PID/unit, command, release, start time, log, progress signal, and stalled-process recovery. Record any command watchdog separately from expected completion time. Continue healthy jobs as needed and preserve ownership across worker changes. Use the existing Jetson deploy/run/collect/rollback workflow and each host's GPU lock. Pin new models and preserve the previous release and memory backup. Training data generation, training, and export share the WSL GPU sequentially. Do not change teachers or models during final acceptance.

## Machine reconciliation and first action

Read-only check at 2026-10-09 05:42–05:46 UTC: Jetson idle, current release `4387936b8ee9`, about 6,033 MiB available, 107 MiB allocated swap, and 105 GB disk free. Boot ID: `09b4bb27-f975-441c-9d00-7af446ec7de6`. The real clip exists at `shared/clips/live-items-1.avi`. These are idle observations, not a runtime budget.

WSL: RTX 3080 with 10,240 MiB VRAM, 363 MiB used, 0% utilization; about 23 GB RAM available and 798 GB disk free. Ollama has Gemma4:12B and Qwen3.5:9B installed, with neither loaded. Use `/usr/lib/wsl/lib/nvidia-smi`; the command is absent from the SSH PATH. Docker 29.7.2 and daemon access work; GPU-container passthrough still needs qualification. Passwordless sudo is unavailable, so use existing access or user-space setup before escalating a host change. The working environment is `~/qdrant-robot-box/venv`, not `.venv`. Its CUDA 13.2.86 export setup and patched inference binary are documented in [lessons](lessons.md). Mac: 24 GiB RAM and about 240 GiB disk free. Recheck ownership and jobs at execution start.

First command: `python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6`. Then run F0 and dispatch the small export preflight and perception preparation. Do not start by repeating the five-model or nine-prompt sweep.

## Sources and verification limits

- Local evidence: D19, D27, D35, D39, D43, D57, D64, D66, D68, D74–D78; [grounding](grounding.md), [detector](detector.md), [booth UX](booth-ux.md), and [lessons](lessons.md). Installed `.venv/lib/python3.12/site-packages/qdrant_edge/__init__.pyi` governs Edge 0.8.0 APIs.
- Official [Edge reading API](https://qdrant.tech/documentation/edge/edge-api/reading-data/) and [configuration](https://qdrant.tech/documentation/edge/edge-api/configuration/) describe current features. They do not establish availability in older installed versions.
- Official [Objectron dataset](https://github.com/google-research-datasets/Objectron), [indices](https://github.com/google-research-datasets/Objectron/blob/master/index/README), and [license](https://github.com/google-research-datasets/Objectron/blob/master/LICENSE) document selective video access. The [EPIC-KITCHENS dataset](https://epic-kitchens.github.io/2026) and [selective downloader](https://github.com/epic-kitchens/epic-kitchens-download-scripts) provide an optional interaction source; automated annotations are not ground truth.
- Official [YOLOE models, training, and export](https://docs.ultralytics.com/models/yoloe/) and [YOLOE-26 configuration](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/models/26/yoloe-26-seg.yaml) support the detector candidates. [TensorRT compatibility](https://docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/engine-compatibility.html) requires qualifying the final engine on the target.
- Official [Qwen3-VL trainer](https://github.com/QwenLM/Qwen3-VL/blob/main/qwen-vl-finetune/qwenvl/train/train_qwen.py), [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization), and [llama.cpp adapter converter](https://github.com/ggml-org/llama.cpp/blob/master/convert_lora_to_gguf.py) support investigating language adapters. Their combination does not establish this exact export or 10 GB training fit.
- Official [CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/contents.html), [Microsoft CUDA guidance](https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl), [Linux memory pressure](https://docs.kernel.org/accounting/psi.html), and [cgroup memory controls](https://docs.kernel.org/admin-guide/cgroup-v2.html) ground the OS alternatives.
- NVIDIA [Edge-LLM installation](https://nvidia.github.io/TensorRT-Edge-LLM/0.11.0/user_guide/getting_started/installation.html), [supported models](https://nvidia.github.io/TensorRT-Edge-LLM/0.11.0/user_guide/getting_started/supported-models.html), [benchmarks](https://nvidia.github.io/TensorRT-Edge-LLM/0.11.0/user_guide/performance/performance-benchmarks.html), and [support matrix](https://nvidia.github.io/TensorRT-Edge-LLM/user_guide/getting_started/support-matrix.html) were checked by Luna during planning. The [Jetson tutorial](https://github.com/NVIDIA-AI-IOT/jetson-ai-lab/blob/main/src/content/tutorials/model-optimization/tensorrt-edge-llm.mdx) gives export and disk prerequisites. No new runtime benchmark was run in this session.
