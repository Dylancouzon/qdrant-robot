# Decisions

Append-only. Five lines or fewer per entry: date, decision, why, rejected alternatives, evidence.

## D1 2026-10-07: Reach the reachy-edge-memory capabilities on the Jetson alone
Why: the strongest "how does this run on Edge?" moment, and it extends a demo already shown on stage.
Rejected: Doodle Oracle, Impossible Museum, arm and plotter concepts (see `research/concepts.md`).
Evidence: `research/concepts.md`, `refs/reachy-edge-memory/README.md`.

## D2 2026-10-07: Same idea, our own architecture
Why: the reference runs every model on a laptop over HTTP; one 8 GB board needs a different design.
Rejected: porting the reference code file by file.

## D3 2026-10-07: Answer quality and speed come first; the LLM gets the most memory
Why: Dylan's priority. Order on conflict: good answers, then fast answers, then camera fps, then search latency.
Rejected: a large Wikipedia shard in the core build (it becomes add-on M5).

## D4 2026-10-07: No servos or arms; Jetson-driven peripherals only
Why: fragile to travel, and hardware would take attention from the software.
Rejected: SO-101 arm, pen plotter, Reachy Mini head, second robot.

## D5 2026-10-07: Off-the-shelf models first, train or distill only on a measured miss
Why: fastest path to a working loop; training is allowed but must be justified by a benchmark.

## D6 2026-10-07: Pin qdrant-edge-py 0.8.0; verify capabilities against its stubs
Why: Edge is beta and drifts. Fusion over prefetches works (tested on 0.7.2); `query_batch` and `Memory` are master-only.
Evidence: `research/qdrant-edge.md`.

## D7 2026-10-07: Reference revisions in refs/
`refs/reachy-edge-memory` at a3d8fbe (2026-10-02); `refs/qdrant-edge-memory-robot` at cfc0dd2 (2026-09-13).
Why: research and parity claims cite these exact versions. Re-clone with `gh repo clone`, then check out these SHAs.

## D8 2026-10-07: Harness verified by Codex gpt-6.1-sol (high) before the autonomous run
Applied: checkpoint rule while Git is unapproved, verdict-checking gate with timeout, per-milestone acceptance, handoff fields in STATE.md, eval and benchmark protocol, smaller M0.
Why: the first draft would have stalled after one task, and gates passed on any Codex exit.

## D9 2026-10-07: Autonomous, AI-led project; repo rules supersede the global CLAUDE.md
Dylan: standing approval to commit and push for the whole project; repo rules win on Git, sub-agents (Opus builders), and gates.
Why: the build runs without a human in the loop.

## D10 2026-10-07: Test by scripted sessions from the Mac; the Mac is the mic and speaker for now
Why: no human at the robot most of the time and no audio hardware on the Jetson. Synthetic speech plus recorded real voices; fixture images for sight.

## D11 2026-10-07: Second Codex gpt-6.1-sol harness review applied
Added: lead-only authority over STATE and DECISIONS, Mac-to-Jetson workflow, recovery rules, scored replay loop, dev vs final audio, counsel via `gate.py design --model gpt-6-astra`, argparse and SIGTERM-safe cleanup in gate.py. Skipped: process-level tests for gate.py (timeout and interruption paths), add if a gate ever hangs.
Correction to D10: the Jetson has a microphone (the camera's); only a speaker is missing.

## D12 2026-10-07: Qualify the stack before choosing models; TensorRT Edge-LLM first
Why: L4T R39.2 is new (rewritten kernel, past compatibility issues) and has no system CUDA or TensorRT. TensorRT Edge-LLM 0.11.0 ships aarch64 Python 3.12 wheels for Orin, JetPack 7.2, CUDA 13.2.
Rejected: a broad model sweep first; assuming jp6/cu126 wheels work here.

## D13 2026-10-07: Measure power and thermals before choosing a power mode
Why: only 15W and 7W profiles exist on this release; Super mode may need better cooling in the closed enclosure.

## D14 2026-10-07: Architecture rethink: one omni brain, event-driven perception, results-first harness
Why: Dylan rejected the testing-phase plan ("it will not fit"). Gemma 4 E2B omni first, Moonshine plus Qwen3-VL-2B fallback; YOLO26n plus ByteTrack; YuNet plus a small face embedder; pooled SigLIP 2 and bge-small; bounded scheduling. A hypothesis the build may replace.
Rejected: eight separate models with their own runtimes; a 15 fps continuous pipeline; patch multivectors before a measured need. Evidence: Astra counsel and two researchers (research/models.md).

## D15 2026-10-07: Gates are enforced by a commit hook, not by instructions (superseded by D17)
Why: Dylan asked how gates are enforced; instructions alone can be skipped. The hook binds a PASS review to the exact code tree and runs deterministic checks; `spike/*` branches stay free for exploration; design briefs need two alternatives.

## D16 2026-10-07: Milestones are working robots with results targets
M1 It talks, M2 It remembers, M3 It knows you, M4 Booth-ready, M5 Wikipedia add-on. Interim numbers from Astra counsel. M1 starts with a vertical slice and a 20-turn decision run, not a benchmark phase.

## D17 2026-10-07: Light safety net replaces strict enforcement (supersedes D15)
Dylan: "Don't go overboard enforcing. Most agents do okay at calling gates, so just an extra layer." The pre-commit hook blocks only failing deterministic checks and reminds about missing reviews.
Rejected: review-to-tree binding that blocks commits, a Claude command guard, a CI audit (each slowed work; the guard also blocked harmless commands).
Owner decision: replaces design verdict reviews/20261007-225624-88242-design.md (RETHINK). Accepted gap: checks read the working tree, so stage everything you commit.

## D18 2026-10-07: Keep the clock keeper, stop only the course robot
Why: `memory-robot-clock.service` restores the time after a power cut (the booth may be offline), and memory timestamps depend on it. It uses under 2 MB.
Rejected: disabling it with `l6-robot.service` as M1.1 first planned. Evidence: `shared/legacy/` on the robot.

## D19 2026-10-07: Bake off brains on llama.cpp first; TensorRT Edge-LLM later
Why: Edge-LLM INT4 quantization needs an x86 host with an NVIDIA GPU (new spending); llama.cpp builds on the Jetson and uses ready-made GGUF quantizations for every candidate (Gemma 4 E2B with audio, Qwen3-VL-2B, Qwen3.5-2B).
Rejected for now: Edge-LLM FP16 (nearly fills RAM). Revisit if decode speed misses its target. Evidence: researcher report in this session, research/stack.md.

## D20 2026-10-07: Disable services the robot never uses
Disabled: docker, containerd, snapd, fwupd (masked), ModemManager, nvargus-daemon (CSI cameras only), kerneloops, bluetooth. About 300 MB RSS freed for models. Kept: avahi (`qdrant-robot.local`), NetworkManager, ssh, the clock keeper.
Revert with `sudo systemctl enable --now <unit>`.

## D21 2026-10-08: Retrieval in code every turn; no model tool calls
Why: with a `remember` tool, Qwen3-VL-2B and Qwen3.5-2B called it on 10 and 12 of 13 current-sight questions, and Gemma 4 E2B text called it on 1 of 4 memory questions. With retrieval in code and memories in context: Qwen3-VL-2B 20/21, Qwen3.5-2B 18/21, Gemma 4 E2B 14/21 (audio and text).
Rejected: model-driven tool routing (fragile at 2B, and a second decode pass). Evidence: bench/results/2026-10-08-brain-*.jsonl.

## D22 2026-10-08: Brain candidate: Moonshine Tiny Streaming plus Qwen3-VL-2B on llama.cpp
Why: best dev score (20/21), first token 0.80 s cold and 0.10 s with a cached system-plus-image prefix, 22.4 tok/s, about 1.6 GB. Moonshine Tiny: 4.3% WER on synthetic voices, 0.46 s p50 from end of speech to final line, on the CPU.
Rejected for now: Gemma 4 E2B omni (14/21, 3.5 GB; audio works on Orin); Moonshine Small and Medium (0.84 s and 0.97 s). Revisit ASR with real voices. Evidence: bench/results/2026-10-08-{brain,asr}-*.jsonl.

## D23 2026-10-08: M1.1 review findings rejected with evidence (reviews/20261008-003940-85037-review.md)
Finding 2 (tegrastats survives a stop): systemd stops the whole unit cgroup. Test: `qr-stoptest` had 2 matching processes running, 0 after `systemctl stop`.
Finding 4 (release hash includes untracked work): CLAUDE.md defines a release as a hash of the shipped source including untracked files; each result now records `release`, and that release directory keeps the exact tree and ENV.txt. Fixed: findings 1 (renamed to tools/jetson.py), 3 (verified .part download), and the optional one (release resolved once).

## D24 2026-10-08: Speech in is Silero VAD plus Parakeet TDT 0.6B v2 int8 on the CPU; Moonshine removed
Why: Moonshine Tiny heard "Qdrant" as "current" or "grant" and broke retrieval (4.3% WER, synthetic voices). Parakeet: 0.8% WER, 0.22 s p50 per line on the CPU (same as GPU int8, no contention with the brain's prefill), 1,050 MB. Silero VAD with a 0.35 s hangover ends lines at 0.34 s p50; the transcript is ready 0.61 s p50 after the end of speech.
Rejected: Parakeet fp32 (3,152 MB); Moonshine with `skip_transcription` (lines ended later, 0.73 s, and split a monologue); Moonshine Small and Medium. Evidence: bench/results/2026-10-08-{asr,final-asr}-*.jsonl.

## D25 2026-10-08: Recall shows the brain captions of stored frames, not the frames (rejects finding 1 of reviews/20261008-014219-36859-review.md)
Each stored frame gets a one-sentence caption written by the VLM from that frame alone (not from the answer), with the frame id and JPEG kept as evidence; turns log the recalled frame ids, and replays score them (`evidence`). With the stored frame always in the prompt, the 2B brain blended past and present (replay 1791435375: "the cat is still sleeping") and every turn paid a second image prefill. Captions: all recall turns pass.
Kept for M2: showing a specific stored frame again ("look again") once semantic recall picks which frame.

## D26 2026-10-08: D24 speech in is provisional; 4B stays a candidate
Design verdict reviews/20261008-014824-42570-design.md (GO WITH CHANGES): confirm D24 with real recorded voices (names, pauses, booth noise) before M1 acceptance; choose between Qwen3-VL-2B and 4B only on an expanded, judged dev set with complete-turn latency. Smart Turn waits for a measured endpointing need.

## D27 2026-10-08: Qwen3-VL-2B stays the brain; memories only for past questions; facts spoken verbatim
Decision run, 39 judged turns (eval/judge.py, gpt-6-luna): Qwen3-VL-2B 32/39 and 1.81 s first audio p50; Qwen3-VL-4B 29/39 and 2.30 s; Qwen3.5-2B 24/39 and 2.55 s (its recurrent layers defeat prefix caching: first token 1.63 s); Qwen3.5-4B was killed by the kernel OOM killer at load (llama-server 4.6 GB anon RSS, 02:54).
Failures traced to stale context: the frame and its caption were right, but recent captions in every prompt pulled the 2B to the previous scene. Now a past-tense check gates memories, and a question matching a fact's phrasings at 0.93 or above gets the fact itself (no LLM). Evidence: bench/results/2026-10-08-replay-179144{1045,1452,1926,3048}.judged.jsonl.

## D28 2026-10-08: Memory limits for every component (M1.3 decision run passes)
llama-server `--cache-ram 0 -c 2048 -ub 256`; Kokoro's CUDA arena shrinks after each run; bge's arena grows by request; Parakeet without CPU arena or weight prepacking (+90 ms per line, -340 MB). Available memory with every M1 component loaded and exercised rose from 460 MB to 2,016 MB; a 39-turn replay kept 1,886 MB minimum headroom with no swap growth (55 MB flat).
Decision run on dev (39 judged turns, gpt-6-sol): 35/39, first synthesized audio 1.77 s p50, 2.50 s max. Evidence: bench/results/2026-10-08-memory-*.jsonl, bench/results/2026-10-08-replay-1791448115.judged.jsonl, bench/results/replay-20261008-041949.tegrastats.

## D29 2026-10-08: Held-out baseline is 15/26; tune only on new dev cases
Held-out set (eval/heldout/sessions.jsonl, frozen 05:40, first use) with Qwen3-VL-2B: 15/26 judged (58%) against 35-36/39 on dev; first synthesized audio 1.70 s p50, 2,086 MB minimum headroom, no swap. Causes: ASR on unfamiliar voices (one voice turned "What's that I'm holding?" into "What's the time all day?"), recall answers that ignore a present memory, weak small talk. Failure modes get new dev cases; the held-out set is only re-run for acceptance, and each use is counted here.
Gemma 4 E2B on the final pipeline (with `--swa-full -lzm on`, 1,144 MB headroom): 26/39 dev: natural talk, weak sight (a stop sign called a rack). Evidence: bench/results/2026-10-08-replay-179145{3212,3543}.judged.jsonl.

## D30 2026-10-08: Counsel applied; context by question kind; hybrid perception next
Counsel (reviews/20261008-072616-91017-design.md, gpt-6-astra): captions now come from the frame alone (they had inherited the conversation, contrary to D25); code-path recall declines questions narrowed by time, place, or comparison; the sentence cap no longer exempts questions or exclamations; a nearest-neighbour router (robot/route.py, bge) withholds the image from small talk and knowledge turns. Dev stays at 40/47 (bench/results/2026-10-08-replay-1791459784.judged.jsonl): greetings fixed, other failures moved.
Next, per Dylan: object memory from a detector (YOLO26n or YOLOE prompt-free, spike/detector builder) with exact regions, and SigLIP 2 crop vectors labelled by vector search in Edge; the VLM keeps open sight questions and gets detections as grounding. Rejected for now: more prompt variants (plateau), Gemma 3 4B (out of memory), LFM2-VL-3B and MiniCPM-V 4 (image tiling overflows the 2,048-token context).

## D31 2026-10-08: Robot runs in MAXN_SUPER (bootloader switched on the device)
With Dylan present: set COMPATIBLE_SPEC and TNSPEC to `jetson-orin-nano-devkit-super-` in /etc/nv_boot_control.conf, `dpkg-reconfigure nvidia-l4t-bootloader` (needs fwupd: unmasked for the run, masked again) staged NVIDIA's TEGRA_BL_3767_super.Cap (verified byte-identical), reboot applied it to bootloader slot B; /etc/nvpmodel.conf now links nvpmodel_p3767_0003_super.conf; `nvpmodel -m 2`. GPU 1,020 MHz, EMC 3,199 MHz, CPU 1,728 MHz. Qwen3-VL-2B: prefill 941 to 1,455 tok/s, decode 22.9 to 35.3 tok/s. Backups: backups/robot-20261008 (Mac), shared/legacy/nv_boot_control.conf.pre-super.
Rejected: the QSPI-only flash from an x86 host (no host was available; now Dylan's 3080 machine could serve as recovery).

## D32 2026-10-08: MAXN_SUPER evidence, and a camera fault on the USB hub
Evidence for D31: bench/results/2026-10-08-llama-bench-maxn-super.jsonl (Qwen3-VL-2B 36.0 tok/s decode, 1,492 tok/s prefill; 4B 17.5 and 658), each row records the power mode. The detector builder measured 66.3 °C peak with detection at 15 fps and LLM decoding (spike/detector research/detector.md).
About 7 minutes after the Super reboot the hub disabled the camera's port ("usb 1-2-port2: disabled by hub (EMI?)"); the camera re-enumerated and now fails VIDIOC_STREAMON (protocol error) even after a software port reset. Asked Dylan to replug it; if it recurs only in MAXN_SUPER, test the 25W mode.

## D33 2026-10-08: Dylan's rulings on three judged answers (human adjudication, not tuning)
Held-out "sunny with clear blue skies" (no snow): correct, less precise. Held-out "chicken, rice, and vegetables" (not "stir fry"): correct. Dev "stuffed animals" for teddy bears: acceptable but imprecise; a follow-up question would help. The three rubrics now say so (eval/heldout and eval/dev sessions); held-out baseline 15/26 becomes 17/26 under the rulings (D29). Precision of object names should come from detector labels (spike/detector).

## D34 2026-10-08: Review findings on the hygiene task, two rejected (reviews/20261008-091638-89292-review.md)
Finding 1 (design gate for bench/edge_bench.py): CLAUDE.md reserves the design gate for architectural decisions, not reversible small steps; a 70-line benchmark script is one. The review prompt (gates/review.md, rule 5) now says so: a benchmark or tool script needs no design verdict, a runtime module under robot/ does. Finding 3 (results path): on the Jetson `SHARED/results` is the protocol path that `tools/jetson.py collect` copies into `bench/results/`, the same as every other bench script; the Mac run was a smoke test, and the evidence is the collected Jetson run. Fixed: knowledge queries now embed the facts' own phrasings (finding 2); tegrastats starts inside the GPU lock (finding 4). Skipped: batched setup writes (optional; setup is under a minute).

## D35 2026-10-08: Qwen3-VL-2B stays after a 4B re-run on the fixed pipeline in MAXN_SUPER
Qwen3-VL-4B on the current dev set (47 turns, synthetic voices, release 1eeeff18de9b): 37/47 judged, first synthesized audio 1.91 s p50, 3.32 s max; the 2B on the same set: 41/47, 1.47 s p50 (STATE, 1791463902). Two 4B failures came from caption lag: its slower captioning left the previous frame uncaptioned when the next question arrived, so the code path found no memory.
Rejected: the 4B as the brain (D27 stands). Evidence: bench/results/2026-10-08-replay-1791465923.judged.jsonl.

## D36 2026-10-08: Real voices split at pauses; the replay then misattributes turns (first real-voice dev run, 29/47)
Dev replay with Dylan's recordings (bench/results/2026-10-08-replay-1791466459.judged.jsonl): 29/47 judged, but from knowledge-more-2 on, 16 turns heard the previous step's question. Cause: a pause inside a question ends the line at the 0.35 s VAD hangover (knowledge-more-2 on the Mac: lines of 0.74 s and 2.51 s), and eval/replay.py takes "the next finished turn" per step, so every later step shifts by one. The recordings themselves are right: tools/record.py --check transcribes them on the Mac (dev 47/47, held-out 25/26; ho-told-2 is a British-spelling transcript of the right line).
Next: the replay drains all turns a step produced and marks a split step BAD (harness), then endpointing for real voices (D26): a longer hangover or a minimum line, measured on first-audio latency. Also robot/asr.py normalize misses "Quadranth" (knowledge-1). The Edge query target is met: bench/edge_bench.py on the Jetson, 1,000 points, 1,000 queries per kind, p99 0.48 ms (recency), 0.49 ms (statements), 0.47 ms (knowledge MaxSim) against 10 ms (bench/results/2026-10-08-edge-1791466562.jsonl).

## D37 2026-10-08: M2 design gate GO WITH CHANGES: sightings with labels first, embeddings only after a miss
Verdict reviews/20261008-100431-34165-design.md on research/m2-design.md. Build order: acceptance fixtures (M2.0), then detector sightings (label, region, times, source frame) in the existing memory flow, then naming, forgetting, and ignoring parsed in code with an ambiguity policy (a name binds to a confirmed track or the robot asks). Separate persistent rules for a named instance ("forget my phone") and a class ("ignore the chair"); both survive restart. Dylan's named-object multivector (several crops, MaxSim) stays as the showcase; a crop embedder (SigLIP 2 or DINOv2-small) and RRF recall come only when label, region, and time filtering miss on same-class fixtures.
Rejected for now: both embedders at once, routine crop multivectors, recency as a fused semantic signal (it ranks within the asked time window).

## D38 2026-10-08: Length-scaled hangover; replay scores split steps; overfitting rule in the review gate
Hangover 0.35 s, 0.7 s after 4 s of speech; line limit 25 s (design verdict reviews/20261008-100527-35955-design.md). Real-voice dev 42/47, 1 split (a 1.34 s pause after "Where is": needs the turn merge), first audio p50 1.45 s, unchanged; held-out real voices (use 2 of D29) 18/26, 0 splits, 1.58 s p50 (bench/results/2026-10-08-replay-{1791468888,1791470020}.judged.jsonl). Past-question note and question-free sentence cap held on one-time probes, 22/23 (eval/probes, 2026-10-08-replay-1791469690).
Rejected: a flat 0.6-0.7 s hangover (adds its length to every turn); a minimum line (the shortest real question is 0.67 s); scoring a step after a 60 s turn timeout (a late turn would be scored as the next step: a hung turn aborts the run, reviews/20261008-103420-65213-review.md).
Rule 6 of gates/review.md (Dylan): a fix needs evidence beyond the dev steps it flips. Known leaks: M1 held-out reuses dev frame live/closet-night.jpg; bench/results holds held-out transcripts.

## D39 2026-10-08: Image tokens stay at 256; detector labels are the next sight arm
Bake-off (research/sight.md, design verdict reviews/20261008-103635-68464-design.md), oracle, 256 vs 512 image tokens (spike/sight-512 at 53e9cca): dev 40/47 vs 40/47; easy probes 9/10 vs 8/10; cluttered probes 5/10 vs 7/10; first audio p50 dev 1.26 vs 1.28 s, scene-change probes 1.43/1.44 vs 1.92/1.61 s. The gain is within noise at n=10 and scene-change turns pay up to 0.49 s: rejected under the decision rule. A wider JPEG at 256 tokens changes nothing (the token cap sets the resolution; fixtures are 640 or 960 wide).
Evidence: bench/results/2026-10-08-replay-{1791470691,1791471099,1791471234} (256) and {1791471465,1791471347,1791471882} (512). Next: frame-matched detector labels after M2.1 brings the detector into the runtime.

## D40 2026-10-08: Breadth first: every feature end to end, then tune (Dylan)
Dylan: carry known gaps, build a system with all features, then tune where measurements show headroom. A milestone now closes when its features work end to end on the Jetson with scored replays and measured numbers; accuracy and latency targets that miss stay listed as unmet in STATE.md and move to a tuning phase after M3. Deferred to tuning: a fresh, larger held-out set with other people's voices, the turn merge for long pauses, detector labels for sight, prompt work for told statements. Kept: review rule 6 and one-time probes (cheap), held-out frozen and counted.
Why: headroom (RAM, GPU contention, latency) is only measurable with every component running. Rejected: polishing M1 accuracy to 90% before M2 and M3.

## D41 2026-10-08: M3 design GO WITH CHANGES: permissive embedders, calibrated claim score, full deletion
Verdict reviews/20261008-115538-54937-design.md on research/m3-design.md. Bake-off SFace (Apache 2.0) vs HSFace (MIT) after YuNet (MIT) on new person tracks; claim score MaxSim vs pooled mean vector vs two-shot support, threshold from our own impostor maxima (never the reference 0.35); "forget me" also deletes the person's frames, crops, and captions. Identity answered in code; no greetings, continuous embedding, or brain identity path.
Rejected: insightface and Hugging Face EdgeFace weights (non-commercial, research/faces.md); a commercial license (new spending: Dylan's call if the permissive pair misses).

## D42 2026-10-08: Face model licenses are not a constraint (Dylan); embedder bake-off on accuracy and cost
Dylan: an internal demo, nothing distributed, any model may be used. The M3 embedder bake-off becomes EdgeFace-S (IJB-C TAR@1e-4 95.63, 306M FLOPs) vs insightface w600k_r50 (97.12, R50), with SFace as the light fallback; SCRFD may replace YuNet if it detects small faces better. The rest of D41 stands (calibrated claim score, full deletion, identity in code). Held-out faces: colleagues' photos and video frames (consent given for video content), kept in eval/faces/ outside git.

## D43 2026-10-08: M2.1 detector sightings land; answers from sightings carried (0/8 unseen probes)
YOLOE-26n booth vocabulary in the robot process at 14.7 fps; one Edge point per track (label, region, first and last seen, frame); gone sightings in Memories for past questions; detector failures reload three times then stop the robot. Review PASS reviews/20261008-121043-71318-review.md. Dev M2 32/74, evidence 19/21 (bench/results/2026-10-08-replay-1791475673); unseen probes 0/8, evidence 3/5 (1791474901): the detector misses objects outside its vocabulary or at low score (orange 0.10, flower pot, books), and the 2B ignores correct sighting lines. Decode 28.2 vs 30.4 tok/s with the detector (carried, D40).
Next: answer sighting questions in code (D37), then naming, forgetting, ignoring. Rejected: prompt wording for sighting lines (the 2B ignores them; rule 6).

## D44 2026-10-08: Two builders at once when files and the Jetson are disjoint (Dylan)
Dylan approved an M3 builder in parallel with the M2.2a builder, "maybe not for concurrent load". Rule: parallel builders own disjoint paths; only one uses the Jetson at a time (M3.1 is Mac-only: face accuracy does not depend on the board; its Jetson latency check waits for M2.2a). Supersedes "one builder at a time" in CLAUDE.md for this case.

## D45 2026-10-08: Face embedder insightface w600k_r50 with two-shot support (M3.1)
Bake-off on team photos (11 people, gitignored eval/faces) and LFW strangers, Mac: w600k_r50 with a claim needing two enrolled shots at 0.328 is the only pair with zero false matches at 20 and 50 identities for full, 80, and 40 px faces; held-out (use 2, after a rule bug in use 1) 15/15 recognized, 0 false identities on 4,113 strangers, highest impostor 0.257 (bench/results/2026-10-08-faces-*-17914{79900,80133,80344,80453}.jsonl; reviews/20261008-132825-68060-review.md).
Carried: the dev margin is 0.011 (impostor 0.317 at 40 px, 50 identities), strangers are press photos, and only 5 held-out probes are from a different session than enrollment: recalibrate the threshold on robot-camera frames before runtime use (M3.2). Rejected: EdgeFace-S (5 false matches at 40 px, 50 identities with two-shot), SFace (false matches at 40 px), MaxSim alone and mean vectors (false matches as the gallery grows).

## D46 2026-10-08: The judge votes three times and caches verdicts; a live soak script
The single-vote judge flipped 5 of 60 identical answers between two dev M2 runs (bench/results/2026-10-08-replay-{1791479044,1791480601}.judged.jsonl), enough to hide changes of a few steps. eval/judge.py now gives each new answer a majority of three passes and caches verdicts in bench/judge-cache.jsonl by a hash of judge model, prompt, rubric, transcript, and answer, so unchanged answers keep their verdict. Judged results before this entry are single-vote. bench/soak.py runs the robot on the live camera without speech and logs detection fps, points, peak RSS, and swap per minute. Reviews: reviews/20261008-134424-94848-review.md.
Rejected: temperature or seed control (codex exec exposes neither); keyword scores alone (they miss meaning).

## D47 2026-10-08: Live camera findings: soak is stable; real frames fragment tracks and flicker labels
30-minute live soak (bench/soak.py, release 31af40fe7e39, no speech, Dylan in and out of frame): detection 15.0 fps every minute, RSS flat at 2,848 MB, swap flat at 66 MB, peak tj 59.3 C, clean exit; 185 sighting points (bench/results/2026-10-08-soak-1791481186.jsonl). Closes the M1 30-minute check without speech. A 90-second clip of Dylan handling items (bench/clip_sightings.py; 2026-10-08-clip-1791483850.jsonl): 52 tracks, 11 with more than one label (cup, wallet, plush toy on one item; phone and camera; chair and person), and one lanyard, badge, or watch split into two or three tracks within seconds. The photo fixtures cannot show either.
Next in M2: a majority label per track, merging a short track into a neighbor of the same label and side, and a bound on stored sightings.

## D48 2026-10-08: M2.2a sighting questions answered in code
"What was on your left?", "what is gone?", "is the clock still there?", "where is X?" are parsed in code (regions, gone words, past or still markers, detector-vocabulary labels with synonyms, "it" from the last exchange) and answered from sightings by track, past-only for past questions, with a whole-frame check before "I do not see it now"; no match or a failed detector falls back to the brain with captions. One-time probes m2b 8/9 (before the review fixes) and m2c 7/8 (after: bench/results/2026-10-08-replay-1791484406); dev M2 37/74 three-vote, evidence 18/21 (1791483822). Review PASS reviews/20261008-143544-52597-review.md; a design-verdict finding rejected: D37 and reviews/20261008-100431-34165-design.md gate this approach.
Carried: "used to" and similar past phrasings; one object yields several labels; question-step evidence expects the turn frame.

## D49 2026-10-08: A told name answers only for the same visitor
A name or fact a visitor said answers "What's my name?" only while the same person track has stayed in view since it was said, or after a face match (robot/people.py identify); a new person track never inherits it, and the robot says it does not think they have met. With no person tracked (photo replays), the conversation answers as before. Why: without this, visitor B is told visitor A's name, a false identity (M3: zero false identities). "Forget me" deletes the person point, every linked evidence id, and pending writes; success is spoken only after deletion.

## D50 2026-10-08: M3.2 people memory module (not yet wired)
robot/people.py: one Edge point per person (id from the name), up to five shots as a MaxSim multivector, enrollment needs consent and two frames, identify applies the two-shot rule at 0.328 in code after an Edge MaxSim prefilter, link() records every evidence id seen with the person and forget() returns them all (verified after reopen), answers are spoken only after their action succeeds. Mac dev through Edge equals the bake-off (20/20, 0 false on 5,479 strangers); Jetson face step 20.3 ms ORT CUDA (546 MB with its CUDA context) vs 10.9 ms TensorRT FP16 (953 MB): CUDA, since it runs only on new person tracks (bench/results/2026-10-08-people-*-1791485150.jsonl). Reviews end with PASS reviews/20261008-145052-72503-review.md. Carried: prune links when retention deletes evidence; threshold recalibration on robot-camera frames (D45).

## D51 2026-10-08: Retention is a booth-day window plus a hard cap, never a per-kind cap
Design gate GO WITH CHANGES (reviews/20261008-151809-4769-design.md): sightings, turn frames, captions, and statements are kept for the booth day, with one hard total cap on points and frame disk as a safety net (oldest out of view first, enforced exactly); active tracks and evidence linked to a consenting person or a named object are never evicted; eviction removes the point and its frame file only when nothing else references it. Rejected: 3 sightings per label and region (an hour-old cup disappears after three newer cup tracks; D47 shows real tracks fragment). Measure: an hour-old cup among repeats, an eight-hour soak (points, disk, RAM, 1,000-query p99), restart, complete "forget me".

## D52 2026-10-08: M3 replay fixtures; private face scenes ship per content hash
eval/dev/m3.jsonl (7 sessions, 33 spoken steps) and eval/heldout/m3.jsonl (5, 23): consent and enrollment, returning visitor, look-alike stranger, new visitor replacing the last, told name, consent refused, forget, restart. Scenes are team photos (D42) composited on our camera background by eval/make_faces.py into gitignored eval/faces/scenes; tools/jetson.py ships them to shared/faces/<hash> and links them per release, and the release ID covers them (reviews/20261008-155622-53783-review.md). Held-out m3 composites were scored once on the Mac by robot/people.py while the fixtures were built (15/15 enrolled recognized, 7/7 strangers no match): counted as a held-out look; nothing tuned after.

## D53 2026-10-08: Faces are blurred before any frame is stored
Design gate GO WITH CHANGES (reviews/20261008-165546-31577-design.md) after three review rounds found new paths where a forgotten visitor's face could stay on disk (reviews/20261008-164504-13567-review.md, 20261008-165455-29875-review.md). Memory.save() is the one write boundary: it blurs YuNet faces and the head region of every person box, and skips the write if the check fails; enrollment keeps vectors only; captions come from the blurred frame. "Forget me" then deletes the person point, links, statements, linked captions, and pending writes. The live frame stays unblurred in RAM for the current answer.
Rejected: (A) linking and chasing every frame of a person across tracks (each review found a new path); (C) no stored frames (loses image evidence for recall).

## D54 2026-10-08: No face blurring (Dylan); sightings store no frames instead (supersedes D53)
Dylan: blurring is over-engineering for now (breadth first, D40). Simpler: sightings keep label, region, and times only (answers never used their frames), which removes most incidental images and the face-to-sighting link code. "Forget me" deletes the person point, linked turns (frames, captions, statements), and pending writes. Carried gap: a turn frame showing a person who was not identified in it stays until 12 h retention evicts it.

## D55 2026-10-08: A proportion and scope rule in every gate; audit cuts (Dylan)
Dylan asked for an over-engineering, scope, and over-focus check. gates/review.md rule 7, gates/design.md item 5, gates/milestone.md item 3: FIX machinery out of proportion to its problem, work beyond the task brief or milestone, and polish of one capability while others are missing (D40); prefer deleting the source; carry residual risk; proportion never waives consent, zero false identities, or real deletion; acceptance checks are frozen per task. Counsel audit reviews/20261008-165842-36020-design.md (RETHINK only for lacking alternatives, an audit): delete the told-name and no-face flags (keep the safe answers), no enrollment images, ordinary linked turns expire with retention (only enrollment and named-object evidence is protected), freeze tracker merge tuning, stop privacy-mechanism expansion and fixture growth beyond acceptance checks. Next: one integrated visitor script on the Jetson, then M2.2b and M2.3, then offline start and physical audio.

## D56 2026-10-08: M2.2c track stability, D51 retention, and M3.3 people wiring land
Review PASS reviews/20261008-174119-95289-review.md. Tracker: majority label per track, short-track merge (frozen). Memory: 12 h window and hard caps, sightings without frames (D54), orphan frames removed at open. People in the robot: identity answers from a face step on the speech-start frame with the two-shot rule (fix A, reviews/20261008-161702-78890-design.md), consent with two matching faces, vectors only, forget deletes the person and linked turns, a RAM guard after forget, no face gives a fixed answer, a told name gives "not sure" (Dylan's rulings pending). Evidence: M3 dev 32/33 with zero false identities (bench/results/2026-10-08-replay-1791494672); M2 dev 30/74 with evidence 18/21 (1791495446; brain and judge variance vs 35/74); live clip held-out half 23 -> 18 tracks, off-majority labels 3 -> 0. Carried: unidentified turn frames until retention; m2-restart-name-2 and intro-3 fail under the no-face answer until Dylan rules; llama-server answers differ on identical prompts.

## D57 2026-10-08: M2.2b named objects: cheapest descriptor first, separate shard
Design gate GO WITH CHANGES (reviews/20261008-174532-2635-design.md): bake-off HSV histogram floor vs SigLIP 2 base vs DINOv2-small on real multi-view objects plus real separate phones and teddy bears (Objectron lacks them), threshold set on half the instances at zero false matches; a name binds to one confirmed track (the sighting carries its box), three crop vectors in one MaxSim point in a separate named-object shard; ask when ambiguous; "forget my X" also removes the naming turn's evidence; ignore rules persist and filter every recall path, captions included.

## D58 2026-10-08: Integrated visitor baseline (one continuous dev session)
eval/dev/visitor.jsonl, 21 steps, no reset, one restart (review PASS reviews/20261008-175613-19815-review.md). Oracle 17/21, audio 14/21 (bench/results/2026-10-08-replay-{1791496173,1791496489}): faces 9/9 with zero false identities in both; sight, objects, and knowledge carry the misses; audio adds "Qdrant hatch" for "Qdrant Edge" and splits after a short opener. First audio p50/p95 1.61/2.74 s with audio; tracking 14.9 fps; minimum headroom 1,260 MB with every component active; memory folder about 4 MB per visit. Frozen as the integration baseline; two rubric and scene limits carried, not fixed after the results.

## D59 2026-10-08: Video view is MJPEG from the robot process, token-protected, labels only
Design gate GO WITH CHANGES (reviews/20261008-175709-21402-design.md): robot/view.py serves a capped MJPEG stream (stdlib http.server) of the newest frame with the boxes and labels of tracks in view on that frame; a token is required and it binds to localhost by default (live visitor video must not be open to the booth network); no person names in the first version; it never writes frames. Rejected for now: a separate viewer process over shared memory, WebRTC.

## D60 2026-10-08: Dylan's rulings on identity answers without a face match
Dylan: never answer "I can't see your face". With no matching face, identity questions answer from the live conversation: a name the visitor told in this conversation answers "What's my name?"; otherwise the robot says it does not think they have met and asks their name. The told name is dropped when a different face appears (a face vector of the speaker held in RAM only for that comparison, never on disk; Dylan: "idk, does it matter?", lead's choice). A name told before a restart belongs to no live conversation: without an enrolled face match the robot says it does not think they have met (fixture m2-restart-name-2 changes meaning; reported, not edited silently). Enrolled faces answer by face match as before (D45, fix A).

## D61 2026-10-08: The robot is an assistant; retrieval feeds the brain; actions and identity stay in code (Dylan)
Dylan: a conversational assistant first, vector search central including what the robot sees, people name objects ("Dylan's phone", as in refs/qdrant-edge-memory-robot), no left or right logic, open conversation, longer answers, a minimum retrieval score, v1 then headroom then a bigger brain or training. Design gate GO WITH CHANGES (reviews/20261008-190813-295-design.md, research/assistant-design.md): ordinary answers come from the brain with a few short source-labeled evidence lines from Qdrant Edge, each shard filtered by a minimum score calibrated on relevant and irrelevant questions including absent memories; identity claims, consent, forgetting, and ignore stay deterministic in code; actions routed first by the bge router with slot and ambiguity rules (a brain-as-classifier, Jev-style, only if the router misses unseen phrasings); teaching confirms the focus object (largest stable central track) before saving; the new answer path is compared with today's code answers on the same replay and one-time paraphrases before the code answer paths are deleted; answers grow toward 200 tokens after a speech-timing check. Left and right fixtures and logic are dropped.

## D62 2026-10-08: v1 plan after the Fable review; push the robot further (Dylan)
Adopted (Fable review, 2026-10-08, saved in full in research/v1-plan.md): always retrieve, per-shard calibrated minimum scores are the gate; actions: rules first (negation, slots), one Qdrant Edge intents shard second (replaces robot/route.py, same mechanism), a confirmation question in the uncertain band, no LLM classifier in v1 (one llama-server slot: a classification prompt evicts the prefilled frame, 0.2 to 0.3 s); fix the TTS first phrase (0.53 s against Kokoro's RTF 0.15) before routing work; compare 2B and 4B evidence use and RAM inside v1; trim history or raise context before 200-token answers and verify barge-in; ship a time-decay Formula and Rrf of statements and sightings plus the memory panel (Mmr, Facet later); record booth noise and grow the ASR fix list from logged misses.
Dylan: this project pushes the robot further than anyone else; training is not off the table. Squeeze the bigger model if RAM allows (measure a per-component RAM budget and what can be freed), finish v1, live test, then decide optimizations and training from the biggest measured gaps.

## D63 2026-10-08: Booth UX adopted with Dylan's changes
research/booth-ux.md (Fable design pass): one focus object for teaching (salience, 5 s hold, 1.6 margin, frozen while naming), labels for known objects with a guess band and hysteresis, auto views with a diversity rule and leave-one-out cleanup, negative points from "that's not my phone", corrections by voice, a status strip on the view, half-duplex audio, hold-to-talk on the view page, metrics for a live test day. Dylan's changes: only unknown objects take the focus and a held object can always be taught; one unprompted line, a greeting; a wake word with a follow-up window (method by bake-off, design gate first) instead of no wake word; 64 tokens for v1, revisit after the live test; undo instead of confirmation (agreed).

## D64 2026-10-08: M2.2b named objects land
robot/things.py: named objects in their own shard, DINOv2-small crops (CLS plus mean patch) as a MaxSim multivector, threshold 0.822 (held half: zero false matches against 625 same-class and 1,400 other-class distractors; 15/22 phones, 15/35 teddies matched), matched across detector labels; "this is my X", "forget my X" (with the naming turn, never re-stored, survives restart), "ignore"/"stop ignoring" a kind (sightings, captions, statements); recall exposed as evidence lines. One-time probes m2d 16/18; dev M2 38/74 (44 before the one-candidate binding rule); zero false "yours" claims; 15.3 ms per crop, 262 MB. Review PASS reviews/20261008-195032-46869-review.md. Carried: the one-candidate rule (replaced by the D63 focus object in v1), the detector misses composite phones, detect fps minimum 13.0.

## D65 2026-10-08: The wake word is "Hey Edgy" (Dylan)
Dylan kept the name: the robot answers a line that starts with "hey Edgy" (also "hi" or "okay Edgy"), never "edgy" or "edge" alone, then keeps a follow-up window of about 20 s (D63). Arm A first: spot the phrase in the Parakeet transcript with aliases taken from real and synthetic recordings; arm B (a trained openWakeWord "hey Edgy" model) only if A misses or false-triggers. Measure false accepts per hour on booth babble with "Qdrant Edge" spoken, false rejects at 1 m (research/wakeword.md). Rejected: renaming (Kodiak, Juniper, Memento proposed).

## D66 2026-10-08: TTS waits for the GPU; the 4B does not fit yet
Kokoro p50 for a 2-word phrase: 0.16 s alone, 0.27 s during llama decode, 0.35 s with the detector too (bench/results/2026-10-08-tts-*). Pausing decode at the first phrase (close the stream, synthesize, resume with the text so far as an assistant prefill) gave first audio 0.73 s vs 0.94 s p50 in a simulated turn with identical answers 24/24 (first-phrase-1791504119): adopted for v1 in robot/main.py and robot/brain.py. RAM (memory-1791503778): bge with the first CUDA session 409 MB, faces 297, DINOv2 172, YOLO 260, Parakeet 531, Kokoro 1,207 (about 750 MB CPU-side, cause unknown), llama-server 2B 1,921; 1,122 MB left with the 2B; Qwen3-VL-4B leaves 190 MB (231 MB with q8_0 KV) and swaps about 900 MB, against the 500 MB minimum. Next for the bigger brain (D62): free 400 to 900 MB, Kokoro first. Carried: swap grew 127 -> 1,070 MB in a replay with in-process restarts. Reviews end with PASS reviews/20261008-201415-76347-review.md.

## D67 2026-10-08: Focus object and booth screen modules land (not yet wired)
Design gate GO WITH CHANGES (reviews/20261008-202651-93371-design.md): rule-based focus is the v1 choice (no hand detector or depth camera yet). robot/focus.py: one unknown focus for teaching (worn items excluded; held at 0.8 inside a person box to take, 0.5 to keep; 1 s watch, 5 s hold, 1.6 margin; freeze while naming; scenery after about 60 s still; guess band 0.772 to 0.822 with hysteresis); target() binds only a live focus or the held object. robot/view.py draws a Screen: names, the focus box with its hint, grey unknowns, unnamed people, status strip, memory events, memory panel. Development evidence on the 90 s live clip (both halves seen): switches 1.33 and 4.12 per minute, one 2.9 s background focus (a reach toward a chair), held items focused in 1.0 to 1.5 s (bench/results/2026-10-08-focus-1791505537.jsonl). Review PASS reviews/20261008-202802-95037-review.md. Carried: an unseen clip is the test (live test day), no hand class, Jetson drawing cost.

## D68 2026-10-08: No names after a restart (Dylan); fixtures follow the rulings; the 4B still does not fit
Dylan: the robot does not need to know a name told before a restart. eval/dev/m2.jsonl: m2-restart-name-2 expects "I don't think we've met" and never Priya; m2-restart-name-3 does not attribute a fact told before the restart (D49); m2-restart-named-2 drops "left" (D61). Rule 6: changed on Dylan's rulings, not to match output.
V1-D (reviews/20261008-212158-65296-review.md): Kokoro's CPU-side memory is CUDA kernel code loaded on first use, mostly shared with the other CUDA sessions; in the robot it adds about 640 MB; no setting frees memory without changing behavior; Parakeet 629 MB is its int8 weights; 1,144 MB available with the 2B; the 4B leaves about 190 MB (bench/results/2026-10-08-kokoro-memory-diagnosis-1791509000.jsonl, memory-1791508856). Left for after v1 (D62): Kokoro on CPU (frees about 640 MB, short phrase up to 0.83 s), Kokoro fp16 (about 160 MB, conversion fails), Piper, a smaller 4B setup. v1 ships with the 2B.

## D69 2026-10-08: A name is not consent; the robot offers once (Dylan)
Telling a name lets the robot use it in this conversation (D60) but never enrolls a face: faces need explicit consent (CLAUDE.md fixed outcome). When a visitor who is not enrolled gives their name, the robot offers once: "Nice to meet you, Ana! Want me to remember your face so I recognize you next time?"; a yes enrolls through the consent path (two matching faces, vectors only); a no or no answer keeps the name in the conversation only; at most one offer per visitor.

## D70 2026-10-08: Only first-person statements are scoped to the visitor (Dylan)
Statements about the speaker ("I build drones", "my name is...", "I'm from Berlin") answer only for the same visitor (face match, or the conversation window when no face, as told names, D60); general statements ("the booth closes at 5") stay shared memory any visitor can recall. Part of the v1 retrieval task. Noted, not built: listen for a name introduction only when a new unrecognized face is present (reduces "I'm tired" style false names; the stoplist guard ships now).

## D71 2026-10-08: v1 logs edge cases and tests the whole robot first (Dylan)
Until v1 is tested end to end, review findings that are edge cases are logged in research/edge-cases.md (trigger, risk, proposed fix) instead of fixed; only failures of the main visitor flow or likely failures of fixed outcomes block (gates/review.md rule 8). Order: wire a minimal v1 end to end (retrieval into the brain, Hey Edgy, the focus screen), run the integrated visit and a live test day, change the architecture if they show it, then work the logged cases that actually happen.

## D72 2026-10-08: V1-A1 lands: decode pause, identity rulings, consent offer, live view
Pause decode at the first phrase (design verdict reviews/20261008-211909-61209-design.md: token-counted resume limit, exact-echo check, stream closed on failure); D60 and D68 told names (face match, or the 20 s no-face conversation window; none after a restart); D69 offer once, only with a usable face, enrollment by two matching faces; name detection guarded by a stoplist; the view runs in the robot with the Focus screen (lag 0.099 s p50). Results: visitor audio first audio 1.39 to 1.44 s p50 (D58: 1.61 s), p95 2.67 to 3.24 s; visitor audio 16/21 then 14/21 (unpaired variance); M3 oracle 33/33. Review PASS reviews/20261008-215317-7426-review.md. MAX_TOKENS 64 with the one-sentence cap stays for v1 (without it, half the answers were cut).

## D73 2026-10-08: Minimal v1 wired end to end; the 2B does not use retrieved evidence
V1-B: Hey Edgy (arm A: 7/9 synthetic wake lines, 0/9 background lines incl. "Qdrant Edge is fast"; replays open the window), a 20 s follow-up window from the end of the answer, first-person statements and history scoped to the conversation and cleared on a visitor change (face step before the prompt, about 60 ms), naming bound to Focus.target(), the memory panel with real hits. Retrieval into the brain lost to the code answers paired against HEAD (m2 34/74 vs 41/74, visitor 15/21 vs 17/21: the 2B ignored correct evidence lines; bge-small cannot score bare labels against questions), so the code answers stay and a Mac brain and prompt bake-off runs next (research/grounding.md). Whole robot: visitor audio 16/21 at 1.43 s first audio p50, visitor oracle 16/21, M3 33/33, sessions 43/47, headroom 1.2 to 1.3 GB, detection 14 to 15 fps. Review PASS reviews/20261008-233058-72473-review.md; edge cases logged (D71).

## D74 2026-10-08: Fix the evidence before changing or training the brain
Mac bake-off (bench/brain_bakeoff.py, research/grounding.md; review PASS reviews/20261008-234551-20256-review.md): no 2B-class brain beats the code answers by prompting, and the 4B upper bound only matches them; the failures trace to the evidence the robot builds (missing details, contradictions, "your" regions, missing told lines, ownership from weak matches). Next: fix evidence quality, adopt prompt shape I (evidence instruction after the image, keeps the prefill; 2B 32 -> 37 on m2), rerun retrieval into the brain against the code answers on the Jetson, then retire the code answers if not worse. Rejected for now: switching to LFM2-VL-3B (larger, longer re-prefill, misreads composites), a LoRA (the evidence is the bottleneck), the 4B (does not fit, D68).

## D75 2026-10-09: Evidence fixes kept; one voice ties the code answers; the 3080 box runs bake-offs
V1-E: one line per memory with its age, no left or right words (D61), duplicate captions and older sightings of a kind dropped, commands no longer stored as statements (they produced false ownership lines), the evidence instruction after the image (shape I, keeps the prefill), raw captions kept for shown(). Paired oracle on the Jetson: m2 HEAD 39/74, retrieval-into-brain 38/74, code answers with the fixes 44/74 (DEV-ONLY: not established until a fresh one-time unseen probe set confirms it, the first task of the next session, rule 6); visitor 16, 17, 16 of 21; M3 33/33; sessions 42/47. The frozen rule (delete the code answers only if retrieval-into-brain is not worse) missed by one m2 step: the code answers stay; the one-voice patch is saved as research/one-voice.patch. Reviews: reviews/20261009-010825-43776-review.md, 20261009-011200-49661-review.md.
X1: dylan@192.168.1.74 (RTX 3080, WSL2) runs llama.cpp 9c2e0e4 with an orin.patch (GGML_CUDA_NSM=8, CC 8.7) and matches the Jetson's answers 63/93 on the bake-off procedure (Mac 51/93; the box at its real 68 SMs 45/93 and deterministic 112/112); a five-brain pass takes 149 s (bench/brain_bakeoff.py --host dylan@192.168.1.74). Acceptance numbers stay on the Jetson.

## D76 2026-10-09: Raise the capability ceiling; make prior evidence usable (Dylan)
Prioritize stronger perception, sustained conversation, useful Qdrant Edge retrieval, and fluid interaction on the 8 GB Jetson. Targets are a floor. Read prior decisions and results before proposing another experiment; name the new hypothesis or changed evidence when reopening an approach.
H1: a Sol 6.1 high builder cleans the local harness, gates, logging, and session guidance after V1-E merged. Use Luna for research. Preserve runtime behavior, raw evidence, and acceptance criteria; no remote jobs in this cleanup.
The reported live conversation already uses swap. A warm memory snapshot or a KV-size estimate does not establish room for a larger context. Keep estimates separate from integrated measurements and unresolved causes.
Evidence: Dylan's instructions in this session; D68, D74, D75; research/lessons.md. Rejected: more feature cases or generic model sweeps before the foundation improves.

## D77 2026-10-09: Recheck audit findings and challenge decisions when useful (Dylan)
Log audit findings that still apply after V1-E, with source paths, evidence limits, concrete interventions, and the capability each could improve. Separate confirmed defects, measured limitations, and untested proposals; deduplicate existing research records.
Earlier decisions may be reviewed or challenged to raise the robot's capability ceiling. State the disputed assumption, new intervention or evidence, expected tradeoff, and comparison that would settle it; retain the original decision and its results.
H1 includes this record cleanup. Runtime changes and remote experiments remain outside H1. Evidence: Dylan's instruction in this session; D76.

## D78 2026-10-09: H1 makes experiment evidence and gates usable across sessions
Added offline tools/results.py over existing replay and bake-off records: separate judged, keyword, and retrieval scores, preserve provenance and missing results, reject stale or ambiguous sidecars. Replay logs identify heuristic scores; console output omits the full system prompt while raw evidence retains it.
Gate checks share one assertion interpreter, sort test paths, report timings, and stop entire process groups on timeout. A code tree changed during review cannot receive its stamp. Guidance and topic records now distinguish current results, rejected options, confirmed gaps, and untested candidates under D76 and D77.
Validation: local checks passed in 13.33 s with 58 pytest tests and all existing module/tool assertions; D75 M2 reproduced 62/74 keyword versus 44/74 judged. Review PASS: reviews/20261009-013611-82855-review.md. Runtime, models, raw evidence, and fixtures unchanged; no remote experiments.
Carried: one native pytest shutdown abort with unresolved cause; later runs passed without suppression. Review follow-ups: add rubric/fixture provenance to future judged records and include reviewed research in stamp coverage. Evidence: research/lessons.md and the review; no new runtime result claimed.

## D79 2026-10-09: Plan a substantial capability increase, then execute with fresh workers (Dylan)
This session plans only. The next autonomous session has the Jetson, WSL 3080, and Mac for a few hours; training and synthetic data are permitted. Use Sol 6.1 low workers for bounded implementation tasks and Luna for research. Qdrant Edge remains central; all deployed inference stays on the Jetson.
The lead prepares research/capability-plan.md with ranked interventions, alternatives, machine allocation, training/export prerequisites, paired adoption rules, and stop conditions. Architectural choices and old decisions can be challenged through D77; a larger model or completed training run is not itself a capability gain.
Evidence: Dylan's latest instruction; D74 through D78. Runtime, models, and fixtures remain unchanged during planning. Reject another broad model/prompt sweep or an edge-case backlog as the primary next session.

## D80 2026-10-09: Sol reviews overnight work; use WSL and allow measured OS changes (Dylan)
The next session uses Sol as reviewer and Sol 6.1 low workers. Planning pins the reviewer to gpt-6.1-sol explicitly. Use WSL wherever it accelerates preparation, data generation, training, export, or preliminary inference; Jetson measurements remain authoritative.
Saved camera footage and independent real videos support overnight comparisons. Final physical camera/audio and interruption validation remains separate. Keep whole source groups disjoint and prior development footage out of fresh acceptance.
OS changes on the dedicated robot hardware are authorized when they improve measured capability or capacity. Preserve remote access and rollback; no OS changes occur in this planning session. Evidence: Dylan's steering; research/capability-plan.md.

## D81 2026-10-09: Treat response distillation as a candidate and keep alternatives open
Dylan asks about distillation and requires open options and durable records of important findings, explored routes, and remaining choices. F3's teacher-generated targets plus LoRA already implement response distillation: the teacher supplies supervision; LoRA updates the student. This is a hypothesis, not a committed winner.
Target evidence use, conversational continuity, and natural final replies. Qualify teacher fidelity, student training/export, and integrated gains; do not infer better perception from answer training. Keep logit/feature distillation deferred until response training shows a specific limitation worth its extra cost.
Reassess routes after the first paired result and at least hourly. Log active/deferred/rejected status, exact results, why, and a reopening condition; stop after 90 minutes without new evidence. Evidence: research/lessons.md, research/capability-plan.md; original sequence-level distillation paper https://aclanthology.org/D16-1139/.

## D82 2026-10-09: P1 execution plan passes Sol review; no implementation started
The reviewed plan prioritizes source-linked event/dialogue retrieval, with response distillation and a stronger detector as bounded candidates. Larger runtimes and OS/provider changes remain eligible when measurements justify them. Four-hour core schedule protects at least 75 minutes for evaluation; extra work uses an available extension.
Astra counsel GO WITH CHANGES (reviews/20261009-014850-158-design.md) resolved by explicit answer-path replacement, evidence contract, LoRA preflight, independent sources, ownership, and a tighter schedule. Sol 6.1 review PASS: reviews/20261009-015822-12641-review.md; plan SHA256 f49ebf78cfbccf9b533e8208ff0ae78609a3135800f544026dda691ee372c134.
First evaluator brief must qualify paced video input: FileCamera currently accepts still images. New results, hardware changes, and model improvements remain unmeasured. Runtime, fixtures, models, and raw evidence are unchanged. Next session starts F0 and follows D80/D81.

## D83 2026-10-09: Remove execution deadlines and preserve the gates (Dylan)
Dylan removes the overall time limit. Readiness phases replace session, experiment, training, acquisition, OS-audit, and worker duration caps. Continue healthy work as long as needed; reassess routes by evidence and progress.
This supersedes scheduling limits in D79, D81, and D82, including clock-based abandonment. Measurement protocols, resource controls, command watchdogs, and architecture choices remain unchanged.
Design and review still check alternatives, over-engineering, scope, and overfitting; milestone review checks drift and acceptance. Align design/task defaults with Sol 6.1 and link exact gate files and commands in the handoff. Astra remains milestone reviewer and counsel. Evidence: Dylan's corrections; research/capability-plan.md.
Validation: local checks passed in 14.82 s; Sol 6.1 PASS reviews/20261009-021318-31433-review.md. Plan SHA256 e391f13e88a7823102e91b2ec48a44188f669d8277ed3061a956b1b257f33ed7. Gate criteria and robot behavior unchanged.

## D84 2026-10-09: Preserve overnight checkpoints on a dedicated branch (Dylan)
Start spike/overnight-2026-10-09 from main eb746fe; commit and push reviewed tasks frequently with their evidence. Main remains unchanged. F0 follows D79 through D83.
Reconciliation found Jetson release 4387936b8ee9 and both GPUs idle; preserve the other project's WSL container. Use bounded connection checks, command watchdogs, and progress-based recovery; healthy experiments have no overall deadline.
Evidence: bench/results/2026-10-09-session-status-1791526671.jsonl; Sol 6.1 status review PASS reviews/20261009-021753-38870-review.md. Idle memory and allocated swap establish no active-turn safety. Rejected: waiting indefinitely without a progress check or restarting jobs without inspecting ownership.

## D85 2026-10-09: Prevent ONNX Runtime telemetry shutdown failures in local gates
Two Mac crash reports locate the H1/F0 abort in the same ONNX Runtime 1.30 telemetry HTTP-response worker. All 69 tests had passed before SIGABRT; the gate correctly failed.
Launch pytest through tools/gate.py and disable telemetry before pytest or module-check sessions. Preserve every check, assertion, timeout, and exit code; product runtime and inference remain unchanged. This is a measured test-process workaround, not a claim that upstream lifetime code is repaired.
Evidence: bench/results/2026-10-09-native-shutdown-diagnosis.jsonl; installed disable_telemetry_events docstring and official API https://onnxruntime.ai/docs/api/python/api_summary.html. Rejected: suppressing the abort, accepting pytest text without its exit status, or retrying without diagnosis. Validation pending.
Validation: all 69 tests and remaining stages exited cleanly in 13.17 s; Sol 6.1 preparation review PASS reviews/20261009-023052-55411-review.md. The workaround remains limited to gate processes.

## D86 2026-10-09: Freeze F0's development evidence comparison before execution
Freeze 24 development questions, two forced-generative arms, identical model/system/history/image policy and limits; exclude actions, identity, and direction-only questions. Twelve packets correct visual evidence as an oracle upper bound, 11 stay unchanged, and one normalizes a transcript. Keep four ordinary controls.
Manifest SHA256 31451ef2d419add469b3d4fa6ce14d93bf655d3fc6026f7a391751d9122808ca; bench/evidence_probe.py saves incremental rows and omits completion on failure. The existing history reader separates arms. Prompt-token accounting is unavailable at the sentence stop.
Evidence: eval/dev/evidence-probe.jsonl and bench/test_evidence_probe.py; all 69 checks passed in 13.17 s; review PASS reviews/20261009-023052-55411-review.md. No capability result yet. The fresh 48-question challenge, continuous baseline, and training branch choice remain pending.

## D87 2026-10-09: F0 prioritizes observation and retrieval before language training
The Jetson 2B scored 14/24 with original evidence versus 21/24 with verified sufficient evidence, seven wins and zero losses; evidence questions 12/20 versus 19/20, controls two/four in both arms. All 11 unchanged packets kept their verdicts (nine identical answers).
Three sufficient-arm failures are below D79/F0's eight-failure trigger. Prioritize source quality, source-linked retrieval, and dialogue continuity; defer LoRA until sufficient production evidence demonstrates the trigger. This is a forced-generative development upper bound, not a deployed gain or integrated acceptance.
Evidence: bench/results/2026-10-09-bakeoff-evidence-probe-1791527749.jsonl, .judged.jsonl, and 2026-10-09-f0-operations.jsonl; release 51bdbb62cea6, frozen manifest 31451ef2d419add469b3d4fa6ce14d93bf655d3fc6026f7a391751d9122808ca. Fresh challenge and continuous baseline remain pending; result review pending.
Validation: Sol 6.1 result review PASS reviews/20261009-024234-70640-review.md reproduced counts, paired changes, hashes, rubric provenance, and the route rule.

## D88 2026-10-09: Qualify clock-paced file video before the fresh challenge
Prefer pull-based newest-due decoding through FileCamera, one lock, monotonic playback, wall-anchor evidence stamps, final-frame hold, and caller-owned cleanup. Keep a decoder thread as the measured fallback; pre-extracted JPEGs add avoidable storage.
Design GO WITH CHANGES reviews/20261009-025338-83534-design.md: measure concurrent 15 Hz detector, 0.3 s watcher, and 1 s speech reads, plus a 0.5 s detector pause. Freeze per-caller p95 latest() <= one source interval, frame age <= two; require independent frame identity for all returns. Record source rate, skips, counts, and RSS on Jetson.
Scope: camera.py, source tests/benchmark, replay caller cleanup only. Preserve stored orientation; the old clip benchmark rotates the raw development clip. No model, memory, detector, voice, or OS change. Evidence/brief: research/sight.md and STATE.md. Implementation and qualification pending.

## D89 2026-10-09: Disable the gate telemetry uploader before initialization
D85 API suppression was intermittent: a third Mac crash aborted after all 78 tests passed in F0b. The same ORT 1.30 HTTP worker caused all three crashes.
Official v1.30 Privacy.md and telemetry source show API suppression leaves the uploader alive. Set ORT_DISABLE_TELEMETRY=1 before runtime imports in gate pytest/modules; remove the API-only import. Keep dependencies, product inference, checks, exits, and watchdogs unchanged.
Rejected: ignoring post-test aborts, blind retries, replacing the runtime, or rebuilding it when the installed binary supports this documented flag. Evidence: bench/results/2026-10-09-native-shutdown-diagnosis.jsonl; https://github.com/microsoft/onnxruntime/blob/v1.30.0/docs/Privacy.md. Full checks passed in 13.29 s; task review pending.
Validation: Sol 6.1 task review PASS reviews/20261009-030935-4181-review.md reproduced counts, native diagnosis, pre-initialization ordering, and retained exit handling.

## D90 2026-10-09: Adopt the qualified pull-based file source
D88 option A passed its frozen Jetson development check: 572/572 pixel identities, all three callers within 66.67 ms latest and 133.33 ms age p95 budgets; 14.8 unique source fps from a recorded 15 fps clip, 83.34 MiB RSS peak.
Use FileCamera for paced constant-rate captured files with accurate indexing, preserve stored orientation and final-frame hold, and keep cleanup caller-owned across Robot restarts. No measured reason to implement the decoder-thread alternative. Integrated detection, paging, sustained conversation, and semantic orientation remain unproven.
Evidence: bench/results/2026-10-09-camera-source-1791529599845132270.jsonl, paired tegrastats, and 2026-10-09-f0b-operations.jsonl; release d7ed8b31a024. Full local checks passed; Sol 6.1 review PASS reviews/20261009-030935-4181-review.md. Carry detector source-error propagation under D71 in research/edge-cases.md.

## D91 2026-10-09: Freeze independent timed challenge data before tuning
Freeze 48 scored questions, 15 auxiliary statements, and six upright MJPG clips across three absolute 600 s visits. All 710 indexed frames match sequential decoding; six AVIs reproduce byte-identically. Source motion is short; final-frame hold supplies the later schedule.
Exclude every Objectron source from training because participant and cross-capture physical IDs are unavailable. Preserve source URLs, C-UDA attribution, raw PTS, separate lossy hashes, exact frame evidence, and reviewer-only rubrics. Reject repeated-hold encoded movies and adjacent-frame acceptance splits.
Evidence: eval/challenge-20261009/freeze.json SHA256 e0e389ff0774a32d746482b27039d1a2ce3c75e86e66f8a6846a7b56fd1879b9; 57 files, 39,679,699 bytes. Full checks: 78 tests, clean exit in 12.35 s. Sol 6.1 review PASS reviews/20261009-034031-43247-review.md independently reproduced hashes and evidence checks. No baseline or capability claim.
Carry verify regeneration under changed OpenCV as an optional risk; current hashes match. Continuous harness, audio preparation, integrated timing, paging, and baseline remain separate prerequisites.

## D92 2026-10-09: Supervise continuous evaluation outside the runtime process
Prefer a dedicated absolute audio scheduler over adding reset/timing branches to legacy replay. Keep one unchanged Robot/FileCamera across visits, sample-end input cadence, timestamp-based association, incremental logs, separate scoring, and measured paging. No product/model change.
Design GO WITH CHANGES reviews/20261009-034911-54216-design.md requires a separate supervisor process, full worker-group cleanup, footer only after zero worker exit/native teardown, and subprocess stall/crash tests. research/continuous-eval.md incorporates these requirements and fixes a 90 s development smoke before baseline.
Builder receives generic invented schema/tests without challenge access. Use synthesized speech through VAD/ASR; physical audible latency and exact prompt-token accounting remain unproven. Rejected: queue-order association, interpreter-local watchdogs, or success markers before process exit.
Evidence: D87, D90, D91, and the design receipt. Implementation, task review, integrated smoke, and 1,800 s baseline remain pending.

## D93 2026-10-09: Adopt the supervised continuous audio evaluator
F0d passes104 local tests/checks and its frozen Jetson90s development smoke on f96b251e7518: one Robot, two visits, four utterances, two shows,1,440,000samples,4/4 switch/held-frame pixel matches, and zero worker/unit exit before completion. Maximum chunk/event lateness0.153/0.097s is within0.5s.
Use separate process supervision, fixed sample-end timing, timestamp association, streamed logs, bounded group cleanup/reaping, and run-owned session directories. Some replies miss requests. This qualifies measurement only; sustained quality, physical audio, exact prompt-token totals, and M4 remain unproven.
System paging55in/55out pages occurred; active-labelled samples47in/1out, with runtime sampledVmSwap0 and at least1,258MiB available. Attribution stays unresolved. Identical AVI bytes yield0/90 cross-platform pixel hashes; record Mac/Jetson FFmpeg builds and qualify a deployed-decoder oracle before the challenge baseline.
Evidence: bench/results/2026-10-09-continuous-smoke-1.jsonl, paired tegrastats, 2026-10-09-f0d-operations.jsonl; Sol6.1 review PASS reviews/20261009-042113-94477-review.md. Reject internal-only watchdogs, queue-order association, unbounded reaping, or completion before native exit. Next: frozen audio/deployed-decoder preparation, then1,800s baseline.

## D94 2026-10-09: Freeze speech inputs and the deployed decoder before baseline
Keep D91 data byte-identical; freeze63 synthetic WAVs separately with six heldout voices, text/source/audio hashes, and recipes. All48 scored/15 auxiliary inputs and endpoint gaps pass the1,800s preflight. Audio8,366,664bytes; freezeSHA be7cc335a41c3e1d39980a681828e04290083569afa6e31f14e0ad1c36c0ca82.
Jetson cd60be65ee79 verifies710/710 reverse-index matches over six15fps480x640 clips; unit exits successfully under an external90s native watchdog. Preserve a Jetson pixel oracle because Mac and Jetson decoder builds differ. No model execution, baseline, tuning, or capability claim.
Evidence: bench/results/2026-10-09-fixture-decode-1791535339564674223.jsonl SHA80623781c7a5ada65047df5e0246378635f0212ff3c2499c2e11a265922cf041, paired tegrastats,2026-10-09-f0e-operations.jsonl. All104 checks passed15.19s; Sol6.1 review PASS reviews/20261009-044433-22776-review.md independently verifies hashes/audio/decoder evidence.

## D95 2026-10-09: Score continuous evidence with shared judgments and speech checks
Adapt scoring to separate frozen rubrics after validating full post-exit completion/coverage/samples/source hash. Reuse the existing cached three-vote judge through one helper; preserve legacy judging behavior. Keep structural failures failed.
Measure confirmed prompt sources separately from answer correctness; exclude current-frame storage, captions removed by deduplication, and ambiguous statement mappings. Resolve newest identical captions from payloads against final prompt text; unknown delivery stays explicit. This is a lower-bound source measure within five returned entries, not fact sufficiency or history coverage. Speech verification saves independent transcripts/hashes and keeps missing/empty/split outputs failed.
Evidence: eval/score_continuous.py and generic tests, eval/judge.py, eval/speech.py and tests; all114 checks14.99s. Four completed development-smoke WAVs independently transcribe at zeroWER on Mac: bench/results/2026-10-09-continuous-smoke-1.speech.jsonl. First review FIX reviews/20261009-045854-40786-review.md: raw IDs can credit deduplicated captions. Fixed via final prompt/payload filtering and generic reproduction; corrected115 checks14.89s, review PASS reviews/20261009-050825-52797-review.md. Baseline remains running and unjudged.

## D96 2026-10-09: Preserve the continuous baseline failures before evidence changes
The frozen Jetson baseline scores10/48(6/12 visual,0/9 older,0/9 topic,0/6 correction,1/6 absent,3/6 chat). Four scored questions and five auxiliary statements split. Source IDs alone do not prove sufficient facts; allnine older-delivery measures are unknown/lower bounds. Prioritize grounded observations/retrieval/continuity; D87 language training remains deferred.
One process completes1,800.187s,63 utterances/72 turns/69 events/28,800,000 samples,12/12 source probes, and native worker exit0. Supervisor/unit exits1 for nine failed steps; no retry or fixture/pacing change. All72 unique nonempty WAVs transcribe within0.35WER; strict speech54/72 retains18 split-turn failures.
First synthesized audio2.291/3.228s p50/p95; per-turn detection13.408minimum/14.900medianfps; minimum headroom1,062.56MiB. System paging89in/852out pages, fully-active56in/16out; sampled runtimeVmSwap0 does not prove attribution or safety. Physical audio,15fps, no-paging, and quality targets remain unmet.
Evidence: bench/results/2026-10-09-continuous-baseline-a.jsonl and .judged/.speech/.scoring.jsonl, paired tegrastats,2026-10-09-f0f-operations.jsonl,2026-10-09-f0f-audit.py.txt. Releasecd60be65ee79; scoring0a76aaa. Sol6.1 review PASS reviews/20261009-052607-74465-review.md independently reproduces counts, hashes, scores, and resource limits.

## D97 2026-10-09: Qualify source-owned semantic retrieval before implementation
Prefer additive observed/dialogue MaxSim vectors on existing seen points over a separate unit shard, pending Jetson comparison. Edge0.8 Mac probes preserve old/new reads, stable IDs, distinct later-unit recall, repeated creation, and deletion after reopen. No live memories changed.
Design GO WITH CHANGES reviews/20261009-055752-11735-design.md requires bounded rendered prompt spans, per-kind source hashes/visitor checks, separate calibration, representative retained-volume costs, and <=0.2s synthesized-p50 regression. Corrected research/event-memory.md adopts these requirements; no product gain yet.
Freeze24 controlled-text comparison questions SHA7f2041d898c4f0fea87b1b7a9d1386fc58790a0b97bccbcf291f30a467803ee8 and separate12 calibration questions SHA409c8e9b8ae343ed9824f9e39a6969884b431b884f7344b675ce0a4b66b98507. Placeholder frames establish no perception result; builders stay blind to fresh challenge detail.
Evidence: eval/dev/event-{retrieval,calibration}.jsonl, bench/results/2026-10-09-f1-schema-api.jsonl and archived probes. Rejected: forced migration, duplicate event copies, unrestricted full-text prompts, summary/fusion machinery, or training before source gains. Preparation review PASS reviews/20261009-060639-22828-review.md verifies the corrected contract and frozen data. Implementation and Jetson acceptance remain pending.

## D98 2026-10-09: Reject the first calibration policy; preserve native source retrieval
Mac supporting-event recall falls12/18 to5/18 under minimum-positive floors0.755407/0.750094 from three direct questions per kind. Keep the frozen first arm and all raw records. No answers judged, deployment, or Jetson acceptance; prototype stop criterion reached.
Astra counsel GO WITH CHANGES reviews/20261009-062748-48954-design.md separates ranking, delivery, and grounding. Its score-free diagnostic finds18/18 full supporting spans within five entries, all rank one in their kind. Cutoffs cause the immediate loss; native MaxSim remains unrefuted.
Initial benchmark counted wrong-kind IDs and ignored utterance_start/end; corrected code/tests preserve original output. Original executable provenance is incomplete; current per-file hashes and native-exit receipt cover the diagnostic. Fresh disambiguated relevance/sufficiency labels, merge/span policy, and comparison must freeze before the next arm. Keep0.5 production floor as a control; defer generation until source gains.
Evidence: bench/results/2026-10-09-f1a-mac-{calibration,comparison,audit,diagnostic}-1.jsonl,operations.jsonl,and archived audit. All126 checks19.19s; diagnostic native0 in16.28s. Retain productioncd60; separate shards,summaries,fusion,training,and larger context stay deferred. Sol6.1 review PASS reviews/20261009-064447-68946-review.md independently reproduces counts and hashes; carry the 64-candidate post-filter risk under D71.

## D99 2026-10-09: Freeze independent relevance labels before new source selection
F1b freezes new invented calibration and comparison sources before embeddings. Relevance includes related partial facts; sufficiency requires the requested fact. Each populated source-kind pair gets both labels, with exact decisive spans and actual speech times. Prior fixtures and failed thresholds stay unchanged.
Calibrated floors retain95% of relevant pairs on a fixed0.01 cosine grid. Compare calibrated, bounded ranked, and0.5 control arms with identical eligibility and five-entry best-unit delivery; expected labels never route selection. Preserve rendered2K/64-output/256-image limits before later generation.
Require source recall +20 percentage points or90%, no category loss in delivered facts, then paired answer gains and D97 Jetson costs. Prefer ranked retrieval unless calibration preserves its supporting spans while rejecting more unrelated sources. Reject retuning on comparison, missing-fact cosine claims, new models, or intermediate challenge runs.
Evidence: research/event-selection.md; new eval/dev/event-{calibration,retrieval}-2.jsonl and event-selection-2.freeze.json, focused validation. Sol6.1 review FIX reviews/20261009-071035-215-review.md corrected an ice-display relevance label before scoring; recurring patterns remain a logged limit. Corrected Sol6.1 review PASS reviews/20261009-071517-6377-review.md validates64 cases and hashes; full checks25.55s. No scoring or deployment.

## D100 2026-10-09: Select calibrated source spans for paired answer qualification
Fresh32-case Mac comparison(E) delivers24/24 positive sources and exact facts for calibrated,ranked,and0.5 arms versus16/24 production. Older0/8 rises8/8; topics/corrections remain8/8. Calibrated preserves every ranked supporting span, with two unrelated selections versus107 ranked,16 control,and99 production. Choose calibrated provisionally under D99; no answer or deployed gain claimed.
Frozen relevance floors0.53 observation/0.55 utterance each retain46/48 relevant calibration pairs with zero irrelevant returns. All384 eligible calibration pairs are scored; native exits0 in23.35s/22.34s for calibration/comparison, thresholds frozen before comparison. Four later-than128-token facts reach bounded units. First failed floors remain unchanged.
Reuse native source-owned MaxSim; reject unconditional five-entry ranking when calibrated spans retain its facts and reject more unrelated evidence. Keep base model,2K/64/256 limits,and runtime unchanged until paired answers, rendered-budget qualification, actual production selection, representative Jetson costs,and safety regressions pass. Repeated synthetic patterns limit generalization.
Evidence: bench/results/2026-10-09-f1c-mac-{calibration,comparison}-1.jsonl,operations.jsonl,and archived native supervisor/audit. Per-file/model hashes match; independent audit reproduces selections, facts, counts,and native receipts. Full checks25.02s; Sol6.1 review PASS reviews/20261009-073249-27709-review.md independently reproduces evidence. Production stayscd60be65ee79.

## D101 2026-10-09: Match native event retrieval to frozen source ordering
A generic Edge0.8 equal-score probe(E) selectsIDs3–7 instead of frozen1–5 from eight eligible sources. Sort the existing64-hit candidate pool by descending score then source ID before hydration; keep early stopping, filters, limits, and lifecycle behavior. No new pagination or architecture.
Actual Memory.events qualification(E) matches all32 frozen calibrated packets, source IDs/hashes/spans/results exactly:24 supporting facts, two unrelated returns. Native exit0 in22.14s; corrected tie probe1–5 both kinds native0 in0.70s. Frozen0.53/0.55 floors/model/procedure remain unchanged; original versus current code differs only by the sort.
Six focused lifecycle/tie tests3.34s and full checks26.11s pass. Launcher import and absolute-hash-key guards each failed before model/shard creation, were preserved, diagnosed, and retried once. Reject a threshold retune or full-fixture inspection as a substitute for actual API qualification.64-candidate exhaustion and large-volume costs remain carried.
Evidence: bench/results/2026-10-09-f1d-{native-tie-before,native-tie-after,mac-api-1}.jsonl,operations.jsonl,and archived probes/failures; research/event-delivery.md. Sol6.1 review PASS reviews/20261009-075131-50293-review.md independently verifies packets, bindings, and native receipts. Rendered2K delivery, paired answers, Jetson costs, and deployed gains remain unmet; production stayscd60.

## D102 2026-10-09: Qualify rendered accounting and end the preparation detour
Jetson d2955df8adf8 template/tokenizer counts match native prompt usage315/379 for text/history. Image568 fits conservative600 including256 image reserve; text3532 exceeds2K plus64 output reserve and is not submitted. Four cases/native0 in6.74s qualify accounting only; enforcement and answer gain remain unmet.
Two failed assertions assumed max_tokens0 meant zero completion or empty content. Preserve both partial runs. Astra counsel GO WITH CHANGES reviews/20261009-081935-83856-design.md directs actual count/content/finish-reason logging; corrected probe applies it. Keep current runtime/model/prefill behavior; reject endpoint redesign or expanded fixtures.
Dylan corrects six-hour focus: fourteen reviewed checkpoints demonstrated no deployed quality/latency gain. Finish this task, then integrate source spans and require paired Jetson answers/latency before further benchmark expansion. Earlier and new scores use different workloads and do not establish regression.
Evidence: bench/results/2026-10-09-prompt-budget-1791548480619362451.jsonl SHAe1906543ff565fecf0cdbbf82eb667443f247defd50dc3bc2c823bc98a247916,failed runs,archived probes,journals,tegrastats,and f1e-operations.jsonl. Two tests0.14s/full checks26.61s pass; Sol6.1 review PASS reviews/20261009-082349-88726-review.md independently reproduces counts/hashes and focused checks.

## D103 2026-10-09: Select calibrated retrieval after paired Jetson answer gain
F1f on d2955df8adf8 compares the same forced-generative path on production/calibrated evidence:22/32→30/32, eight wins/zero losses: older0/8→8/8, topics/absence8/8 both, corrections6/8 both. Exact facts16/24→24/24, unrelated99→2, no budget drops. Freeze calibrated0.53/0.55 for runtime integration; retain ordinary code/actions/identity. Reject fixture-specific correction rules, more calibration, or training before an integrated result.
Warm31-per-arm post-transcript first synthp501.077→1.058s,p951.502→1.363s, within0.2s regression allowance; no reliable speedup claim. Full model stack loaded/detector+TTS active, no ASR input. Minimum loaded headroom1,343MiB; minimum turn detector14.449fps; system paging1in/2out versus10in/1out is unassigned and remains unmet. No full-turn/volume/sustained acceptance claim.
Native worker0 completes64 answers. Independent source/span/budget audit and cached three-vote judging pass. Speech63/64/native1 preserves one0.375WER failure already incorrect by text; joint correctness22/32→30/32. Initial audit import fails before judge; identical-source retry usesPYTHONPATH root. Do not retry quality failures or weaken rubrics.
Evidence: bench/results/2026-10-09-paired-event-answers-1791549264663591169.jsonl SHA80510ecbdfc5135280142eba6defa05200deffd01fbcd65a085819b66e9a5857,judged/speech/telemetry,2026-10-09-f1f-operations.jsonl,launches,archived runner/audit,and tegrastats. Sol6.1 review PASS reviews/20261009-084552-14016-review.md independently reproduces scores,source/span/budget/WAV bindings,and limits. Integration and unchanged audio/safety comparisons are next.

## D104 2026-10-09: Diagnose runtime timing while comparing unchanged audio
F1g first candidatefb9ba71bcf4e fails frozen90s smoke at46s: audio lateness0.519s exceeds0.5s; cleanup native-6 is secondary. Retainedcd60 completes90.100s/worker0 with max0.197s lateness. Preserve both; no cause or integrated gain claimed. Restore existing past-question role for observations, without scenario rules, prompt edits, or retuning.
Astra counsel GO WITH CHANGES prefers narrow diagnosis within the unchanged paired recorded-audio comparison. Log actual chunk arrival/hear/VAD/evaluator-report timing, budget-call counts/cost, and prefill duration. Successful legacy replay cannot clear the strict smoke failure. Reject premature process isolation, caching, more fixtures, and repeated quality runs for PASS.
Candidate435518db9947 adds source-role guard/timing;137 local checks pass27.89s. Baseline audio was already running without the narrow observer; preserve this instrumentation difference and avoid small speedup claims. Keep500MiB floor, <=0.2s synthesized-p50 regression, paging/detection/safety/representative costs, exact spans, and strict smoke/native lifecycle requirements open.
Evidence: research/event-delivery.md; bench/results/2026-10-09-f1g-smoke-{a,baseline-a}.jsonl,journal,tegrastats,operations,archived supervisors/workers; reviews/20261009-091830-51018-design.md. Gate exits3 for GO WITH CHANGES and test-added tree mismatch; no stamp. Actions apply to final task review; adoption remains pending.

## D105 2026-10-09: Reject runtime adoption and reassess the ordinary answer path
Unchanged47-step audio pair(J) completes47/47,48 outputs/one split each,native1 with clean teardown. Baseline42/47 versus candidate41/47 judged,zero wins/one current-image loss; joint39→38,speech43/48 both. Warm first synthp501.416→1.455s,p951.907→2.155s. No overall gain; preserve failures,restorecd60/previous435. No source/floor/prompt/case retune.
Four exact utterance spans and zero semantic observations expose ordinary past-object code answers bypassing improved generative evidence. F1f22→30 remains controlled only. Reassess general answer architecture under D75/D77 with changed retrieval before model/context/scheduling intervention. Reject individual visual patches,new calibration,and unused-retrieval product claims.
Loaded sampled headroom1,075/1,148MiB; minimum turn detect11.338/13.805fps; system paging4,204/39,057 versus4,045/9,207 pages(in/out),unattributed. Strict smoke0.519s/native-6 remain unresolved. Observer has one1.099s cold delay,later0.122s,no cause claimed,and differs from baseline. Stop adoption/final challenge/volume/safety expansion; final targets stay unmet.
Evidence: research/event-delivery.md,f1g-operations.jsonl/native0 paired audit; raw2026-10-09-replay-{1791552444,1791553079}.jsonl/sidecars/receipts/tegrastats/48WAV hashes per arm.137 checks27.89s. Sol6.1 task review pending for rejected spike checkpoint. Next architecture must demonstrate a paired general capability/latency gain.


## D106 2026-10-09: Open semantic caption evidence through the ordinary answer path
Sol6.1 design GO WITH CHANGES selects A: delete shown() recency-only caption answers and newly unused runtime reads/helpers, preserve detector/state/actions/privacy/benchmark readers. Verify actual delivered observation spans through Brain.context; no chronology/query repairs, new fixtures, model, prompt, or floor changes.
Compare retainedcd60 with A on unchanged Jetson oracle M2/visitor74+21 turns per arm, fresh memories, exact models/inputs; require aggregate gain/no capability loss and warm first-synth median regression<=0.2s. Preserve native completion, joint speech, routing/source spans, p95/full-answer duration, detection, headroom, and paging. Historical D75 is context only.
Reject broader sighting deletion initially and capacity/scheduling-first while evidence bypass persists. No extra unchangedF1g control unless attribution is disputed. Selected recorded audio/strict smoke/lifecycle/safety/volume remain adoption gates; no general or sustained gain claimed yet.
Evidence: research/answer-path.md; reviews/20261009-100717-4643-design.md; generic real-Edge/full-turn check verifies caption evidence reaches bounded generation;138 local tests/full checks27.51s/native0. Jetson paired measurement underway; candidate unadopted.


## D107 2026-10-09: Select integrated source evidence for audio qualification
Unchanged Jetson95-turn pair(J) judged54→58,joint53→56,speech94→93; M2 five wins/one loss38→42,visitor16/21both,no category loss. Warm86 synthp501.022→1.020,p951.730→1.806; instrumentation differs,no speedup. All four native1 quality failures complete/clean; source/span/budget audit passes. Two code→generation transitions yield no judged wins; no causal shown-deletion claim.
WSL standalone12 source-grounded packets(E)2B8/12 versus4B7/12,zero wins/one loss; fresh2B answerparity9/12/verdict12/12, native0/no overflow/clean. Reject4B integration from this result; single-call/pause differences and sampled VRAM establish no Jetsoncapacity evidence.
Keep the smaller source-retrieval bundle for selected strictsmoke/recorded-audio qualification, without adoption. Preserve existing thresholds/models/prompts/fixtures. System paging/detector target, native-6, physical/sustained, retained-volume, and independent deletion/safety remain unmet; no individual-case repairs or extra unchangedF1g control absent disputed attribution.
Evidence: research/answer-path.md,brain-capacity.md; f1h-audit aggregate/m2/visitor and f1h-box-m2 artifacts; four native receipts and all95WAVs/turns per arm.138 local checks27.51s; Sol6.1 taskreviewPASS reviews/20261009-110025-64682-review.md in132.91s verifies completed prototype/code/evidence; adoption pending.


## D108 2026-10-09: Reject F1h adoption after recorded audio qualification
Selected unchanged90s smoke(J) passes90.104s/worker0/unit0/clean,0.420s maxlateness<0.5. Exact executedtrace shows0.428s report/0.427s resources ending0.003s before delayedchunk; otherthreads overlap. Diagnose synchronous evaluator collection, without continuous GIL-freeze or causal root-fix claims. Preserve prior0.519/native-6 failure.
Unchanged47recorded-audio questions(J), matching68inputs/SYSTEM/models/limits versus preserved completedbaseline: judged42→39,joint39→36,zero wins/three memoryrecall losses,speech43→45/48,one splitboth. Warm46 synthp501.416→1.473,p951.907→1.884; synthesiscompletionp502.286→2.490. Candidate47/47/nativequality1/clean. Observer/earlierbaseline differences prohibit causal speedup claims; no quality retry or case repair.
Reject adoption, restorecd60 while retaining038 candidate/evidence. Oracle54→58 remains prototype-only; general memory evidence/routing needs a stronger design. After two failed integrated approaches, use Astra counsel before a third. Volume/deletion/upgrade/held-out/physical/sustained/no-paging/detector targets stay unmet; no large model/context/process isolation from these data.
Evidence: f1i-smoke-{audit,independent-audit}.json/raw/timing/launch and nativejournal; f1i-audio-audit.json/raw1791561551/judge/full48turns/speech/native receipt1791561022769530053. Loadedavailable~1,075MiB both; detector11.338→13.523minimumfps; systempagingunattributed. Taskreview pending, spike only.


## D109 2026-10-09: Preserve answer authority and assemble sufficient source context
F1i rejected checkpoint Sol6.1reviewPASS131.05s/native0/fullchecks29.75s/committedpushed2d4b38e. Astra counselGO WITH CHANGES68.15s/native3 selects bounded source-evidence assembly around2B, preserving baseline captions/timed sightings/exactstate/actions/identity. Prior sequence overvalued generative routing; evidence and conversation continuity remain largest demonstrated gaps, with relative contributions uncertain.
Freeze selection, temporalbounds, authorityprecedence, and costs before building. A combines semantic source matches with bounded same-scope chronological neighbors/literal provenance/time/uncertainty. B holds selection/authority fixed and substitutes one linked retained frame/crop,256image tokens/2Kcontext/64output, no independentimage copies. Delete replaced span assembly if A wins. Preserve frozen floors/source-ownedmultivectors.
Compare baseline/A through actualJetson M2/visitor, thenA/B across existingvisual-memory turns selected before scoring; separately log stored/selected/delivered/sufficient sources. Require pairedjudged/jointspeech gain/no capability loss/<=0.2s synthp50regression before unchanged audio/smoke. No quality retry/individual-case repair/extra shard/summaries/processfanout/largercontext/training. Optional evaluator counter reduction stays proportionate. Voice C needs cheap integrated quality-preserving evidence, not cumulative ASR-stage inference.
Evidence: reviews/20261009-120725-43893-design.md and20261009-120304-37972-review.md; F1f/F1h/F1i audits andresearch/answer-path.md. Baselinecd60restored; candidate038retained. Sourceprivacy/consent/deletion/restart/images and remainingvolume/safety/held-out/sustained/physical15fps/500MB/no-paging targets remain fixed. Next: freeze bounded contract, not runtime implementation yet.

## D110 2026-10-09: Freeze evidence assembly before runtime implementation
D109 contract is frozen in research/answer-path.md (SHA256 e7a4e1521ef098bac83db1d52791ddf74e20f7b906fc2067a79335eab3768729): preserve cd60 authority; three semantic seeds, two same-kind/scope neighbors within inclusive120s, five sources/15units maximum, existing2K/64/256/floors. Bounds are U engineering choices.
B freezes16 metadata-selected inputs (manifest f9ea045b66129861a485003c1403759c76d2645ba61b804ba1d5adb50915a30b), explicit historical-image roles, identical pre-generation packets, and source-owned frames. Coverage floors10 generatedA/four eligibleB; no gain or regression rejects adoption. Capacity/training/routing deletion remain rejected alternatives pending new evidence.
Sol6.1 designGO WITH CHANGES resolves four contract gaps; taskreviewPASS confirms all four fixes, manifest/source hashes, privacy, budgets, stops, and freeze-only scope. No runtime edits, deployment, or answer-gain claim. Candidate-limit exhaustion and first-three-neighbor omissions remain measured risks.
Evidence: reviews/20261009-123250-71965-design.md; reviews/20261009-123529-75394-review.md; research/f1j-visual-inputs.json; research/lessons.md. Next implementation restores baseline caption authority before building A; unchanged pairs and final qualification remain required.

## D111 2026-10-09: Choose a hybrid dialogue model and small observer, then build
Dylan rejects repeated evaluation planning. CLAUDE now requires selected architecture, runnable build, and existing validation; P2 testing draft/dispatch superseded before builders. Research returns decisions, not another test matrix.
Choose Granite4.0-H-Micro3B Q4_K_M plus SmolVLM2-500M Q8 observer on pinned CUDA llama.cpp,4K/128/three sentences, token-budgeted dialogue, in-processEdge/code actions, existing source-owned observations. Keep ParakeetCPU; select upstream KokoroFP16CUDA. Gains remain U until execution.
Material fallback: Gemma4E2B INT4AWQ with TensorRT Edge-LLM/MTP. Liquid hybrid/audio deferred for commercial-license/WIP constraints; FP4 excluded onOrin. No new fixtures/harness/schema/retention path before runnable replies. First checkpoint is actual text/image answers, then existing regressions/continuous validation.
Evidence: research/architecture-choice.md and primary sources therein; twoLuna research reports; revisedCLAUDE/lessons; previous P2 planning reviews remain historical, not dispatch authority. Lead owns pins/deploy/status; builders use isolated branches and report without editing shared state.

## D112 2026-10-09: Keep Q4 dialogue and restore qualified speech for the split build
WSL(E) existing12 frozen source packets: GraniteQ4 andQ8 both9/12 versus qualifiedQwen2B8/12; both fail the same three cases. Q8 adds1.45GB weights without a diagnostic quality gain. KeepQ4; no integrated/adoption/held-out claim.
Jetson6283246e9253 first integrated startup fails on upstreamKokoroFP16 warmup: zero-size audio in kokoro_onnx.pauses._quiet_frames; native1, no completed turns. Restore qualifiedFP32 speech in the split branch rather than delay the new architecture. This differs from earlier local conversion failure; preserve both, no third FP16 approach without counsel.
Dylan selects gpt-6.1-sol/low for all further builders this session; existing completed work stays. Build GemmaINT4/TRT fallback separately on WSL, with Jetson engine builds queued after primary. Productioncd60 remains rollback.
Evidence: bench/results/2026-10-09-p2-granite-{q4,q8}-wsl.jsonl/.judged.jsonl, p2-smol-clock-wsl.json, qr-p2-hybrid-m1 journal/tegrastats; selected-design review131139. Next: actual split-model robot replies with qualified speech, not another evaluation plan.

## D113 2026-10-09: Give the new dialogue model a fair evidence interface
Split prototype9141a7b is runnable/reviewed/pushed; Jetson oracle26/47 judged,30/47 keyword, correct observations sometimes ignored, observed worker swap. Adoption remains rejected at this checkpoint; family/layout choice stays open. Four spent uncached probes reproduce wrong sources; simple prompt/sampling changes each fix one selected case. Two no-history tool calls validate schemas but retain unsupported detail/agency.
Astra counselGO WITH CHANGES/native3/106.93s selects one-pass code-constructed aggregate tool-result evidence before another model judgment. Keep retrieval/actions in code and exact source/history/uncertainty. Match tool IDs; disable further tool selection; unify rendered/generation/resume metadata. Paired user-text/tool-result diagnostics share SYSTEM/sampling, include prior successes, then existing integrated pause/resume validation if useful.
Reject autonomous routing/new dispatch/history summaries/per-case repairs/new harness. D21 remains evidence against a second routing pass; schema compliance is not answer quality. GemmaINT4 quantization continues separately onWSL; all acceptance targets remain unmet.
Evidence: reviews/20261009-140048-81746-design.md; p2-granite-{dialogue,tools}-probe and p2-hybrid-m1-fullturns in bench/results; research/p2-briefs/evidence-role.md. No new planning gate before the scoped build.

## D114 2026-10-09: Preserve the source-role prototype without adoption
P2-R4f6b920 passes Sol6.1 taskreview140847 and fullchecks15.22s, committed/pushed on its spike. Jetson standalone exact source/history comparison39/39 per arm/native0/token parity; sameSYSTEM/temperature0/repeat1.0/128output/4K/no cache. Genuine plain user-text and matched code-owned tool results both21/39 judged; two recall wins/two absence/social losses.
Reject adoption and additional integrated replay for zero aggregate gain. The initial control's unused shared tool declarations caused four literal tool-call replies; archive separately and compare actual plain-template control instead. Candidate has zero tool-text artifacts. This resolves the comparison defect, not a quality retry. No observer/source repair or per-question tuning.
Keep family/layout choice open and qualifiedcd60 baseline. Do not continue small prompt tuning without a changed material hypothesis; GemmaINT4/TRT export remains the next architecture build. Schema validity and fresh token accounting do not prove hybrid pause/resume, paging safety, sustained conversation, or final acceptance.
Evidence: bench/results/2026-10-09-p2-evidence-role-summary.json, candidate/control packets/results/judgments and archived run-owned scripts; reviews/20261009-140847-90295-review.md; research/architecture-choice.md/lessons.md. Fixed outcomes and targets stay unchanged.

## D115 2026-10-09: Use the verified native TensorRT wheel on Orin
Official0.11.0 cp312aarch64wheel447070745B/SHA9e6722a5 installed in isolatedJetsonexperiment; runtime.load selects jetson-orin-jp72-cu13-sm87 with aptTRT10.16.2.10(J/native0). Baselinecd60/current/previous/main unchanged. This is native loading qualification, not model inference or resource acceptance.
Choose one wheel-direct GemmaMTP/INT4AWQ build path; reject duplicateC++ONNX engines. Source supports externalizedint4FFN; firstengineprofile batch1/input2048/KV4096/draft&verify4 is U. Lead uses only immutable workflow; builder owns WSL prep, no unsupportedplatform patches.
WSLAQW remains active sameinvocation since13:37, first128activationpasscomplete14:00, parametersearchno firstimage/checkpoint at16:19. GPU99%/near10GB/unit8.24GB stable. Inspect actualmoduleloop/resourceoverhead before changing it; no deadline/restart or completedexportclaim.
Evidence: bench/results/2026-10-09-p2-trt-runtime-load.json/setupscript/journal/environment/tegrastats; officialsource95515c2; build/p2/logs/trt-report.md. Next actualnativeengine/reply after usablecheckpoint, with fit/pause/quality/latency/privacy targets still open.

## D116 2026-10-09: Fix quantization resources and native streaming assumptions
WSL originalAWQ has no checkpoint; three readonlystacks confirm eager_tensor_quant616/635 inGemmaMLP. Nativeextension fell back because installedninja lacked servicePATH. Actual1536×12288weights yield eagerFP32temporarylowerbound216MiB+36MiBprescaledFP16 versus~241MiBfreeGPU. NativeCUDAoutput36MiB avoids copies/scalar-hostbranches; pressure is predicted, no measuredpaging/deadlock/OOM claim.
Preserve originalunit/invocation/journal/kernel/stacks, markINTERRUPTED, then one resource-basedretry withownedninja/CUDA PATH and verifiedofficialCUDAextension, exactmodel/INT4AWQ/MMMU128 settings/newunit/log. Reject clock-basedabandonment, qualityretry, otherprojectGPUcleanup, or unsupportedplatformpatches. Stop/report nativecompilefailure before anotherroute.
PinnedTRTtemplate closes terminalassistant, so oldfirstphraseprefillresume cannot map. Select uninterruptednative streaming with qualifiedCUDAKokoro initially; delete oldpause/resume assumption, keep interruption/closecancellation. CPUKokoro remains alternative if actualfit/contention requires it; D66/D68 numbers do not establish newruntimeperformance.
Evidence: build/p2/logs/trt-report.md and diagnostics-stack-1625/-1626/-1629.txt; officialsource95515c2 tensor_quant_gpu.cu/chatTemplate.cpp; research/p2-briefs/trt-edge.md. Engine/replies/quality/latency/headroom/deletion remain unproven; productionbaseline unchanged.

## D117 2026-10-09: Keep official checkpoint-backed weight placement
First nativeGemma builder uses official default externalization, replacing D115's explicitint4_ffn restriction. Installedwheel WeightPolicy.from_request enables supported kinds; PLE externalization requires fp16, while the restriction would force full FP16 table load/scale/write. Preserve checkpoint-backed PLE/embeddings plus INT4FFN; no quantization or quality change.
Set batch1/input2048/KV4096/draft&verify4 and explicit single-image512total/per-image512(U). Read actualbuiltvisualconfig for the image upperbound, native text-template count plus image markers and output reserve. Reject an unproved512 estimate and unsupported imagecount API; nativecount accepts text only.
InstalledOrin native binding/API probe completesnative0/563ms(J), matching adapter request/stream/speculative constructor shapes. This is API qualification only; engine/inference/cancellation/fit remain pending. Retain qualifiedspeech and cd60 rollback.
Evidence: bench/results/2026-10-09-p2-trt-native-api.json/run/script; installedwheel0.11.0 experimental/builder/core/weight_policy.py99, artifacts/embeddings.py113/168, runtime_config.py435. Source copies under ignoredbuild/p2/inputs; no platformpatch or secondruntime route.

## D118 2026-10-09: Prepare the selected INT4 model on CPU
Second CUDAprep has kernel dxgkio_make_resident:-12 and firstactivationimage unchanged near10015MiB; nativeextension correction passed but fullFP16VLM residency remains. Astra164038 GO WITHCHANGES/native3 selects official--device cpu with unchanged models/MMMU128/INT4AWQ, not another model/calibration mechanism.
Reconcile and preserve secondrun; ifunchanged, stoponlyownedunit asINTERRUPTED. Freshnamedunit/GPUlock/22G cap writes checkpoints/int4-awq-cpu. Measure hostpeak/swap, skips, progress, exportintegrity, and nativeexit; stop unsupportedoperations/nonfinite/changedcoverage/resourceexhaustion/corruption/diagnosedstall, never elapsedtime alone. CPUfit/export remain U.
Reject customoffload/layerstreaming/duplicateONNX/calibrationreduction. Officialcatalog research establishes no readyE2B AWQ artifact in checkedsources; QATunquantized source is not AWQ. Preserve separateFP16assistant/nativeJetsonbuildonly/cd60/main. Nativeadaptercoding/checks continue independently; no answergain claimed.
Evidence: reviews/20261009-164038-48808-design.md; build/p2/logs/trt-native-retry; originalINTERRUPTED manifest/extension/nativeAPI receipts in bench/results; research/architecture-choice.md/lessons.md. D117 placement helpsenginepreparation, not quantizerfullmodel residency.

## D119 2026-10-09: Correct premature interruption using recovered progress
D118CPU decision was conditional on unchangedfirstimage. Latestreconciliation proves128/128 activationcompleted16:44:54/searchstarted16:44:58/nativeextensionloaded1.4s16:45:00. Buildercombined reconciliation+stop before assessing output, violatingcondition; unitad37 stoppednativeSIGTERM15/no checkpoint. Preserve INTERRUPTED, not nativefailedsearch.
Chooseone infrastructure retry of same correctedCUDA preparation, freshunit/invocation/log and exactmodels/MMMU128/INT4AWQ/verifiedextension/22G cap/GPUlock. Nativeextension AWQsearch has not been measured. Transientload dxg:-12 does not justify claiming stalledrun after actualcompleteactivation pass. This changes D118's nextdevice based newevidence, not a qualityretry.
KeepCPU route as resolvedfallback for concrete unsupported/resource/nonfinite/corruption/diagnosedsearchfailure. Readonlyreconciliation and any conditionalstop must be separatecommands with assessment between. No further clockstop or newmechanism; preserve qualifiedbaseline and ongoingadapterchecks.
Evidence: build/p2/logs/trt-interrupted-native with actualactivation/search/extensiontimestamps and nativeSIGTERMreceipt; reviews/20261009-164038-48808-design.md applies resourcefallback, its unchangedprogress premise was disproved beforestop. CPUroute remains unexecuted/U.

## D120 2026-10-09: Pause at the reviewed native implementation checkpoint
Dylan requests a clean checkpoint and handoff. Nativeadapter0e5a484 is committed/pushed on spike/p2-trt-edge after Sol67521 PASS102.05s/native0/fullchecks15.30s/hook14.98s. Fixed scene-change pair eviction and obsolete continuous child polling; source/deletion/cancellation checks pass. No modelengine/inference/adoption yet; baselinecd60/main remain unchanged.
Leave healthy WSLp2-trt-quantize-native-retry b9ec/flock128539/python128544 running; agent monitoring stops. Final16:56:16 receipt records tensors1951/1951 loaded, activationcache started16:53:40, unit8.481GB/swap0/GPU10004MiB; no completed sample/checkpoint. These E preparation snapshots establish no Jetson fit or paging safety.
Assistant bundle222033920B/SHA9da354befc24230d158db2d2687e376265a42687d091c1dc7754605a3a64bd35 verifies15 sourcefiles plus embeddedmanifest, exact revisions/Apache2model-card proof; baseweights excluded. Nextsession reconciles job/nativeexit/output, hashescheckpoint, builds Orin engines, then measures actual replies and existing workloads. Do not restart from staleSTATE or treat review/API compatibility as capabilityprogress.
Evidence: reviews/20261009-165443-67521-review.md; bench/results/2026-10-09-p2-trt-handoff* and assistant-metadata/bundle manifests; STATE.md/research/lessons.md. Prior26/47 judgedsplit and21/39 source-role tie remain rejected; all47 splitWAVs independently transcribe47/47/native0.

## D121 2026-10-09: Correct the recorded search timestamp
The archived ad37 journal records Searching parameters at16:44:54, not16:44:58 stated in D119. Nativeextension load remains16:45:00. This correction changes no outcome: activation completed, search started, and the operator prematurely interrupted before a checkpoint.
Evidence: bench/results/2026-10-09-p2-trt-interrupted-native/quantize-native.log; pause/handoff review20261009-170053-79168 PASS141.38s/native0 verifies21 receipt hashes, bundle16members/licensecards, and47/47 speech bindings. Superseded research wording is replaced; append-only decisions remain intact.

## D122 2026-10-09: Build a reusable Mac audio control interface
Dylan requests MacBook microphone/speaker interaction now and later, with Sol6.1/high builder. Select a loopback page over existing native sounddevice/TCP audio and SSH; all models/Edge stay on current qualified Jetson cd60. Start/Mute/Stop, explicit built-in devices, status/errors/levels; page load starts no capture.
Sol design192324 GO WITH CHANGES81.43s/native3 requires local Host/Origin/token controls, listening-marker readiness, fresh owned unit per Start, device qualification, bounded frames, monotonic paced mute/tail, and complete cleanup. Resolve during scoped build, no further planning gate. Native old-client cleanup is unqualified.
Reject browser PCM/WebSocket for added resampling/transport machinery and new dependencies. Preserve product/model/memory behavior, WSL quantizer, and existing workflow. Local lifecycle checks plus actual Jetson audio turn and opened page qualify the interface; human listening remains pending, no quality/physical-latency claim.
Evidence: research/mac-audio-interface.md; reviews/20261009-192324-33657-design.md; tools/talk.py/robot/audio.py/robot/main.py. Builder owns isolated spike/mac-audio-interface; lead owns review, deployment, and shared status.

## D123 2026-10-09: Qualify the reusable Mac audio interface
Sol 6.1 high replaces the old CLI audio loop with loopback controls and one owned native audio child. Exact MacBook devices, readiness, bounded framing, muted silence, and owned cleanup pass; all robot models and memory stay on cd60. WSL and main stay unchanged.
Twenty focused checks pass in 5.07s; full checks pass in 33.46s; Sol52230 review PASS135.83s. Actual acoustic recorded question, returned playback, Mute/Unmute, Stop, fresh Start, and warmup Stop pass. The page remains open and idle; human listening and all final acceptance targets remain pending.
Recorded TCP returns75,759 samples/3.156625s, independently transcribed as the embedded-Qdrant answer;1.205s input-end to complete phrase excludes physical playback. Reject browser audio machinery and further optional polishing. Carry launcher-timeout/mute-close races under D71.
Evidence: research/mac-audio-interface.md; bench/results/2026-10-09-mac-audio-{interface,transport}.json and paired journals/WAV/tegrastats; reviews/20261009-193528-52230-review.md; research/edge-cases.md. Current and previous remain cd60; all owned model jobs stop.

## D124 2026-10-09: Build the first complete robot interface prototype
Dylan expands the preview to camera, people/object detection, Edgy transcripts, and the rest of existing visitor capabilities. Continue with one Sol 6.1 high builder. Reuse D59/D72/D73 in-process view and D122 audio controls, adding transient live state rather than another runtime or persistent schema.
Show real camera overlays, robot state, user/reply text, and existing memory evidence. Keep anonymous person boxes, code-owned consent/deletion/actions, on-Jetson models/Edge, bounded UI history, token-protected loopback access, and clean Stop. No new model, framework, action API, or inference path.
Dylan owns live testing and explicitly prohibits the full suite. Apply this limit to builders, review commands, and commit hooks. Syntax and small changed-path checks are allowed; no automated audio replay/live detector run. Build the usable preview, review once, deploy through the existing workflow, and open it idle.
Evidence: research/mac-audio-interface.md; reviewed audio base dcb1e38/55c0ede; reviews/20261009-193528-52230-review.md. WSL remains untouched. Existing capability and final acceptance gaps remain visible.

## D125 2026-10-09: Keep the preview on the protected robot behavior
Read-only SHA comparison finds builder dcb1e38 runtime/config matches deployed cd60 except camera.py; lead copies exact cd60 camera source into builder. Coordinator still holds rejected F1 changes in main/brain/memory/things/text_embed. Never deploy that coordinator tree as-is for the UI.
Build and deploy the UI on the protected runtime plus minimal view/status wiring. Preserve rejected source in existing spike history, and remove its paths from the integrated preview. This changes no selected model, generation policy, evidence assembly, or acceptance target.
Dylan owns live testing; no full suite or replay is required for this source-integrity comparison. Keep cd60 as rollback and verify source/deployment bindings without loading models. No further planning pass.
Evidence: build/p2/logs/interface-cd60-source-hashes.json; protected release cd60be65ee79; builder dcb1e38; coordinator8eb5402. Source changes belong to the lead; one Sol high builder continues the UI.

## D126 2026-10-09: Leave the complete prototype ready for human testing
One Sol6.1/high builder adds live camera overlays, streaming real replies, bounded transcripts, status, supplied evidence, and existing audio controls. Three targeted checks pass1.43s/native0; Sol77868 PASS114.08s/native0. No full suite or automated live tests run, per Dylan.
Deploy the protected builder branch directly as b2b36d9718da, previouscd60 for rollback. Preserve rejected root F1 source with its matching tests instead of partial restoration. Post-deploy main/view/camera hashes match, and no qr unit runs. The page opens Idle with microphone off.
Dylan performs Start/Mute/Stop and capability testing. Camera reconnect and overlapping-turn display are optional carried gaps; evidence supplied does not prove generated grounding. No model adoption, physical latency, quality, or acceptance claim follows this preview.
Evidence: bench/results/2026-10-09-robot-interface-prototype.json; reviews/20261009-195203-77868-review.md; research/mac-audio-interface.md and edge-cases.md; spike/mac-audio-interface; local URL http://127.0.0.1:8765.

## D127 2026-10-09: Select visual memory explicitly and show verified names
Dylan confirms hiding tiny background detections and persisting only objects named or explicitly tracked. Show green object/person names after explicit object binding or fresh enrolled face matches, superseding D59 anonymous-only display. Consent and real deletion remain fixed.
Keep live perception temporary; reject unknown sighting and ordinary-turn image/caption writes. Keep conversation text and consented faces. Named visual crops retain provenance and deletion links; legacy unnamed history remains intact and outside automatic visual recall. No historical purge.
Use bounded idle work in the existing worker to publish labeled source frames, with anonymous live fallback during generation/staleness. Never carry person names by track ID. Reject tighter automatic history and stale name caching; no new model, module, runtime, or broad evaluation.
Evidence: Dylan live feedback and two explicit answers; research/mac-audio-interface.md; research/booth-ux.md verified missing Focus recognition wiring; protecteda7eeae3/currentb2b36d9718da. One design gate, scoped Sol6.1/high build, targeted checks/review, then human live test.

## D128 2026-10-09: Persist ignore rules separately from visual observations
Dylan clarifies that ignored kinds need persistent memory so Edgy remembers what to ignore. Retain existing Things ignore/unignore rule points across restart. These rules describe user preferences; ignored detections create no new visual evidence.
Object deletion removes the named object and linked visual evidence, while the independent class ignore rule remains until unignore. This clarification preserves the existing rule path and adds no schema, model, or architecture.
Evidence: Dylan explicit clarification; robot/things.py ignore/ignored on protected preview branch; D127 and research/mac-audio-interface.md. Include rule restart and no-visual-write checks in the scoped implementation.

## D129 2026-10-09: Separate live video from recognition display refresh
Dylan reports choppy video and blinking labels after D127; _shown holds old labeled frames, and skipped crop queries erase display names. Choose current tracked video with bounded object-only display hysteresis, keeping fresh source scores as sole write authority.
Keep person boxes anonymous on current frames; show the actual matched face crop and name in a finite-age inset. Never transfer identity by person track. Consent, deletion, ignore rules, thresholds, inference budgets, and models stay fixed.
Reject frozen labeled full frames; anonymous current video remains fallback. Scoped model-free regressions and one task review precede Dylan-owned physical qualification; no full suite or automated live experiments.
Evidence: Dylan live feedback; protected7a7f3db robot/main.py _shown/_preview and focus.py boxes; research/mac-audio-interface.md. This supersedes D127 full-frame display policy only.

## D130 2026-10-09: Preserve the visitor's explicit object name
Dylan says "Dylan's smartphone" but sees phone. _thing replaces recognized names with category aliases, and the parser excludes possessives. Preserve explicit object names separately from detector categories; use categories for matching/ignore, and consistent normalized lookup for recall/forget.
Accept possessive names in explicit teaching phrases without treating introductions or ordinary conversation as object enrollment. Keep existing category-based recall and persistent ignore preferences; do not guess historical renames.
Evidence: Dylan live feedback; protected7a7f3db robot/things.py _THING/_thing/command and Things.named; research/mac-audio-interface.md. Include varied names and persistence/deletion in the scoped model-free checks; no model or schema change.

## D131 2026-10-09: Reverify the explicit object name before competing aliases
A temporary real-Edge/stub-Robot sequence reproduces phone overriding a new "Dylan's smartphone" binding: both score1.0, and unrestricted nearest retrieval returns phone. This breaks the current naming flow.
Use the existing by-name query for a continuously tracked accepted name with the same crop embedding/query budget. Retain that RAM verification preference beyond display expiry; green display still expires after two seconds, and fresh scores alone authorize writes. Gaps, misses, conflicts, ignore, and deletion clear preference through existing Focus state.
Reject historical alias migration or extra inference/cache machinery; global matching resumes once the association clears. Evidence: research/mac-audio-interface.md and bench/results/2026-10-09-preview-display-names.json. Stop unfinished review74012/native130 before the material fix; review the corrected tree once.

## D132 2026-10-09: Ship the reviewed live-feedback update
D129-D131 and responsive/auto-scroll source1b9496b pass29 scoped checks and Sol87875 PASS. Dylan authorizes restart; deploy protected364d83474b31, previousc182, retainingcd60 and a closed-shard backup. Five changed runtime/UI hashes and19 protected unchanged paths match.
Reload original preview only and start one fresh session at Dylan's request. System unit qr-live-mac-b6cae9c835d3 is Listening; Dylan owns physical qualification. No full suite or automated live tests.
Evidence: bench/results/2026-10-09-preview-display-names.json; WSL same-job fresh progress in 2026-10-09-wsl-awq-restart-status.json. No architecture/model adoption or final-target claim.

## D133 2026-10-09: Read actual AWQ batch counters
Initial0/128 journal search entry is stale. Saved py-spy _calibrate_multimodal locals establish31/32 then43 then45 completed search batches, zero NaN skips; correct previous reports and receipts. Installed loop increments after each model forward and searches alpha candidates inside layers.
Preserve the same active job; reject first-batch stall inference from that log entry. Export/ETA remain unqualified. No model, calibration, service, or architecture change.
Evidence: bench/results/2026-10-09-wsl-awq-counter-status.json and corrections in live-progress/restart-status receipts; installed quantize.py836-850/model_calib.py1221-1239; raw locals ignored.

## D134 2026-10-09: Smooth boxes and require sustained focus priority
Dylan reports jumpy boxes, rapid unknown-focus changes, and a disconnected corner name card. Choose display-only smoothing and one second of the same raw-salience challenger; keep current focus while fit. Raw geometry retains crop/write/association authority.
Move exact face crop/name/source age into one bounded card beside immutable source face coordinates. Current person outlines stay anonymous; no identity follows a track. Clear on absence even when busy, and reject old in-flight sources after a gap.
Reject cached named live-body outlines and frozen matched full frames. Fixed-corner source card remains fallback. Models, budgets, thresholds, memory policy, consent, and deletion stay fixed; Dylan owns physical qualification.
Evidence: research/mac-audio-interface.md; peer overlay_reviewer; design34450 GO WITH CHANGES/native3, accepted conditions. No tree stamp because authorized smoothing landed during design; final task review must stamp complete frozen code.

## D135 2026-10-09: Ship the reviewed stable preview update
D134 sourcef2f3496 passes36 scoped checks11.20s/native0, peerreview PASS, and Sol45876 PASS177.34s/native0/tree23fa8244. Deploy protected1384f8a50c52 and verify27 source files plus19 unchanged protected paths; previous364d and retainedcd60 remain.
Stop only the owned prior session/server, back up closed shards, reload original Chrome1202942045, and restore Listening on qr-live-mac-b2b159dbd549.service with Macserver53156. No duplicate viewer, WSL mutation, full suite, or automated live acceptance test.
Physical smoothness/recognition remains Dylan-owned. Source-card placement and label-only continuity edges remain carried; no architecture/model adoption or final-target claim.
Evidence: bench/results/2026-10-09-preview-stable-boxes.json; reviews/20261009-214603-45876-review.md; research/mac-audio-interface.md and research/lessons.md.

## D136 2026-10-09: Separate recognition ownership from continuous display
D134 software checks pass but Dylan rejects live continuity, jitter, duplicated face card, and background filtering. Select independent serial recognition ownership, continuous object associations with200ms display-only dropouts and gap epochs, fresh-only writes, all unambiguous known labels plus one unknown focus, and640widthYuNet/exact-verified-frame name-only face display.
Reject recognition inside the detector loop, track-only person identity, copied face cards, and two-second object TTL. Configurable minside120 follows actual foreground green-capped bottle126-127px; confidence0.25 provisional. User selects persistent item-only ignore descriptors in existingThings, with filtered ordinary queries, restart-safe recall exclusion, and reachable restore; category-ignore remains separate.
Evidence: protected reviews/20261009-220711-70897-design.md Astra GO WITH CHANGES and221259-78941 Sol GO WITH CHANGES; recorded background/person clips private, source probes actual(J); research/mac-audio-interface.md. Microphone lacks detector candidates in60backgroundframes, so display changes alone cannot prove its recognition.

D136 common-flow clarification: the sole≥120px background object sits outside the teaching zone, so hard zone eligibility prevents normal learning. Treat held/zone placement as priority cues and allow one other stable eligible unknown. Preserve minimum, hold, challenger, source, and persistence rules; no scene coordinates or model override. Evidence: private background detector probe and Focus._fit source.

## D136 clarification 2026-10-09: Retain confirmed named tracks across confidence dips
Candidate1234 natural learning and persistent item ignore pass, but named coverage81% fails stability. Raw detector scores0.2379/0.2056 at frames4/133 erase the chosen name although geometry126/128px and the confirmed tracker continue.
Use existing DETECT_LOW0.10 for accepted-name continuity and fresh re-verification; DISPLAY_CONFIDENCE0.25 still admits unknown teaching focus. Preserve120px size, actual crop misses, gap/merge invalidation, fresh action/write authority, and model thresholds. Reject scene-specific exceptions or lowering unknown admission.
Evidence: bench/results/2026-10-09-liveview-repair.json; private d136-confidence-diagnostic.json, native0 with170backgroundframes. Two-phone fixture is misclassified wallet/bag; this is a detector gap, not evidence of simultaneous-label failure.

## D137 2026-10-09: Ship the reviewed common booth preview repair
D136 frozen1d77da passes Sol46346/native0 and27 final focused checks. Candidate623954f5cdb8 keeps bottle names85/85 versus47/87 baseline; actual item-ignore return/reset/recall, other-bottle allowance, and warm Restore pass(J). Independent recorded browser review passes source-face name placement, moving feed, and no copied card/tiny boxes.
Keep native1 extra fixture receipts: uncontrolled naming does not prove distinct bindings; a recorded chair crop overlaps a toy and its label disappears; exact ambiguity remains unqualified. Reject scene-specific fixes and another fixture sweep. All36 original final samples show latest known name plus one unknown; multiple distinct physical identities and continuous face jitter remain bounded limits.
Restore all222 production-memory files from the closed verified archive, retain replay-modified shards separately, and reopen only original preview Idle/mic off. Keep1384/cd60 and backups. WSL completion-only scheduled precheck is verified/enabled; another session owns subsequent export/engine/qualification.
Evidence: bench/results/2026-10-09-liveview-repair.json; reviews/20261009-231341-46346-review.md and20261009-d136-recorded-browser-review.md. No full suite, main merge, model adoption, or final-target claim.

## D138 2026-10-10: Apply current focus policy to source geometry
Dylan reports rapid focus alternation and an unwanted body outline. A tracker/shard regression proves the selector stays centered while verified frames reuse an older left focus. Snapshot policy-free source geometry and epochs, then apply current names/focus through one display route. Remove body drawing/style; retain internal person cues and exact-source face identity.
Twenty-nine scoped checks pass6.68s/native0(E), independent code review PASS, and Sol96960 PASS183.32s/native0/tree3a225f71. Deployed08ff2193ddc7 matches704 source hashes; one recorded browser review sees consistent laptop focus across named/unnamed face frames and no body outline(J). Sparse snapshots leave continuous physical jitter/cadence unqualified.
Reject selector threshold changes, identity caching, and scene rules. Models, inference/write budgets, raw crops, persistence, and source guards stay fixed. Retain replay memory separately, restore all223 CURRENT archived files, and reopen original preview Idle. Evidence: bench/results/2026-10-09-d138-focus-publication.json; reviews/20261009-235844-96960-review.md and20261010-d138-recorded-browser-review.md.

## D139 2026-10-10: Deliver completed face sources at detector cadence
Dylan rejects missing grey outlines, category-text flicker, phone coverage, and blinking names. Restore eligible neutral outlines/stable ??? and retain same-track names through size-only dips, keeping120px drawing/action/crop floors and fresh-source write authority.
Two completed-source prototypes fail frozen90% cadence: conversation7.58 then6.57 versus9.86fps(J). Astra79508 GO WITH CHANGES selects one15Hz existing-owner prototype, equal-capture upgrades only for identical anonymous frame objects, and corrected actual-publication/post-render-age evidence; crop3/s, priorities, source/gallery/gap/identity guards stay fixed.
Reject extra caches/flags, identity transfer, scene thresholds, and unchanged retries. Source-driven MJPEG is alternative; if this candidate fails, retain D138 with scoped grey/text/size fixes. Larger YOLOE-26s remains unadopted: physical teaching/Ignore commit persist, but movement88%, Restore87.33%, and ignored reset44/50 miss required checks(J); private clip splice also introduces an abrupt jump.
Evidence: bench/results/2026-10-10-d139-preview-delivery.json; research/mac-audio-interface.md; reviews/20261010-011157-79508-design.md. Third source tree342d36cd passes22scoped/native0; actual paired qualification and final task review remain pending.

## D139 outcome 2026-10-10: Keep current video and scoped object repairs
Corrected paired third prototype68114ad88ef5 completes/native0 but rejects adoption: person8.09vs9.83fps, conversation6.09vs9.63fps and52vs77 named sources(J). Person names145vs36 improve while phone104vs30 improves; this fails90% cadence and repeats exceed200ms.
Select Astra79508 fallback: D138 face/detection/owner publication with grey outlines, stable ???, and size-only name continuity. Preserve all failed source releases and private342d patch. No fourth publication tweak or relaxed threshold; source-driven delivery remains later architecture choice.
Keep larger detector unadopted until continuous teaching/motion/Ignore/reset/Restore and resources qualify. Correct only private held-frame continuation; preserve original and failednative1 receipts. Face delivery and detector coverage stay unmet at handoff.
Evidence: bench/results/2026-10-10-d139-preview-delivery.json; private corrected paired baseline/candidate with identicalbad59dc9 adapter; research/mac-audio-interface.md; reviews/20261010-011157-79508-design.md.

## D139 checkpoint 2026-10-10: Ship reviewed repairs and carry capability gaps
Product609b425 pushed; fallbackcc8b526812e5 verifies704source hashes. Sixteen scoped checks3.97s/native0, peerCODEPASS, and Sol7760 PASS190.35s/native0/treecab93927 approve only grey/text/size repairs. No full suite or overallbooth acceptance.
Corrected N/S phone runs bothnative1: N lacks heldphone detection; S physicalteaching/Ignore/Restorepersist pass but movement76.67%, Restore84%, and return/reset48/49 fail(J). Keep N default and S unadopted; carry detector, descriptor, and face delivery gaps without relaxed floors or scene fixes.
Native UI lifecycle/layout PASS only; preserve replay shards and restore all224freshCURRENT memory hashes. Reopen original previewIdle oncc8b, retain08ffrollback. Keep WSL same activejob/completionwatcher/ownedawakeprocess; pause at Dylan's requested handoff checkpoint.
Evidence: bench/results/2026-10-10-d139-preview-delivery.json; reviews/20261010-013644-7760-review.md and20261010-d139-recorded-browser-review.md; research/mac-audio-interface.md and research/lessons.md.

## D140 2026-10-10: Stabilize names and verify item-control crops
Keep accepted display confidence through bounded below-GUESS misses and enforce three-second unknown-target assignments across loss/recognition. Remove unused freeze/thaw. Fresh sightings still require current SURE matches; ambiguous duplicate names abstain.
Sol41450 FIX exposes stale descriptor Ignore; embed exact selected crop and verify chosen name before borrowing saved views. Unknown Ignore uses current crop only. Jetson then exposes RestorefocusNone after reset; guard RAM cleanup and preserve persisted deletion. Reject stored-name action authority and buffered unknown crops.
Paired unchanged S recording improves motion84→93.33% and restored75.33→90.67%(J), while moving Ignore remains failed. Repaired idle teaching/physical binding/Ignore/reset/Restore/reopen/cleanup pass8.48s after warmup/native0(J). Sol53747 and63548 PASS; independent60then26checks pass(E). Keep N default and all wider targets open.
Evidence: bench/results/2026-10-10-d140-detection.json; reviews/20261010-022300-63548-review.md. Preserve native1 queued-control failure and interrupted reset crash. Next measure explicit multiview retention and distinct same-kind replacements, then source-driven face delivery.

## D141 2026-10-10: Keep diverse explicitly verified object views
Select bounded diverse views in existing Edge MaxSim points: maximumthree after paired comparison, exactduplicate removal, original/current anchors, farthestcosine selection. Compare threediverse and currentreplacement; keep capturethree, DINO, MATCH, detector, and floor fixed. No background self-training.
Generic same-name teaching merges only after fresh exact-name MATCH; otherwise replace old physical-instance crops. Preserve firstcasing, unionaliases, everydeletionlink, and exact-normalized fallback to one eligible known track. Ignore retains complete selected gallery after currentcrop verification. Peer flags unconditionalmerge falselyrecognizing both old/new phones.
Sol85347 GO WITH CHANGES requires exactID, pending/duplicate/stale rejection, bounded actual belowSURE greenretention with existing counter, allpersistence/deletion regressions, and pairedJetson freshmatches/exclusion/falseclaims/resources. Select three: phone10/15vs7/15replacement; six11/15 onlyoneextra with zerosamekindphone negatives admitted. Cup92/142allvariants, qualitynative1; safetyunqualified.
Evidence: bench/results/2026-10-10-d141-multiview.json; Sol24860 PASS185.78s/tree97652d03; worker/peer78pass. Runtime94%movement, Ignoretarget ambiguity stopsactionsequence; native0adapterbug auditedfailure. Face/detector/paging/phonefalsepositive safety stayopen.
