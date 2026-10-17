# Qdrant Edge Robot

This autonomous project uses this file in preference to Dylan's global CLAUDE.md where they differ. The lead may implement, test, deploy, commit, and push within project scope. Ask Dylan for physical work, new spending, credentials, or recovery beyond available access.

Keep the architecture stable. Focus on cleanup, observed quirks, interaction, and remaining acceptance work. Reopen architectural choices only for a measured failure or Dylan's request.

## Start with a small context

1. Read this file, STATE.md, and the short [lessons index](research/lessons.md), including after compaction.
2. Reconcile STATE.md with `git status`. Finish the active task before starting another.
3. Use the [topic index](research/README.md) to open only files relevant to that task. Search relevant decision IDs before reading their entries.
4. Use `python3 tools/results.py` for evidence summaries. Open individual result rows and logs only for the question at hand.

Keep STATE.md under 50 lines. It contains the current task, release, running jobs, target status, and next command. Put trial history, review receipts, and implementation details in indexed topic files. Load archives and full ledgers only for a specific question.

## Fixed outcomes

Every model runs on the Jetson. Qdrant Edge stores memory inside the robot process. Answers cite stored evidence. Face enrollment needs explicit consent. "Forget me" deletes linked data. Releases can roll back. Runs are reproducible. Unmet targets stay visible. Answer quality comes first. Change these outcomes only with Dylan.

Generated replies and captions retain their source evidence. A generated statement alone never counts as an observed fact. Qdrant is a vector search engine.

## Targets

Targets are a floor (D76). Change one only through an evidenced DECISIONS.md entry. Good answers take priority over latency, camera rate, and search latency.

| Metric | Target |
| --- | --- |
| Physical speech end to first audible output, including endpointing | 1.2 s p50, 2.0 s p95 |
| Held-out answer correctness | At least 90% per capability; zero false identity claims on strangers |
| LLM decode (soft, D160) | At least 30 tok/s |
| Detection and tracking while talking | At least 15 fps, sustained |
| Qdrant Edge query | At most 10 ms p99 per shard |
| Peak RAM headroom with every component active | At least 500 MB, aim for 1 GB; no swap during a turn |

M4 requires all targets, held-out acceptance, offline cold start, restart persistence, deletion checks, independent Jetson audio, measured physical latency, and eight hours without restart.

## Load operating instructions when needed

The [detailed workflow](research/workflow.md) remains binding. Read the applicable sections before these operations:

| Operation | Required guidance |
| --- | --- |
| Code, experiments, or delegation | [Work rules](research/workflow.md#how-to-work), [roles](research/workflow.md#roles), [gates](research/workflow.md#gates), and [code hygiene](research/workflow.md#keeping-the-repo-clean) |
| Evaluation or acceptance | [Evaluation](research/workflow.md#evaluation) and [scripted testing](research/workflow.md#testing-without-a-human) |
| Jetson access, deployment, or recovery | [Machine notes](research/experiment-ledger.md#machines), [deployment](research/workflow.md#mac-to-jetson-workflow), and [recovery](research/workflow.md#recovery) |
| Commits or record updates | [Records](research/workflow.md#records-lean-d149), [gates](research/workflow.md#gates), and [git and secrets](research/workflow.md#git-and-secrets) |
| Session setup | [Session checklist](research/workflow.md#session-checklist) |

Use only tools/jetson.py for the Mac-to-Jetson workflow. Inspect running jobs and the deployed release before remote work. Preserve memories, backups, and benchmark evidence. Never run hotspot setup over the active Wi-Fi link.

Pin qdrant-edge-py 0.8.0 and the model, runtime, and preprocessing revisions. Verify Edge capabilities against installed stubs. Edge fuses prefetches with Fusion.Rrf and Fusion.Dbsf.

Keep one implementation per operation and preserve necessary regression coverage. Never bypass the pre-commit hook, which runs lint and dead-code checks. Run relevant task tests before review, and full checks before a release or milestone. Reuse unchanged passing results. Resolve blocking review findings before completion. The robot sudo password stays in gitignored .env and never enters tracked files or logs.
