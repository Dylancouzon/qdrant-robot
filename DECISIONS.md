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
