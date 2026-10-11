# Archive

These files describe superseded plans, completed experiments, and the full decision and lesson history up to 2026-10-10. They do not describe the current robot. Use [../lessons.md](../lessons.md) for outcomes and [../../DECISIONS.md](../../DECISIONS.md) for binding choices.

- `decisions-2026-10-10.md`: every decision D1 to D148 plus the 2026-10-10 session entries.
- `lessons-2026-10-10.md`, `lessons-index-2026-10-10.md`: detailed lessons through the Gemma comparison.
- `experiments.md`, `experiment-heads-20261010.json`: archive tags for retired branches.
- Design briefs and plans: `m1-slice-design.md`, `m2-design.md`, `m3-design.md`, `v1-plan.md`, `assistant-design.md`, `capability-plan.md`, `concepts.md`, `memory-and-booth.md`.
- Topic reports: `models.md`, `sight.md`, `endpointing.md`, `grounding.md`, `gemma-fit.md`, `jetson-trt.md`, and `one-voice.patch` (the rejected retrieval-into-brain path).

Many archived paths under `bench/results/` and `reviews/` left main on 2026-10-10. Read them from the pre-cleanup tag:

```sh
git show archive/2026-10-10/pre-cleanup:bench/results/<file>
git ls-tree -r --name-only archive/2026-10-10/pre-cleanup bench/results reviews
```

The Jetson keeps the same results in `shared/results-archive-20261010/`.
