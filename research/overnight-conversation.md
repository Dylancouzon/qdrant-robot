# Memory demo session plan

Completed 2026-10-17. Results and kept changes are in the [conversation record](conversation.md#memory-demo-session-2026-10-17) and D207. Two-sentence replies were rejected (D208). The validation set's first use is spent.

Dylan set this scope on 2026-10-17; it replaces the earlier overnight conversation handoff. The demo shows on-device long-term memory with Qdrant Edge to developers. The robot must hold a quick, natural, multi-turn conversation, recall facts from earlier turns and from an earlier session, explain how its memory works, and start the right fixed-rule action from natural phrasing. Advice and general trivia are out of scope; the advice suite stays only as a regression guard.

## Fixtures

- Development: `eval/dev/demo.jsonl`, eight sessions, oracle text. Face scenes p05 to p07 and their strangers; images from `eval/dev/live/` and `m2-*`.
- Validation: `eval/validation/demo.jsonl`, four sessions, written by a separate Sonnet 5.5 author. Face scenes p08, p09, and `dev-stranger-p06-2`; `coco-*` images. The lead records only its hash and capability counts, never reads its questions or rubrics before the keep-or-reject decision, and counts its first use in `DECISIONS.md`. A later change inspired by its transcripts needs a new validation set.
- Regression guards: recorded voice (`sessions.jsonl`, 43/47 J), visual recall (`recall.jsonl`, 16/21 J), M3 people checks, and deletion.

## Metrics

Each spoken turn carries a capability: sight, object recall, personal recall, dialogue recall, session recall, memory explanation, action, privacy, or small talk. The main metric is embarrassing answers per session: wrong facts, false memories, prompt recitation, or empty praise. Report judged correctness per capability. False identity claims, wrong deletions, and privacy failures must stay at zero. First-audio latency must not rise beyond baseline variation.

## Changes, compared one at a time

1. Memory facts in the knowledge snapshot, verified against the code and Qdrant documentation. A collision check keeps personal and sight questions below the knowledge threshold.
2. Recall of earlier exchanges beyond the four-exchange window, fixing the two traced prototype faults: the broad past cue and unanswered history after a scene change.
3. At most two short spoken sentences within the existing 64-token budget (rejected, D208).
4. Wider general phrasing for a fixed-rule action only when a development miss shows it.
5. Personal-recall threshold only when baseline traces show irrelevant memories in answers.

## Guardrails against overfitting and drift

- Every runtime change is a general mechanism. The lead reviews each diff with one question: would it still work with different wording? Runtime code contains no fixture phrases; a grep over changed runtime files checks this.
- Each fix must also pass reworded variants written after the fix, outside the fixtures.
- Freeze the judge model, prompt, and contextual rubric before comparisons. Run the baseline twice and count only gains larger than its disagreement. Pair the final run with a fresh baseline.
- Workers edit only their assigned paths, never runtime code they were not given, and never the judge cache. The lead integrates and verifies every result.
- Stop and keep the stable release when evidence conflicts. Never rerun an unchanged quality failure.

## Jetson

Dylan granted the Jetson and the Mac for eight hours from 2026-10-17 02:30. The speaker stays at 0% during tests (mixer and `shared/speaker-volume`); restore 100% afterwards. Use isolated replay stores and no physical motion. Preserve live stores, backups, and release `6e8fd759c5d2` for rollback.
