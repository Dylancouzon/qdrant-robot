# Detailed project workflow

These instructions apply alongside CLAUDE.md. Read the sections required for the active operation. Paths in commands refer to the repository root.

## How to work


- Off-the-shelf first. Fine-tune, distill, or train only when a benchmark shows a miss.
- Build the runnable thing first, then measure. Do not prepare evaluations for hours before a candidate exists (D102).
- Before you try an approach, find its row through the index in `research/lessons.md`. Reopen it only with a named change and a paired comparison (D77).
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


`tools/gate.py <design|review|milestone> [--model <name>] "<what to judge, with paths and evidence>"` runs Codex read-only, saves the verdict to `reviews/`, and exits 0 only on `GO`, `PASS`, or `MILESTONE MET`. Exit 3 means act on the findings; exit 124 means timeout. The criteria are in [gates/design.md](../gates/design.md), [gates/review.md](../gates/review.md), and [gates/milestone.md](../gates/milestone.md).

- `tools/githooks/pre-commit` (enable once: `git config core.hooksPath tools/githooks`) runs ruff, vulture, tests, and module assertions. It blocks only on failure and reminds about a missing review (D17). Checks read the working tree: stage complete files, never partially staged bookkeeping, and never bypass the hook.
- Resolve every blocking finding, or reject it with evidence in the next gate brief (the verdict file keeps it). `DECISIONS.md` gets only the binding outcome. Rerun a gate only after a material change.
- Do not gate records-only changes (status, lessons, decisions text).

A task is done when its checks pass, blocking findings are resolved, replaced code is deleted, the review passed, and `STATE.md` is true.

## Records (lean, D149)


Records exist so the next session works well. Write each fact once, in the one place it belongs.

- **`STATE.md`:** under 50 lines. Active task and its steps, robot and running jobs (host, unit, log path), targets table, and the next command. Rewrite it; never add receipts, evidence hashes, or review IDs (release IDs are fine).
- **`DECISIONS.md`:** binding choices only. Add an entry (three lines or fewer) when a task changes the design or a rule, and for each counted held-out use. Append-only; a new entry names the one it supersedes. Reviews, receipts, scope notes, and corrections are not decisions.
- **`research/lessons.md`:** a short index into `research/experiment-ledger.md`. The ledger keeps one row per avenue tried, with outcome, status, and decision link, plus pitfalls and machine access. Update the row when an avenue concludes.
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
- **Live:** the robot hears and speaks through its own USB audio on the Jetson; `tools/talk.py` is only the monitor and controls, and the robot keeps running without it.
- **Human test days:** put a short checklist in `STATE.md` of what only a human can judge, and record each result as a fixture.
- **Physical tuning:** reuse one staged script with fixed limits and pass criteria. Ask Dylan for physical readiness and observations. Resolve conditional review findings with focused regressions. Repeat a design gate only when the design changes; run one task review when the change is complete. Keep checks, evidence, and torque-release verification in the script.

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
