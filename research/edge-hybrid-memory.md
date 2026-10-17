# Hybrid Edge memory session plan

Completed 2026-10-17 and rejected for the runtime (D209). Ranked exchange recall retrieved far better but did not answer better; the 2B model's use of quoted evidence and the speech-verb cue limit dialogue recall, not Qdrant retrieval. The rejected commit is tag `archive/hybrid-exchanges-2026-10-17`.

## Results

| Measurement | Time-ordered (main) | Fused dense and BM25 (DBSF) |
| --- | --- | --- |
| Gold exchanges beyond the live window, benchmark check half (E) | 6/13, top one never gold | 13/13, top one gold 12/13 |
| Gold exchange delivered, cued dialogue turns of `recall-long` (J) | 6/9 | 8/9 |
| `eval/dev/recall-long.jsonl` judged (J) | 62/87, 60/87 | 58/87, 61/87 |
| `eval/dev/demo.jsonl` paired (J) | 51/79 | 48/79 |
| Sealed `eval/validation/recall.jsonl` judged (J) | 25/55 | 23/55 |
| Fused exchange query on the Jetson, 3,000 queries (J) | | 2.17 ms p50, 3.67 ms p99 |
| Recorded voice judged; people checks judged (J) | 42/47; 22/34 | 42/47; 22/34 |

Dense alone matched the fused arms on this benchmark: the BM25 leg showed no measured gain. The bge query instruction prefix did not change the outcome. Time decay did not move corrected statements first (14 to at most 15 of 20 on the selection half, E), and statement traps scored 0.69 to 0.71, inside the gold range of 0.53 to 0.90, so no threshold separates them. With the gold exchange delivered, the robot still answered "I don't remember" or picked the wrong line in several turns. RAM headroom stayed at or above 886 MB, with up to 378 MB of swap held (J).

The design gate (RETHINK) showed that `UpdateOperation.create_dense_vector` and `create_sparse_vector` add named vectors in place; `update_vectors` backfills, and a `must_not HasVectorCondition` filter finds turns written without them. No migration is needed for a later schema change.


Dylan asked on 2026-10-17 for a best-in-class Qdrant Edge memory, run like the [memory demo session](overnight-conversation.md). The goal is better recall of what visitors said and what the robot answered, with no regression in the demo, privacy, deletion, or latency.

## Verified Edge 0.8.0 capabilities

Checked against the installed stubs and a Mac probe (E): built-in `Bm25` with the IDF `Modifier`; `Prefetch` legs fused with `Fusion.Rrf` and `Fusion.Dbsf`; a `Formula` that rescores fused results with `Decay` over a payload field; a `Text` payload index for `MatchText`; and `HasVectorCondition`. Loading an existing shard with a config that adds named vectors fails; the design gate found `create_dense_vector` and `create_sparse_vector`, which add them in place.

## Candidate design

1. (Superseded by the in-place APIs above; no migration ran.) Migrate `seen` once, preserving IDs, payloads, and existing vectors. Add a dense `dialog` vector (bge-small of question and answer) and a sparse BM25 `words` vector with IDF. Back up the closed live store first. Older releases can still open the shard.
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
