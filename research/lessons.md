# Lessons: what we tried, what happened, what to avoid

Read this before you propose an experiment. Each avenue has one row; reopen one only with a named change (D77). J means measured on our Jetson, E measured elsewhere, U unverified. D-numbers point to [the decision archive](archive/decisions-2026-10-10.md); [DECISIONS.md](../DECISIONS.md) keeps the ones still binding. Paths missing from main are in tag `archive/2026-10-10/pre-cleanup`: `git show archive/2026-10-10/pre-cleanup:<path>`.

## Brain and runtime

| Avenue | Outcome | Status | Ref |
| --- | --- | --- | --- |
| Qwen3-VL-2B on llama.cpp | 39/47 recorded judged, 29 tok/s, 1.59 s first WAV p50 (J) | Current brain | D27, D35, Gemma full stack |
| Qwen3-VL-4B | 29/39 and 37/47 vs 2B 32/39 and 41/47; leaves 190 MB, swaps about 900 MB (J) | Rejected until RAM frees | D27, D35, D66, D68 |
| Qwen3.5-2B / 4B | 24/39; recurrent layers defeat prefix caching (1.63 s first token). 4B OOM at load (J) | Rejected | D27 |
| Gemma 4 E2B omni on llama.cpp | 14/21 then 26/39; weak sight (stop sign called a rack); 3.5 GB (J) | Rejected | D22, D29 |
| Gemma 3 4B, LFM2-VL-3B, MiniCPM-V 4 | Out of memory, or image tiling overflows 2K context | Rejected | D30, D74 |
| Gemma E2B LiteRT 0.18 (Vulkan) | Screen 9/12 (J) vs WSL Qwen 7/12 (E); full stack 31/47 vs 39/47, first WAV 4.9 s p50 (J) | Rejected | Gemma full stack; `archive/gemma-fit.md`; `bench/results/2026-10-10-gemma-full-stack.json` |
| Gemma E2B INT4 AWQ on TensorRT Edge-LLM | Engines build; init OOM: base weights 7,674 MiB > 7,485 MiB board (J) | Blocked; needs a weight-placement change | D115–D121, D117 result; `archive/jetson-trt.md` |
| Granite 4.0-H-Micro 3B + SmolVLM2-500M observer | 26/47 oracle (J); plain vs tool-result evidence both 21/39 | Rejected | D111–D114 |
| Qwen with CPU Kokoro (no decode pause) | Recorded 39/47 unchanged, but stress lost four net judged answers and five net joint passes (cause unverified); paging windows 10/48 vs 36/48; +1.79 s first audio p50 (J). Compares whole speech policies, not placement alone | Option if paging becomes the blocker | Gemma full stack |
| Model tool calls for memory | 2B models called memory on 10–12 of 13 sight questions (J) | Rejected; retrieval in code | D21 |
| Prompt variants and prompt bake-off | Plateau; no 2B beats code answers by prompting. Shape I (evidence after image) kept | Done | D30, D74 |
| 512 image tokens | 40/47 both; scene changes pay up to 0.49 s (J) | Rejected | D39 |
| LoRA / response distillation | Evidence, not language, was the bottleneck | Deferred until evidence is sufficient | D74, D81, D87 |
| TensorRT Edge-LLM FP16; Kokoro FP16 | FP16 LLM nearly fills RAM; Kokoro FP16 conversion fails or gives zero-size audio | Rejected | D19, D68, D112 |
| Kokoro int8 ONNX (CPU and CUDA) | RTF 2.4–4.6; int8 ops fall back badly (J) | Rejected | `stack.md` speech timings |
| Kokoro on ORT TensorRT EP | Blocked: `SplitToSequence` has no output shape; symbolic shape inference fails (J) | Blocked | `stack.md` |
| Kokoro upstream fp16 asset (model-files-v1.1) | Distinct from the failed local conversion; never tested | Open, measure loaded RAM | `stack.md` |
| Qwen3-VL-4B with q8_0 KV | KV 288 to 153 MiB, but only 190–231 MB available (J) | Rejected | D66; `stack.md` |
| Piper TTS | Not tested | Open RAM alternative | D68 |
| Decode pause at first phrase | First audio 0.73 vs 0.94 s p50, identical answers (J) | Current | D66 |

## Retrieval and answers

| Avenue | Outcome | Status | Ref |
| --- | --- | --- | --- |
| Stored frame in every recall prompt | 2B blended past and present ("the cat is still sleeping") | Rejected; captions instead | D25 |
| Recent captions in every prompt | Pulled the 2B to the previous scene | Rejected; past-tense gate | D27 |
| Retrieval into the brain ("one voice") | 34 vs 41/74, then 38 vs 44/74 (J) | Rejected twice; patch saved | D73, D75; `archive/one-voice.patch` |
| Sufficient-evidence diagnostic | 14/24 to 21/24 with perfect evidence (J) | Upper bound only | D87 |
| Floors from three direct questions | Supporting recall 12/18 to 5/18 (E) | Rejected | D98 |
| Calibrated floors 0.53 / 0.55 | Controlled 22/32 to 30/32; integrated recorded audio 42 to 39/47 (J) | Rejected for runtime | D100–D108 |
| Bounded evidence assembly (A/B contract) | Frozen, never built; the session moved to Granite | Open idea | D109, D110 |
| bge-small scoring bare labels vs questions | Does not work | Known limit | D73 |
| Continuous 1,800 s baseline | 10/48; older-memory, topic, and correction questions 0/24 (J) | Baseline for long conversation | D96 |
| Intent parsing (rules, BGE scores, linear head) | Never built. The 8 recorded misses (39/47, J) include no wrong past or present choice: `about_past()` fired on every past question. Combined questions still lack earlier evidence | Not the bottleneck for this set; reopen with routing misses | `recall.md` |
| Recall: earlier frame labeled as past (B) | Right frame delivered; 2B answers in present tense or about the image. 38/47, 10/15 (J) | Rejected | D150 |
| Recall: B plus a past-tense note (B-note) | 41/47, 11/15 (J); answers still wander ("the first thing I saw was...") | Rejected for B2 | D150 |
| Recall: RAM captions of retained frames, code answers (B2) | 41/47, 13/15, first audio 1.41 s p50 (J); combined question passes | Current | D150; `recall.md` |

## Voice

| Avenue | Outcome | Status | Ref |
| --- | --- | --- | --- |
| Moonshine Tiny / Small / Medium | Heard "Qdrant" as "current"; Small and Medium slower | Rejected | D22, D24 |
| Parakeet int8 on CPU | 0.8% WER, 0.22 s per line, 531 MB (J) | Current | D24 |
| Parakeet fp32 | 3,152 MB | Rejected | D24 |
| Flat 0.6–0.7 s hangover; minimum line length | Adds latency to every turn; shortest question is 0.67 s | Rejected; length-scaled hangover | D38 |
| Real voices with pauses | A pause splits a question; the turn merge is still open | Open | D36, D38 |
| Hey Edgy from transcript (arm A) | 7/9 synthetic wake lines, 0/9 false (J) | Current; arm B (openWakeWord) if it misses | D65, D73 |
| Spoken yes/no before voice deletions | Fixes deletion despite a correction ("Forget my phone? No..."); unit tests and dev fixtures (E) | Current | D162 |

## Perception, faces, and interface

| Avenue | Outcome | Status | Ref |
| --- | --- | --- | --- |
| YOLOE-26n vocabulary | Misses held phone and off-vocabulary objects | Fallback | D43, D146 |
| YOLOE-26s TensorRT | Phone movement 91.4%, Restore 91.5% (J) | Current | D146 |
| Track label voting and short-track merge | Off-majority labels 3 to 0 on the live clip | Current, frozen | D47, D56 |
| Crop descriptors: HSV, SigLIP 2, DINOv2-small | DINOv2 at 0.822: zero false matches on 2,025 distractors | DINOv2 current | D57, D64 |
| Three vs six object views | Phone 10/15 vs 11/15; six adds little | Three | D141; `bench/results/2026-10-10-d141-multiview.json` |
| Gallery growth: fixed, simulated voice confirmation, track harvest (teaching window) | 17 viewpoint videos, scoring half: 397, 435, 530 of 816 at 0.822; false matches 41, 179, 116 of 36,918, all lookalike instances (two Sony cameras, two mugs) (E). Admissions clean on contact sheets | Teaching window current | D154; `bench/results/2026-10-11-gallery-1791694947.json` |
| Unindexed payload filter on the things shard | `type` filter unindexed: things.score 10.7 ms p50 vs 1.65 ms indexed at 200 objects x 24 views (J) | Fixed: index every filtered field on open | D155; `bench/results/2026-10-11-edge-1791703351.jsonl` |
| Threshold 0.822 on lookalike instances | Fixed galleries match lookalikes up to 0.874 (E); no threshold is safe for lookalikes, and the real camera differs | Thresholds are UI settings | D154 |
| Changed cup viewpoints | 121/164 (73.8%) recognized (J) | Open gap | D145 |
| First-start camera readiness and retry | Old listening logs published readiness before the endpoint opened; a failed image stayed active. Endpoint probing and image-error reset pass 29 lifecycle checks and recover from three failed image requests without refresh (E). Live attachment passes without another viewer or robot restart (J) | Fixed | `bench/results/2026-10-11-first-start-video.json`; `research/mac-audio-interface.md` |
| Bounded object drawing through detector gaps | Existing state bridges at most 200 ms without action authority. Focus gaps fall from 111 to 102 of 675 development frames; 40 px/frame motion lag falls from 74 to zero, with unchanged small jitter (E). Full-model live stream receives 208 JPEGs, 172 ms source-age p95 (J) | Current; longer detector gaps remain | D159; `research/booth-ux.md` |
| Coordinate median, stock Kalman, gated Kalman | Lag 35–50 px, chair worse, motion rejected for 3 s (E) | Rejected | D147 |
| Lucas-Kanade box tracking | Features stick to background; 429 px lag (E) | Rejected | D147 |
| Missed face on the speech-start frame | Ended the conversation (lost history, told name, visitor id). Person-track continuity now carries it; unit tests only, live check pending | Current | D161 |
| Face delivery: four timer and cache prototypes | Failed 90% cadence or 200 ms hold | Rejected; completion-driven accepted | D139–D143 |
| Face embedders: EdgeFace-S, SFace, MaxSim alone, mean vector | False matches at 40 px or as the gallery grows | Rejected; w600k_r50 two-shot | D45 |
| Face blurring before storage | Each review found a new leak path | Rejected (Dylan); no frames in sightings | D53, D54 |
| Background masking of crops (YOLOE-26s masks, grey fill) | D145 cup video, Mac CPU: masked 241/360 vs box 263/360, zero false matches in both; masks correct, misses are viewpoint changes; the video has no background change (E) | Not adopted; background change untested | D148; `bench/results/2026-10-11-crop-arms-1791693406.json` |
| Compact UI and readable recall | Three-view carousels, sliders, simple auto-scroll, and the camera-first Qdrant theme pass desktop/mobile checks (E). Jetson fixture-image/oracle-text check passes recall thumbnails, settings, and deletion (J). Teaching statements link through object turns, not only point payloads | Current | D157, D158 |
| UI Ignore validated against the live track | Ignore failed with 409 within about 1 s of an item leaving view; the page rebuilt the list every poll | Replaced by held 30 s offers | D151 |
| Camera at 15 fps to lower preview grain | Four paired captures: noise 7.34 at 15 fps vs 6.29 at 30 fps, same brightness; our preview encode adds no noise (J) | Rejected; add light instead | `research/objects.md` |
| Hand detector or depth camera | Not tried; a reach can steal focus for about 3 s | Open | D67 |

## System and memory

| Finding | Value | Ref |
| --- | --- | --- |
| Edge query p99, 1,000 points | 0.47–0.49 ms (J), target 10 ms | D36 |
| Component RAM | bge 409, faces 297, DINOv2 172, YOLO 260, Parakeet 531, Kokoro 1,207 (640 MB CUDA kernels), llama 2B 1,921 MB (J) | D66, D68 |
| Headroom with all components active | 558 MiB minimum; paging in 36/48 recorded turns, cause unattributed (J) | Gemma full stack |
| Detection while speaking | 14.9 fps median, below 15 during synthesis (J) | D96, D143 |
| MAXN_SUPER | Decode 22.9 to 35.3 tok/s, prefill 941 to 1,455 tok/s (J) | D31 |

## Evaluation pitfalls

- A single-vote judge flipped 5 of 60 identical answers. The judge now votes three times and caches verdicts (D46).
- Keyword `correct` and judged scores differ a lot: D75 M2 is 62/74 keyword but 44/74 judged.
- The held-out set has been used three times: 15/26 (17/26 after Dylan's rulings), 18/26 with real voices, then 17/26 for both arms of D150. Count every use in DECISIONS.md.
- Synthetic voices overstate ASR quality. Real voices split at pauses (D36).
- The same video decodes to different pixels on the Mac and the Jetson. Verify pixels with the deployed decoder (D93).
- Small paired runs are noisy: llama-server answers differ on identical prompts. One question in 47 is about 2%.
- FileCamera still images keep their original timestamp, so recognition goes stale in replays (edge-cases.md).
- ONNX Runtime telemetry aborts pytest after the tests pass. `tools/gate.py` sets `ORT_DISABLE_TELEMETRY=1` (D89).

## Process pitfalls

- Six hours of evaluation preparation produced no deployed gain (D102). Build the runnable thing first, then measure.
- The D139–D147 box-display loop ran many prototypes; Dylan accepted the live result and stopped it. Ask what "good enough" means before a fifth prototype.
- The pre-commit checks read the working tree. Stage complete files; partially staged bookkeeping breaks the gate's index cleanup. Never bypass the hook.
- Do not stop a healthy job on a stale log line (D119). Check real progress counters first.
- Records grew until 19 of 30 commits were receipts (D149). Keep records lean.

## Machines

- **Jetson:** `ssh robot`, `/home/qdrant/qdrant-robot`, releases under `releases/`, data under `shared/`. GPU jobs take `shared/gpu.lock`. No `rg`; use `grep`. JetPack 7, TensorRT 10.16, OpenCV 5; no Torch or Ultralytics. Never run the course robot's hotspot setup over Wi-Fi.
- **WSL box:** `ssh dylan@192.168.1.74`, `/home/dylan/qdrant-robot-box`, `gpu.lock`. Preserve other owners' jobs and Docker or Ollama services. LiteRT GPU on WSL picks software Vulkan; use CPU there.
- **Mac:** shared `.venv` (Python 3.12); system Python 3.9 lacks modules. The preview needs the exact current release; a second MJPEG subscriber replaces the first.
- Edge stores are sparse files: use `rsync -aS`. The Jetson kernel lacks `/proc/PID/task/TID/children`; walk PPid in `/proc/*/stat`.
- `tools/jetson.py collect` copies all of `shared/results/` to `bench/results/`. Results before 2026-10-10 moved to `shared/results-archive-20261010/`.

## Where old material lives

- [research/archive/](archive/): earlier design briefs (M1–M3, v1, capability plan), model research, grounding, Gemma and TensorRT reports, the old experiment index, and the full historical lessons.
- Archive tags `archive/2026-10-10/*` keep every retired branch; [experiment-heads-20261010.json](archive/experiment-heads-20261010.json) lists them.
- Private media, voices, adapters, and raw logs stay gitignored under `build/` on the Mac and `shared/experiments/` on the Jetson.
