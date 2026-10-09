# Qdrant Edge Robot

This is an autonomous, AI-led project. **The rules in this file supersede Dylan's global CLAUDE.md** wherever they differ (Git, sub-agents, review gates, writing gates).

The lead may choose architectures, models, training approaches, cleanup, deployments, commits, and pushes within this product scope without asking. After a task, continue to the next unmet milestone. Ask Dylan only for physical intervention (cables, reflashing, hardware), new spending, credentials, or recovery beyond available access. Keep unmet targets visible.

Session-start reconciliation and edits to `STATE.md` and `DECISIONS.md` belong to the lead. Builders, researchers, and reviewers report discrepancies to the lead and never edit those two files.

A desktop robot that sees, listens, talks, and remembers, with every model and every memory on one Jetson Orin Nano Super 8 GB. Its memory is Qdrant Edge, the embedded Qdrant engine, inside the robot's own process. It is a conference-booth showcase: the reaction we want is "how does this run on a $249 board?"

## Session start (and after every compaction)

1. Read this file, then `STATE.md`, then the `DECISIONS.md` entries that the active task links.
2. Reconcile `STATE.md` with reality: `git status`, and on the Jetson the running jobs and the deployed release. Fix `STATE.md` first if it is wrong.
3. Read `research/` only for the topic of the active task.
4. Finish and review the active task before you start another. Commit only if the Git section of `STATE.md` allows it. Otherwise, leave the diff and evidence as a verified checkpoint and record it in `STATE.md`.

## Goal

Reach the capabilities of `refs/reachy-edge-memory` with no laptop: same idea, our own architecture. That demo stores memory on the robot but runs every model on a laptop over HTTP. We run all of it on the Jetson. Expect architecture changes: for example one process, GPU inference, one resident VLM, and no HTTP between components.

Capabilities to reach (from the reference README, "What to ask it"):

| Visitor says | Answered from |
| --- | --- |
| "What do you see?" | The camera, now |
| "What was on your left?", "What did I show you?" | Stored frames (image vector plus text vector on one point) |
| "What did we talk about?" | The conversation window, then the conversation memory shard through a `remember` tool |
| "Do you remember me?" | Face match against people (one point per person, several face shots as a multivector, MaxSim) |
| "What is Qdrant Edge?" | A knowledge shard that ships as a snapshot (facts with several question phrasings as a multivector) |

The robot has no motors. "Left" and "right" mean the left and right parts of the wide-angle frame.

Priority order when goals conflict: good answers, then fast answers, then camera fps, then search latency. Give the generative model as much memory as the rest allows. A Wikipedia knowledge shard is an add-on after M4, never at the cost of the core loop.

## Targets

Final targets for M4. Each milestone in `STATE.md` has its own interim numbers. M1 measures the first baselines. Change a target only through an evidence-backed `DECISIONS.md` entry; an unmet target stays visible in `STATE.md` until then.

| Metric | Target |
| --- | --- |
| Physical end of speech to first audible output (includes endpointing) | 1.2 s p50, 2.0 s p95 |
| Answer correctness on held-out `eval/` fixtures | 90% or more per capability; zero false identity claims on strangers |
| LLM decode (secondary to answer quality) | 30 tok/s or more |
| Detection and tracking while talking (not camera capture rate) | 15 fps or more, sustained |
| Qdrant Edge query | 10 ms p99 per shard |
| Peak RAM headroom with every component active | 500 MB minimum, aim for 1 GB; no swap during a turn |

## Hardware and machines

- **Robot:** Jetson Orin Nano Super 8 GB, headless, NVMe, USB camera (Arducam IMX291, about 100°), reachable over the network. Access details are in `STATE.md`. Keep SSH access working: never run the course robot's hotspot setup over the active Wi-Fi link.
- **Allowed additions:** anything the Jetson drives directly over USB, I2C, SPI, or GPIO: speaker, microphones, sensors, LEDs, displays, a thermal printer. No servos, no arms.
- **Mac (Apple silicon):** development, unit tests, dataset preparation, index builds, and training runs that need headroom. Build Jetson-specific engines on the Jetson, and measure every acceptance number on the Jetson. The product runs on the Jetson only.

## Approach

- Off-the-shelf models first. Fine-tune, distill, or train our own (for example a YOLO model) only when a benchmark shows the off-the-shelf option misses a target.
- Build a thin working loop early, then measure and replace parts. Do not run a broad model sweep before something works end to end. There is no separate testing phase: every milestone ships a robot a visitor can use.
- Pin `qdrant-edge-py` (0.8.0 at the start), model revisions, runtime versions, and preprocessing. Verify every Edge capability against the installed package's `.pyi` stubs, not against a skill or blog. The `qdrant:qdrant-edge` plugin skill is wrong about fusion: Edge fuses prefetches with `Fusion.Rrf` and `Fusion.Dbsf`.
- 0.8.0 has no `query_batch` and no `Memory` placement setting; both are on Qdrant `master` only. Building Edge from source is allowed if a benchmark justifies it.

## Fixed outcomes and open choices

Fixed (change only with Dylan): every model runs on the Jetson; memory lives in Qdrant Edge in-process; answers cite stored evidence; faces need explicit consent; "forget me" deletes for real; releases can roll back; runs are reproducible; unmet targets stay visible; answer quality comes first.

Open (the build decides by measurement): model family, runtime, process count, CPU or GPU placement, precision, detector cadence, training, and every item of the starting architecture below.

## Starting architecture (a hypothesis, not a rule)

Validated by research and Astra counsel on 2026-10-07 (D14). Replace any part that a measurement beats.

- **Brain:** one resident multimodal model takes the visitor's audio, the current frame, and retrieved memories, and streams text with tool calls. First candidate: Gemma 4 E2B at INT4 (NVIDIA lists audio, image, and text input). Fallback, swapping only this path: a streaming ASR (Moonshine) in front of Qwen3-VL-2B.
- **Perception:** YOLO26n on TensorRT FP16 with ByteTrack, about 10 fps, event-driven (embed only new or changed tracks and explicit "remember this" requests). Faces: YuNet for detection and landmarks, a small aligned-face embedder (EdgeFace or MobileFaceNet) on new faces or identity requests. A combined detector is a later training project, only if YuNet measurably misses.
- **Embeddings:** pooled SigLIP 2 vectors for object crops, frames, and text queries; bge-small for conversation and knowledge. Patch multivectors are deferred until a measured miss on similar objects.
- **Voice:** Silero VAD; streaming TTS (Kokoro) that emits short clauses with a maximum wait, faster than playback; interruption cancels the turn.
- **Scheduling:** bounded GPU tasks with speech first, detection deadlines, and deferred embedding writes. Capture runs independently and drops stale frames. Start CPU sessions at one thread and allocate by measured contention across the six cores.
- **Generation limits to start:** one active generation, 2,048-token context, bounded image tokens, 64 output tokens. Preallocate buffers and warm every path at boot.
- **Memory:** points carry timestamps, boxes, track IDs, and robot-relative regions. Tools run in code against Edge, validate arguments, and resolve times in code. Memory stores observed evidence, never generated recollections. Retention is bounded.

## Exploring without tunnel vision

- A design brief names at least two real alternatives and how each would be measured. A brief with one option gets RETHINK.
- A choice that moves a target is settled by a time-boxed bake-off: prototype the candidates on `spike/*` branches, measure them on the Jetson, merge the winner, record the loser in `DECISIONS.md`.
- Drop an approach after 90 minutes with no new evidence. After two failed approaches to one problem, run Astra counsel before a third.

## Roles

| Role | Who | When |
| --- | --- | --- |
| Lead | The main session (Opus) | Plans, decides, integrates, deploys; sole owner of `STATE.md`, `DECISIONS.md`, and shared configuration |
| Researcher | `researcher` subagent (Sonnet) | One question needed for the next decision. Never edits code. Two at most at once |
| Builder | `builder` subagent (Opus) | One scoped task from a written brief. One builder at a time |
| Design gate | Codex `gpt-6-sol`, `tools/gate.py design` | Once per architectural decision (model, runtime, process layout, data schema, new module), before building it. Not for reversible small steps |
| Task review | Codex `gpt-6-sol`, `tools/gate.py review` | Once per completed task, before it counts as done |
| Milestone review | Codex `gpt-6-astra`, `tools/gate.py milestone` | End of each milestone |
| Counsel | Codex `gpt-6-astra`, `tools/gate.py design --model gpt-6-astra` | After two failed approaches to the same problem, or an architecture-level doubt |

Subagents do not spawn subagents. The lead reads every builder diff before the review gate.

Brief a builder with: the task ID, the linked decisions, allowed paths, interfaces it must keep, acceptance checks, the machine it runs on (Mac or Jetson), and when to stop and report instead of building around a problem.

## Gates

`tools/gate.py <design|review|milestone> [--model <name>] "<what to judge, with paths and evidence>"` runs Codex read-only on this repo, saves the verdict to `reviews/`, and exits 0 only on a passing verdict (`GO`, `PASS`, `MILESTONE MET`). Exit 3 means act on the findings. Exit 124 means it timed out.

- **Design gate** asks: Is this the best solution? Is this the best way to build what we are trying to build? What would a strong edge-ML engineer do instead? What is the simplest version that meets the target? What can be deleted?
- **Review gate** checks correctness, performance, dead code, duplication, and whether the change is the smallest one that does the job.
- **Milestone gate** judges the milestone's own acceptance criteria, lists unproven final targets separately, and gives counsel on direction.

### Safety net (light by design)

Gates are mainly a habit, not a lock. One extra layer helps:

- `tools/githooks/pre-commit` (enable once per clone: `git config core.hooksPath tools/githooks`) runs `tools/gate.py checks`: ruff with a complexity limit of 10 (`ruff.toml`), vulture for dead code, and our tests. It blocks only when those fail, and prints the size delta.
- The same hook prints a reminder when no PASS review matches the staged code. It never blocks on that.
- `spike/*` branches are for free exploration; bring the winner to `main` with a review.

Resolve every blocking finding. To reject a finding, record the evidence in `DECISIONS.md`. Rerun a gate only after a material change, never to ask again about unchanged work. A better approach wins over sunk cost when evidence supports it, not on a reviewer's preference alone.

## Definition of done

A task is done when its acceptance checks pass, blocking findings are resolved, the code it replaces is deleted, the review gate passed, and `STATE.md` reflects reality.

## Keeping the repo clean

The repo must stay the cleanest, most optimized version of itself. Every task leaves the code smaller or clearer where it can.

- One way to do each thing. Delete the old path in the same change.
- No dead code, no compatibility shims, no commented-out code, no "for later" scaffolding.
- No abstraction that adds neither isolation nor testability. No config option for a value that never changes.
- Each module starts with one or two lines on what it is for.
- Non-trivial logic leaves one runnable check (a small `test_*.py` or an `assert`-based self-check).
- Everything in `refs/` is read-only reference. Copy an idea, not a file.

## Benchmarks and evaluation

- Define acceptance fixtures before choosing models. Keep development fixtures separate from held-out acceptance fixtures in `eval/`.
- Fixtures cover current sight, past frames (including left and right, and similar objects), conversation eviction and recall, people (including unknown people), knowledge, absent memories, restart, and deletion. Each case stores the expected evidence IDs and acceptable answers. Score retrieval and answer correctness separately.
- Each benchmark run writes `bench/results/YYYY-MM-DD-<what>-<run id>.jsonl` with: code revision or diff hash, machine, software and model versions, precision, context and image-token limits, dataset size, the command, sample counts, and percentiles.
- Separate cold start from warm turns. Per turn, record endpointing, ASR done, retrieval, first token, first audible output, and answer done. Milestone acceptance uses at least 100 representative turns and 1,000 queries per shard; smaller checks are fine while building.
- Log memory, swap, temperatures, and clocks (`tegrastats`) during every Jetson run. Peak headroom is measured with every component active.
- M4 needs held-out acceptance, all targets, offline cold start, restart persistence, deletion checks, and an eight-hour active run with no restart.

## Context hygiene

- `STATE.md` is the only status file. Rewrite it, do not append. Keep it under 120 lines. Before any delegation, remote change, compaction, or session end, it records: the active task and its acceptance checks, changed paths, unresolved findings, evidence paths, running jobs (host, directory, PID or service, command, log path), and the exact next command.
- `DECISIONS.md` is append-only. Each entry is five lines or fewer: date, decision, why, rejected alternatives, evidence path.
- `research/` holds one file per topic: summary first, sources last. Replace an outdated finding; do not stack corrections. Label numbers J (measured on an Orin Nano), E (measured elsewhere), or U (unverified).
- `reviews/` keeps gate verdicts (logs are ignored). Record the outcome in `DECISIONS.md` when it changes a decision.
- `research/lessons.md` logs every important lesson for future sessions (Dylan, 2026-10-09): each avenue explored with its outcome and decision link, each pitfall with its fix or workaround, and machine access and setup. Add to it as lessons happen, not only at the end; before any pause, compaction, or session end, check that the session's lessons are in it and that `STATE.md` links it. Replace an outdated lesson rather than stacking corrections.

## Mac-to-Jetson workflow

- Build one deploy, run, and collect workflow in the first task, and use only it afterwards.
- A release is identified by a hash of its source, including untracked files. Copy source and fixtures from the Mac to `/home/qdrant/qdrant-robot/releases/<hash>`. Models, memories, and logs live in `/home/qdrant/qdrant-robot/shared`.
- Create the venv on the Jetson with its system Python 3.12. Pin dependencies and save the full environment (`pip freeze`, CUDA, TensorRT, model revisions and checksums) with the release.
- Download models before offline tests. Record revision, checksum, preprocessing, and license per model.
- Run long jobs as named systemd units with bounded logs. Record unit, command, release, start time, and log path in `STATE.md`. Collect results to the Mac before review.
- Keep the previous release and a closed-shard backup until the new release passes acceptance. If health or acceptance fails, switch back.

## Recovery

- After reconnecting or a reboot, inspect boot ID, services, the deployed release, logs, and unfinished results before restarting anything. Mark interrupted runs as interrupted, never as complete. systemd restarts are bounded (for example `StartLimitBurst=3`).
- On OOM or throttling: keep the kernel log and `tegrastats`, then reduce concurrency or memory before retrying.
- On low disk: stop downloads and builds; delete only reproducible caches. Never delete memories, backups, or benchmark evidence.
- Lost SSH: retry with backoff for 15 minutes, keep doing Mac-side work, then record the blocker and ask Dylan.
- Before long work, record its timeout, disk estimate, and progress signal. Drop an approach after 90 minutes with no new evidence. Retry an infrastructure failure once, after diagnosis.

## Launch checklist (each autonomous session)

Verify Claude and Codex authentication, model selection, and remaining usage, and that `git config core.hooksPath` prints `tools/githooks`. Keep the Mac awake (`caffeinate -dimsu` in the background). Reconcile any still-running subagents before starting new ones.

## Tools and gotchas

- `codex exec` waits on stdin unless stdin is closed. `tools/gate.py` handles it; close stdin in any direct call.
- This workspace cannot read folders outside the repo (macOS sandbox). Keep references inside `refs/` (gitignored); their revisions are in `DECISIONS.md`.
- Writing style for docs and commit messages: plain, short sentences; "vector search engine", never "vector database".

## Git

Dylan gave standing approval (2026-10-07) to commit and push for this entire project. Commit each task after its review gate passes. Push when a remote exists. Commit messages: imperative subject, 5 to 10 words, with the `Co-Authored-By` footer.

## Secrets

The robot's sudo password is in `.env` as `ROBOT_SUDO_PASSWORD` (gitignored). Never write it into a tracked file, a log, or a commit. If passwordless sudo works, prefer it.

## Testing without a human

Most of the time no one is near the robot. Every capability must be testable from this Mac without a person:

- **Scripted sessions.** The runtime reads audio and frames from a source: live devices, or files. `eval/` sessions are scripts of steps (show this image, say this WAV, wait) with expected answers and evidence IDs. Replay them on the Jetson and score them.
- **Speech in.** Generate question WAVs on the Mac (`say -o q.aiff "..."`, then convert to 16 kHz mono WAV), and record real voices when Dylan is around. Keep both in `eval/`; synthetic voices alone overstate ASR quality.
- **Speech out.** Save every TTS answer as a WAV with timestamps. Score it by transcribing it on the Mac and comparing it with the expected answer and with the LLM's text.
- **Sight.** The robot's camera cannot be aimed by an agent. Use fixture images and recorded clips through the file source. Use the live camera only to check that capture, orientation, and fps work. The room lights may be off at night: check mean frame brightness first, and when the frame is dark, run fixture-based work and leave live-camera checks for when it is lit.
- **Live interaction during development.** Use the camera's microphone (on the Jetson) or a Mac client that streams Mac mic audio in and plays answers. Every model still runs on the Jetson. Report file-generation latency and Mac-transport latency separately.
- **Final acceptance (M4).** A Jetson-connected speaker and microphone, the Mac disconnected, offline cold start, full spoken interaction. Measure physical audible latency with an acoustic recording or an audio loopback.
- **Scoring.** Each replay command exits non-zero when any required step fails. It records ASR text, tool arguments, retrieved evidence IDs, answer text, output audio, and stage timestamps. Score retrieval and answers separately against the fixture. Transcribe output audio independently on the Mac; empty, truncated, or wrong speech fails.
- **Coverage.** Current and remembered left and right regions, similar objects, conversation eviction, absent memories, identity uncertainty, a new visitor replacing the last one, consent, restart, and deletion (verify after restart, including images and pending writes). Calibrate thresholds on development fixtures; freeze held-out fixtures before tuning.
- **Provenance.** Store generated captions and replies with their source evidence. A generated statement alone never counts as an observed fact.
- **Human test days.** When Dylan is at the robot, prepare a short checklist in `STATE.md` of what only a human can judge, and record each result as a fixture.
