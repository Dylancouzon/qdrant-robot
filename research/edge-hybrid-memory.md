# Hybrid Edge memory session plan

Dylan asked on 2026-10-17 for a best-in-class Qdrant Edge memory, run like the [memory demo session](overnight-conversation.md). The goal is better recall of what visitors said and what the robot answered, with no regression in the demo, privacy, deletion, or latency.

## Verified Edge 0.8.0 capabilities

Checked against the installed stubs and a Mac probe (E): built-in `Bm25` with the IDF `Modifier`; `Prefetch` legs fused with `Fusion.Rrf` and `Fusion.Dbsf`; a `Formula` that rescores fused results with `Decay` over a payload field; a `Text` payload index for `MatchText`; and `HasVectorCondition`. An existing shard rejects new named vectors, so new vectors need a migration to a new shard that keeps point IDs.

## Candidate design

1. Migrate `seen` once, preserving IDs, payloads, and existing vectors. Add a dense `dialog` vector (bge-small of question and answer) and a sparse BM25 `words` vector with IDF. Back up the closed live store first. Older releases can still open the shard.
2. Exchange recall: dense and BM25 prefetches under the visitor filter, fused with RRF, rescored by a formula with exponential time decay. This replaces time ordering.
3. Statement recall: the same hybrid query restricted to points with a statement vector; the decay favors corrections.
4. Object deletion: `MatchText` filters on text indexes replace the client-side regex scan.
5. Knowledge stays on MaxSim; its word-for-word threshold relies on calibrated cosine scores.

Each step is compared against the current main release on its own.

## Measurements

- Retrieval benchmark on the Mac, no LLM: planted conversations with gold source IDs and irrelevant-memory traps, split into selection and check halves before measuring. Metrics: recall at the delivered limit, mean reciprocal rank, and irrelevant delivery. Arms: current, dense with decay, hybrid RRF, hybrid DBSF, hybrid RRF with decay.
- Development dialogue: `eval/dev/recall-long.jsonl`, long conversations whose recall targets sit six to 12 turns back, with corrections, exact names, vague topic questions, and traps.
- Sealed validation: `eval/validation/recall.jsonl`, written by a separate Sonnet author and unread by the lead until the keep-or-reject entry.
- Regression guards: `eval/dev/demo.jsonl` (49/79 paired, J), recorded voice (42/47, J), people checks (22/34, J), deletion tests, and Edge query p99 at most 10 ms on the Jetson.

## Guardrails

The guardrails of the [memory demo plan](overnight-conversation.md#guardrails-against-overfitting-and-drift) apply unchanged: general mechanisms only, a fixture-phrase grep, reworded checks outside fixtures, a frozen judge, two baseline runs, paired scoring with `bench/paired.py`, zero privacy failures, and a design gate before the schema change. The Jetson speaker stays at 0% during tests.
