# Qdrant Edge Robot

This is an autonomous, AI-led project. **The rules in this file supersede Dylan's global CLAUDE.md** wherever they differ (Git, sub-agents, review gates, writing gates).

A desktop robot that sees, listens, talks, and remembers, with every model and every memory on one Jetson Orin Nano Super 8 GB. Its memory is Qdrant Edge, the embedded Qdrant engine, inside the robot's own process. It is a conference-booth showcase: the reaction we want is "how does this run on a $249 board?"

The lead may choose architectures, models, training, cleanup, deployments, commits, and pushes within this scope without asking. After a task, continue to the next unmet target. Ask Dylan only for physical work (cables, reflashing, hardware), new spending, credentials, or recovery beyond available access.

## Session start (and after every compaction)

1. Read this file, `STATE.md`, and `research/lessons.md`. Then read the decisions and topic files the active task links.
2. Reconcile `STATE.md` with `git status`. Before remote work, check running jobs and the deployed release.
3. Read results with `python3 tools/results.py`. Open individual rows or logs only for the question at hand.
4. Finish and review the active task before you start another.

## Goal and priorities

Raise the capability ceiling for perception, sustained conversation, useful retrieval, and fluid interaction on one 8 GB Jetson (D76). Qdrant Edge is central to how the assistant remembers and uses evidence.

| Visitor says | Answered from |
| --- | --- |
| "What do you see?" | The camera, now |
| "What did I show you?", "Where is my phone?" | Stored captions, detector sightings, and named-object crop vectors |
| "What did we talk about?" | The conversation window and retrieved statements from Qdrant Edge |
| "Do you remember me?" | Face match against people (one point per person, face shots as a multivector, MaxSim) |
| "What is Qdrant Edge?" | A knowledge shard that ships as a snapshot (facts with question phrasings as a multivector) |

Priority when goals conflict: good answers, then fast answers, then camera fps, then search latency. Give the generative model as much memory as the rest allows. The robot has no motors and no left or right logic (D61). A Wikipedia shard is an add-on after M4.

## Targets

Targets are a floor, not the ceiling (D76). Change one only through a `DECISIONS.md` entry with evidence; unmet targets stay visible in `STATE.md`.

| Metric | Target |
| --- | --- |
| Physical end of speech to first audible output (includes endpointing) | 1.2 s p50, 2.0 s p95 |
| Answer correctness on held-out `eval/` fixtures | 90% or more per capability; zero false identity claims on strangers |
| LLM decode (secondary to answer quality) | 30 tok/s or more |
| Detection and tracking while talking | 15 fps or more, sustained |
| Qdrant Edge query | 10 ms p99 per shard |
| Peak RAM headroom with every component active | 500 MB minimum, aim for 1 GB; no swap during a turn |

M4 (booth-ready) needs held-out acceptance, all targets, offline cold start, restart persistence, deletion checks, a Jetson-connected speaker and microphone with the Mac disconnected, physical latency measured acoustically or by loopback, and an eight-hour run with no restart.

## Fixed outcomes and open choices

Fixed (change only with Dylan): every model runs on the Jetson; memory lives in Qdrant Edge in-process; answers cite stored evidence; faces need explicit consent; "forget me" deletes for real; releases can roll back; runs are reproducible; unmet targets stay visible; answer quality comes first.

Open (measurement decides): model family, runtime, process count, CPU or GPU placement, precision, detector cadence, training, and context and answer lengths.

## Current design

`DECISIONS.md` lists every binding choice. In short: Qwen3-VL-2B on llama.cpp with retrieval in code and code-owned actions and identity; YOLOE-26s TensorRT with tracking; DINOv2-small named-object multivectors; YuNet and w600k_r50 faces; Silero VAD, Parakeet int8, and Kokoro on CUDA with a first-phrase decode pause; 2,048-token context, 256 image tokens, and 64 output tokens. Generated captions and replies are stored with their source evidence; a generated statement alone never counts as an observed fact. Improve or replace any part when evidence supports it.

## Hardware and machines

- **Robot:** Jetson Orin Nano Super 8 GB, NVMe, USB camera (Arducam IMX291, about 100°), and a USB speaker with microphone (ALSA card `Device`, connected 2026-10-10). Never run the course robot's hotspot setup over the active Wi-Fi link.
- **Allowed additions:** anything the Jetson drives over USB, I2C, SPI, or GPIO. No servos, no arms.
- **Mac:** development, tests, data preparation, and training. **WSL 3080 box:** bake-offs and heavy preparation. Build Jetson engines on the Jetson; measure every acceptance number on the Jetson.
- Access details and pitfalls are in `research/lessons.md` (Machines).

## How to work

- Off-the-shelf first. Fine-tune, distill, or train only when a benchmark shows a miss.
- Build the runnable thing first, then measure. Do not prepare evaluations for hours before a candidate exists (D102).
- Before you try an approach, find its row in `research/lessons.md`. Reopen it only with a named change and a paired comparison (D77).
- A design brief names at least two real alternatives and how each is measured.
- Settle choices by paired comparison: a cheap local check first, then one integrated Jetson run after a material change. Prototype on `spike/*` branches.
- No deadlines (D83). Stop on evidence or resource limits. After two failed approaches to one problem, run counsel before a third.
- Pin `qdrant-edge-py` 0.8.0, model revisions, runtimes, and preprocessing. Verify Edge capabilities against the installed `.pyi` stubs. The `qdrant:qdrant-edge` skill is wrong about fusion: Edge fuses prefetches with `Fusion.Rrf` and `Fusion.Dbsf`.

## Roles

| Role | Who | When |
| --- | --- | --- |
| Lead | The main session | Plans, decides, integrates, deploys; sole editor of `STATE.md` and `DECISIONS.md` |
| Researcher | `gpt-6-luna` | One question for the next decision. Never edits code. Two at most at once |
| Builder | User-selected model, otherwise Opus | One scoped task from a written brief. One at a time unless paths and the Jetson are disjoint (D44) |
| Design gate | `tools/gate.py design` (gpt-6.1-sol) | Once per architectural decision (model, runtime, process layout, schema, new module) |
| Task review | `tools/gate.py review` (gpt-6.1-sol) | Once per completed task |
| Milestone review | `tools/gate.py milestone` (gpt-6-astra) | End of each milestone |
| Counsel | `tools/gate.py design --model gpt-6-astra` | After two failed approaches, or an architecture-level doubt |

Subagents do not spawn subagents. The lead reads every builder diff before review. A builder brief gives the goal, linked decisions, allowed paths, interfaces to keep, acceptance checks, the machine, and when to stop and report.

## Gates

`tools/gate.py <design|review|milestone> [--model <name>] "<what to judge, with paths and evidence>"` runs Codex read-only, saves the verdict to `reviews/`, and exits 0 only on `GO`, `PASS`, or `MILESTONE MET`. Exit 3 means act on the findings; exit 124 means timeout. The criteria are in [gates/design.md](gates/design.md), [gates/review.md](gates/review.md), and [gates/milestone.md](gates/milestone.md).

- `tools/githooks/pre-commit` (enable once: `git config core.hooksPath tools/githooks`) runs ruff, vulture, tests, and module assertions. It blocks only on failure and reminds about a missing review (D17). Checks read the working tree: stage complete files, never partially staged bookkeeping, and never bypass the hook.
- Resolve every blocking finding, or reject it with evidence in the next gate brief (the verdict file keeps it). `DECISIONS.md` gets only the binding outcome. Rerun a gate only after a material change.
- Do not gate records-only changes (status, lessons, decisions text).

A task is done when its checks pass, blocking findings are resolved, replaced code is deleted, the review passed, and `STATE.md` is true.

## Records (lean, D149)

Records exist so the next session works well. Write each fact once, in the one place it belongs.

- **`STATE.md`:** under 50 lines. Active task and its steps, robot and running jobs (host, unit, log path), targets table, and the next command. Rewrite it; never add receipts, evidence hashes, or review IDs (release IDs are fine).
- **`DECISIONS.md`:** binding choices only. Add an entry (three lines or fewer) when a task changes the design or a rule, and for each counted held-out use. Append-only; a new entry names the one it supersedes. Reviews, receipts, scope notes, and corrections are not decisions.
- **`research/lessons.md`:** one row per avenue tried, with outcome, status, and decision link; plus pitfalls and machine access. Update the row when an avenue concludes. This is how we avoid repeating failed work.
- **`research/<topic>.md`:** how the current system works, one file per topic. Summary first. Replace outdated text; move superseded plans to `research/archive/`.
- **`research/edge-cases.md`:** known gaps (D71).
- **`reviews/`:** gate verdicts. **`bench/results/`:** one result file per run. Private media, voices, and raw logs stay in gitignored `build/`.
- Each task commit carries its own record updates. No records-only commits except a session handoff. Archive tags only when retiring a branch with unmerged work.
- Write records in full plain sentences. Label numbers J (measured on our Jetson), E (elsewhere), or U (unverified).

## Evaluation

- Keep development fixtures separate from held-out fixtures in `eval/`. Freeze held-out fixtures before tuning, and count every held-out use in `DECISIONS.md`.
- Fixtures cover current sight, past observations, similar objects, conversation recall, people (including strangers), knowledge, absent memories, restart, and deletion. Each case stores expected evidence IDs and acceptable answers. Score retrieval and answers separately.
- Each run writes `bench/results/YYYY-MM-DD-<what>-<run id>.jsonl` with the code revision, machine, versions, limits, command, sample counts, and percentiles. Log `tegrastats` during every Jetson run.
- Milestone acceptance uses at least 100 representative turns and 1,000 queries per shard; smaller checks are fine while building.
- Per turn, record endpointing, ASR done, retrieval, first token, first audio, and answer done. Separate cold start from warm turns.
- `correct` in raw replays is a keyword heuristic; `.judged.jsonl` holds judged scores (three votes, cached). Missing judgments are failures, never passes.
- Oracle text, synthetic speech, recorded voice, and live interaction answer different questions. A synthesized first phrase is not physical audible latency. Short turns do not prove long-conversation quality.
- A fix must hold beyond the development steps it flips (review rule 6).

## Testing without a human

- **Scripted sessions:** `eval/` steps (show this image, say this WAV, wait) replay on the Jetson through file sources and score themselves. A replay exits non-zero when a required step fails.
- **Speech in:** synthetic WAVs from `say` (16 kHz mono) plus Dylan's recorded voice; synthetic voices alone overstate ASR quality.
- **Speech out:** save every TTS answer as a WAV and transcribe it independently on the Mac; empty, truncated, or wrong speech fails.
- **Sight:** use fixture images and recorded clips. Use the live camera only for capture, orientation, and fps checks; check frame brightness first because the room may be dark.
- **Live:** `tools/talk.py` streams Mac audio to the Jetson. Report Mac transport latency separately.
- **Human test days:** put a short checklist in `STATE.md` of what only a human can judge, and record each result as a fixture.

## Mac-to-Jetson workflow

- `tools/jetson.py` deploys, runs, and collects; use only it. A release is a hash of its source, copied to `/home/qdrant/qdrant-robot/releases/<hash>`. Models, memories, and logs live in `shared/`.
- The Jetson venv uses system Python 3.12 with pinned dependencies; each release saves its environment. Download models before offline tests and record revision, checksum, preprocessing, and license per model.
- Run long jobs as named systemd units with bounded logs, and record them in `STATE.md`. Collect results to the Mac before review.
- Keep the previous release and a closed-shard backup until a new release passes. Switch back if health or acceptance fails.

## Recovery

- After a reconnect or reboot, inspect the boot ID, services, deployed release, logs, and unfinished results before restarting anything. Mark interrupted runs as interrupted.
- On OOM or throttling, keep the kernel log and `tegrastats`, then reduce concurrency or memory before retrying. Retry an infrastructure failure once, after diagnosis; never retry a quality failure unchanged.
- On low disk, delete only reproducible caches. Never delete memories, backups, or benchmark evidence.
- Lost SSH: retry with backoff for 15 minutes while doing Mac work, then record the blocker and ask Dylan.

## Session checklist

Verify Claude and Codex authentication and usage, and that `git config core.hooksPath` prints `tools/githooks`. Keep the Mac awake (`caffeinate -dimsu`). Reconcile running subagents before starting new ones. `codex exec` waits on stdin unless it is closed; `tools/gate.py` handles that. This workspace cannot read outside the repo; keep references in `refs/` (gitignored, revisions in D7).

## Git and secrets

Dylan gave standing approval (2026-10-07) to commit and push for this project. Commit each task after its review passes. Commit messages: imperative subject, 5 to 10 words, with the `Co-Authored-By` footer. Docs and commits use plain, short sentences and "vector search engine", never "vector database".

The robot's sudo password is in `.env` as `ROBOT_SUDO_PASSWORD` (gitignored). Never write it into a tracked file, a log, or a commit.

## Keeping the repo clean

- One way to do each thing; delete the old path in the same change.
- No dead code, compatibility shims, commented-out code, or "for later" scaffolding.
- No abstraction without isolation or testability; no config option for a value that never changes.
- Each module starts with one or two lines on what it is for. Non-trivial logic leaves one runnable check.
- `refs/` is read-only reference. Copy an idea, not a file.
