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
