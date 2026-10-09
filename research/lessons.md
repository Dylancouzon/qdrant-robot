# Lessons: avenues explored and pitfalls (2026-10-08 to 2026-10-09)

The session log a new session reads after STATE.md: every avenue tried, its outcome, and where the evidence lives; then the pitfalls. Decisions are in DECISIONS.md (Dnn); evidence in bench/results/ and reviews/.

## Avenues explored

### Speech and latency
- Real-voice replay misaligned turns when a pause split a question: the replay now collects every turn per step and marks splits BAD (D38).
- Endpointing: a global longer hangover was rejected (adds latency to every turn); a length-scaled hangover (0.35 s, 0.7 s after 4 s of speech) removed long-question splits (D38). A turn merge for pauses after a short fragment was designed but not built (research/endpointing.md, reviews/20261008-100527-35955-design.md).
- TTS first phrase was slow because Kokoro shares the GPU with llama decode and the detector (0.16 s alone, 0.35 to 0.55 s in a turn); pausing decode at the first phrase and resuming with a prefill cut first audio from 1.61 to about 1.4 s p50 with audio (D66, D72; bench/first_phrase.py).
- Wake word "Hey Edgy" (Dylan kept the name; "Edgy" alone collides with "Qdrant Edge"): arm A, spotting in the Parakeet transcript, 7/9 synthetic wake lines and 0/9 background lines; arm B (openWakeWord) only if A fails on real voices (D65, D73, research/wakeword.md).

### Sight and objects
- 512 vs 256 image tokens: no gain beyond noise, scene-change turns up to 0.49 s slower: 256 kept (D39, research/sight.md). Detector labels in the sight prompt were the next arm, not run.
- Detector sightings in Edge (D43) answered by code (D48); the 2B ignored sighting lines given to it.
- Live camera: tracks fragment and labels flicker on real frames (D47); majority labels and short-track merging fixed most of it (D56); sightings store no frames (D54).
- Named objects: DINOv2-small crops as a MaxSim multivector won over an HSV histogram and SigLIP 2; zero false matches on held-out instances; matching across detector labels (D57, D64). Binding first used "exactly one candidate" (failed on backgrounds), then the focus object (D67).
- Focus object and booth screen: rule-based focus with scenery, held-object and teaching-zone cues; on the 90 s live clip one background focus (a reach toward a chair) and slightly too many switches; a hand class or depth camera deferred (D67, research/booth-ux.md).
- Video view: token-protected MJPEG from the robot process, labels only (D59), lag 0.1 s.

### People
- Face embedder bake-off on team photos: insightface w600k_r50 with a two-shot rule at 0.328, zero false identities on 4,113 strangers; the dev margin at 40 px is thin and robot-camera recalibration is open (D45, research/faces.md, research/m3-design.md).
- First M3 replay gave 6 false identities: identity was tied to the person track, and a stale cached frame was used; fix A (a fresh face match on the speech-start frame for every identity answer) reached 33/33 with zero false identities (D56).
- Told names and statements: answered only for the same visitor (face match or a 20 s conversation window), none after a restart, only first-person statements scoped (D49, D60, D68, D70); a name is not consent, the robot offers once (D69).
- Face blurring at write time was proposed after review rounds kept finding deletion paths; Dylan called it over-engineering; sightings without frames replaced it (D53 superseded by D54).

### The assistant and the brain
- Direction: an assistant first, retrieval feeds the brain, actions and identity in code (D61, research/assistant-design.md); the Fable v1 plan: always retrieve with per-shard minimum scores, actions by rules then a Qdrant intents shard then confirmation, no LLM classifier in v1 (D62, research/v1-plan.md). Jev (TypeSafe AI) and open versions were considered for the intent layer.
- Retrieval into the brain lost to code answers (m2 34 vs 41/74) (D73); a Mac bake-off of five brains x nine prompt shapes found the gap is mostly the evidence, not the brain; the 4B only matches code answers (D74, research/grounding.md).
- Evidence fixes (one line per memory, no sides, no duplicates, commands not stored as statements, instruction after the image) raised code answers to 44/74 (dev-only) and brought one voice to a tie (38 vs 39/74); the one-voice patch is saved (D75, research/one-voice.patch).
- Bigger brain: Qwen3-VL-4B leaves about 190 MB against the 500 MB floor; Kokoro's CPU memory is CUDA kernel code, not waste; routes left: Kokoro on CPU, fp16 Kokoro, Piper, a smaller 4B setup (D66, D68).
- Training (LoRA on the 3080 box) is open but not yet justified: the evidence was the bottleneck (D74).

### Process
- Review gate rules added today: overfitting (rule 6, D38), proportion and scope (rule 7, D55), v1 mode logs edge cases (rule 8, D71); breadth first (D40); edge cases in research/edge-cases.md.
- Judge noise: the single-vote judge flipped 5 of 60 identical answers; now three votes with a verdict cache (D46).
- Milestones: M1 met under D40 (reviews/20261008-111211-5165-milestone.md); M2 and M3 gates not yet run.

## Pitfalls

- Judge variance and llama-server variance: identical prompts can give different answers; compare paired runs, use the judge cache, and do not read a 1 to 3 step change as real.
- Mac llama.cpp is not the robot: the Mac Homebrew build matched the Jetson on 51/93; the 3080 box at the Jetson's commit with GGML_CUDA_NSM=8 matches 63/93 (D75). Rank brains on the box; accept on the Jetson.
- Real-time replays are slow (5 to 15 min each) and serialize on the Jetson GPU lock: iterate in text mode on the touched sessions, run the full audio set once.
- Review loops grow scope: each round found another edge case (privacy deletion paths, D53). Use rules 7 and 8: block only main-flow and fixed-outcome failures, log the rest.
- Overfitting traps: builders copied a dev question into a knowledge phrasing (removed, D38 era), printed held-out phrasings once (not tuned on), chose a rule with the whole live clip in view (both halves now labeled dev, D67). The M1 held-out set reuses a dev frame; bench/results holds held-out transcripts.
- Composite fixtures paste objects with no person: the focus never forms, so naming is untested in replays (live day).
- Stale frames: the brain's cached look can show an earlier visitor; identity and stored evidence must use the speech-start frame (D56, D72).
- Parallel builders share one working tree: commit only a task's files; a deploy ships everything in the tree, including another builder's uncommitted edits.
- In-process replay restarts grow swap (about 1 GB in long runs); a real restart is a new process; measure in the eight-hour run.
- Live sessions with Dylan: wait for "ready", send a snapshot with the zones first, cue every step to the end (memory: live-session-instructions).
- Tools: the Jetson's ffmpeg has no V4L2 input (record clips with OpenCV in the release venv); `grep` on the Mac is aliased to rtk (use /usr/bin/grep); codex exec needs stdin closed (tools/gate.py does it); the pre-commit hook's "no PASS review" reminder is approximate and never blocks.
- Private face data: eval/faces/ is gitignored; tools/jetson.py ships face scenes to shared/faces/<hash> per release (D52); only LFW images go to the Jetson for benches.

## Machines

- Robot: `ssh robot` (qdrant-robot.local, user qdrant). See STATE.md, Robot access.
- 3080 box: `ssh dylan@192.168.1.74` (key auth from the Mac; WSL2 Ubuntu 26.04, RTX 3080 10 GB, 16 cores, 25 GB RAM; no passwordless sudo). ~/qdrant-robot-box: cuda.sh (CUDA 13.2.86 in user space; system CUDA 12.6 fails with GCC 15), build.sh (uv venv with cmake and ninja, llama.cpp 9c2e0e4, orin.patch, sm_86, GGML_CUDA_NO_VMM=ON), llama-server-orin (sets GGML_CUDA_NSM=8, GGML_CUDA_CC=8.7), models/ (GGUFs checked against models.json). Ollama 0.35.1 with gemma4:12b and qwen3.5:9b is also installed: not for parity (different llama.cpp and packaging); possible later as a stronger judge or data generator. Run: `.venv/bin/python -m bench.brain_bakeoff --host dylan@192.168.1.74 <brain> <shape>`.
