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
