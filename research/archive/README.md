# Archive

These files preserve superseded plans and completed experiments. The decision and lesson snapshots cover history through 2026-10-10; later reports carry their own dates. Use [current topics](../README.md) for the robot, [lessons](../lessons.md) for outcomes, and [decisions](../../DECISIONS.md) for binding choices.

- `decisions-2026-10-10.md`: every decision D1 to D148 plus the 2026-10-10 session entries.
- `lessons-2026-10-10.md`, `lessons-index-2026-10-10.md`: detailed lessons through the Gemma comparison.
- `experiments.md`, `experiment-heads-20261010.json`: archive tags for retired branches.
- Design briefs and plans: `m1-slice-design.md`, `m2-design.md`, `m3-design.md`, `v1-plan.md`, `assistant-design.md`, `capability-plan.md`, `concepts.md`, `memory-and-booth.md`, `answer-evidence.md`, and `recognition-import-plan.md`.
- Topic reports: `models.md`, `sight.md`, `endpointing.md`, `grounding.md`, `gemma-fit.md`, `jetson-trt.md`, and `one-voice.patch` (the rejected retrieval-into-brain path).

## Conversation trials, 2026-10-15

The [trial report](conversation-trials-2026-10-15.md) preserves all measurements, qualification rules, resource limits, reproduction notes, and review receipts. [Current conversation guidance](../conversation.md) records the retained release, exact regressions, and next steps.

| Rejected prototype | Patch | Base commit |
| --- | --- | --- |
| Preserve nonvisual history | [History](conversation-history.patch) | `23d1430` |
| Usefulness-first instruction | [Prompt](conversation-prompt.patch) | `23d1430` |
| Two counted spoken statements | [Reply budget](conversation-budget.patch) | `23d1430` |
| Store and quote both sides | [Dialogue v1](dialogue-v1.patch) | `314645d` |
| Reuse the retrieval instruction | [Dialogue v2](dialogue-v2.patch) | `314645d` |

## Evidence from earlier archive tags

Many archived paths under `bench/results/` and `reviews/` left main on 2026-10-10. Read them from the pre-cleanup tag:

```sh
git show archive/2026-10-10/pre-cleanup:bench/results/<file>
git ls-tree -r --name-only archive/2026-10-10/pre-cleanup bench/results reviews
```

The Jetson keeps the same results in `shared/results-archive-20261010/`.

## File index

- [edge-sdk-notes-2026-10-07.md](edge-sdk-notes-2026-10-07.md)
- [answer-evidence.md](answer-evidence.md)
- [assistant-design.md](assistant-design.md)
- [capability-plan.md](capability-plan.md)
- [concepts.md](concepts.md)
- [conversation-budget.patch](conversation-budget.patch)
- [conversation-history.patch](conversation-history.patch)
- [conversation-prompt.patch](conversation-prompt.patch)
- [conversation-trials-2026-10-15.md](conversation-trials-2026-10-15.md)
- [decisions-2026-10-10.md](decisions-2026-10-10.md)
- [dialogue-v1.patch](dialogue-v1.patch)
- [dialogue-v2.patch](dialogue-v2.patch)
- [edge-case-records-2026-10-15.md](edge-case-records-2026-10-15.md)
- [endpointing.md](endpointing.md)
- [experiment-heads-20261010.json](experiment-heads-20261010.json)
- [experiments.md](experiments.md)
- [gemma-fit.md](gemma-fit.md)
- [grounding.md](grounding.md)
- [interface-checks-2026-10-16.md](interface-checks-2026-10-16.md)
- [jetson-trt.md](jetson-trt.md)
- [lessons-2026-10-10.md](lessons-2026-10-10.md)
- [lessons-index-2026-10-10.md](lessons-index-2026-10-10.md)
- [m1-slice-design.md](m1-slice-design.md)
- [m2-design.md](m2-design.md)
- [m3-design.md](m3-design.md)
- [memory-and-booth.md](memory-and-booth.md)
- [models.md](models.md)
- [one-voice.patch](one-voice.patch)
- [recognition-import-plan.md](recognition-import-plan.md)
- [sight.md](sight.md)
- [v1-plan.md](v1-plan.md)

The [enclosure fit record](enclosure-fit-checks-2026-10-16.md) preserves earlier assembly concerns after Dylan confirmed assembly.

The [branch reconciliation](branch-reconciliation-2026-10-16.md) records the preserved branch tips and local print session.

The [mounted servo trial report](mounted-servo-trials-2026-10-16.md) preserves calibration recovery, staged travel, speed comparisons, rejected measurements, and historical procedures. Use [current head control](../servo.md) for operation.

The [mounted servo evidence manifest](mounted-servo-evidence-2026-10-16.json) maps 13 complete raw traces to tag `archive/2026-10-16/mounted-follow-trials`. Current result files retain compact summaries. Read a complete original with `git show archive/2026-10-16/mounted-follow-trials:bench/results/FILENAME`.
