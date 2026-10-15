# General conversation

The accepted release keeps the existing model, retrieval, conversation window, and reply policy. Three policy changes and one installed-model comparison failed the frozen adoption criteria. No conversation change has been adopted from this comparison.

## Paired development comparison, 2026-10-15

The Jetson ran 18 typed turns across six topics, plus six transfer turns about desk organization and language practice. The sessions include follow-ups after scene changes, corrections, topic changes, and conversation-window turnover. Every arm uses its own generated replies. These are development checks, not held-out acceptance.

`bench/conversation.py` adds the actual preceding dialogue to each frozen rubric and calls the existing three-vote, cached judge. Empty keyword lists provide no correctness measurement. The fixture copies were verified byte-for-byte; result summaries retain their original `source_cases` and the fixture SHA-256.

| Arm | Development, judged | Transfer, judged | Outcome |
| --- | --- | --- | --- |
| Accepted baseline, `f9b90b958023` | 7/18 | 2/6 | Retained |
| Preserve nonvisual replies, `7d17b2e539ba` | 6/18 | Not run | Rejected |
| Usefulness-first instruction, `66cb234f594c` | 9/18 | 1/6 | Rejected |
| Two counted statements, `fadd74bebf31` | 12/18 | 2/6 | Rejected |
| Installed Qwen3.5-2B, original policy | 6/18 | 2/6 | Rejected |

All measurements are J. The two-statement version gave more practical help, but newly suggested an outdoor activity after an indoor preference. Transfer performance did not improve. The prompt-only version also lost that preference and performed worse on transfer. Preserving generated replies made several exchanges repetitive.

Adoption required at least two additional judged development passes across two topics, no new correction or topic-change failures, and no transfer regression. Recorded-voice, speech-output, privacy, and visual-claim checks also precede adoption. The statement budget alone failed the correction requirement. The recorded regression scored 44/47 judged, 44/47 keyword, and 5/5 retrieval, with synthesized first audio at 1.773 s p50 (J). The unit reported 57.7 MB peak swap. These results do not reverse the correction failure.

## Reply and evidence limits

The existing counter counts statements with at least six words. Questions and shorter statements are exempt. The experimental limit therefore permits two counted statements, rather than enforcing two literal sentences. The experiment kept 64 output tokens and explicitly retained one counted statement for captions. The cutoff, pause/resume, exhausted-budget, and caption-limit checks passed.

Independent transcription matched the two-statement version's 18 development answer WAVs. All six transfer answer WAVs also matched. Recorded speech matched 46/47 answers; the checker rejected the known proper-name transcription, "Metrocentre via Bens" versus "Metro Center via Benz". The threshold remains unchanged. These checks compare synthesized speech with answer text. They do not establish factual correctness or physical audible latency.

The failures show weak use of corrections and topic changes even when context is supplied. They do not establish an inherent model ceiling. Longer replies also add opportunities for unsupported claims. Remaining work should address general dialogue control, with varied conversations and unchanged evidence requirements.

## Reproduction and evidence

Fixtures: `eval/dev/conversation.jsonl` and `eval/dev/conversation-transfer.jsonl`. Run them through `tools/jetson.py run` and `eval.replay --oracle` with isolated test memories. Score with `python -m bench.conversation RESULT CASES`. The synthetic fixture WAVs are available for separate audio-input checks.

The `2026-10-15-conversation-*replay-*.jsonl` files and their judged sidecars preserve the runs. Matching tegrastats files preserve resource samples. Use `python3 tools/results.py` for compact summaries. Raw journals and original collected files stay in `build/`.

The three patches in `research/archive/conversation-{history,prompt,budget}.patch` preserve the prototypes against commit `23d1430`. The design and counsel verdicts are in `reviews/`. The [task review](../reviews/20261015-194002-22778-review.md) approves the evaluation and records. Short dialogues establish neither sustained conversation, paging safety, stranger acceptance, nor M4.

## Installed-model comparison

One isolated trial compares installed Qwen3.5-2B with accepted Qwen3-VL-2B on the same 24 typed turns. The original prompt, statement limit, 64-token output budget, retrieval, and source stay unchanged. The measured correction failures justify reopening D27 under D77 on the current recall and comparison pipeline. The production default stays unchanged until every frozen check passes.

The older Qwen3.5 ledger reports 24/39, while its archived judged sidecar contains 25/39. That unresolved provenance difference does not affect the present paired comparison. The historical recorded reference, 43/47, belongs to release `94a07aadc5dc`. Its brain source matches accepted `f9b90b958023`; subsequent runtime changes handle worker failures, shutdown, and fixture-error propagation. It is historical lineage evidence, rather than a new measurement of the accepted release.

The trial captures existing tegrastats, `free -b -s 1`, `vmstat -w -t 1`, and before/after swap counters. Samples cannot establish peak headroom or paging safety. The model checksums are recorded with the comparison results. A candidate must gain two development passes across two topics, introduce no correction or topic-change failures, and retain at least 2/6 transfer passes. Only a qualifying candidate proceeds to recorded regression.

Qwen3.5-2B scored 6/18 development and 2/6 transfer, judged (J). It lost several previously successful follow-ups and added unsupported conversation claims. All 24 synthesized answer WAVs matched independent transcription. Development and transfer synthesized first-audio medians were 1.380 s and 1.422 s; complete-answer medians were 2.751 s and 3.471 s (J). Detection medians were 14.98 fps and 15.09 fps (J). The candidate failed conversation qualification, so its recorded regression was not run.

The minimum sampled `MemAvailable` was 683,581,440 bytes across 345 samples (J). Paging occurred in 33/172 development and 19/75 transfer one-second intervals overlapping a response (J). These intervals include synthesized speech duration and have boundary uncertainty. Whole-replay swap-out counters increased by 165,535,744 and 145,408,000 bytes, including model loading (J). This candidate also fails the no-paging target. `bench/results/2026-10-15-conversation-model-resources.jsonl` retains the analysis, raw-source hashes, and measurement limits. The protocol file retains the command and installed model hashes.

All four candidates are rejected. Runtime source matches the accepted release. General conversation remains unresolved; the evidence supports examining how instructions, retrieved statements, and dialogue context interact. It does not support more per-topic rules, a larger-model retry, or another wording sweep.
