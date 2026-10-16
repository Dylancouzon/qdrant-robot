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

## Stored exchange prototype, 2026-10-15

Dylan validated accepted live release `f9b90b958023` and requested recall of both sides of a conversation after topic changes. Opus 5.5 recommended adding replies to existing text points and using bounded recent retrieval before semantic decay. The prototype stores `answer` and source `evidence` on the existing point. No point, vector, index, or shard is added.

The frozen development fixture has 44 typed turns across six sessions. It contains six topic-recall probes, a corrected food preference, and three no-memory/deletion/restart probes. Four intervening exchanges and a scene change remove the opening reply from the ordinary prompt window. Keyword checks and source delivery are reported separately from judged correctness.

| Arm | Judged overall | Judged topic recall | Raw source checks |
| --- | --- | --- | --- |
| Accepted `f9b90b958023` | 34/44 | 1/6 | 2/7 |
| Quoted exchanges, `e345d845afa2` | 38/44 | 5/6 | 7/7 |
| Existing retrieval instruction, `347285a7bee6` | 37/44 | 4/6 | 7/7 |

All measurements are J. The first prototype recalled Microsoft, Tokyo, a novel, risotto, and both discussed companies. Both prototypes failed the exact single-Qdrant question despite source delivery. The second also reversed speaker roles when recalling the dish. All three arms passed the corrected preference. All three passed two of three no-memory checks; the post-deletion answer still mentioned Qdrant. Its identity prompt names Qdrant, while deleted exchange records were absent. This is a model-generated false memory, not successful retrieval. Neither prototype qualifies.

The prototype retrieves at most ten same-visitor rows, filters point IDs after the active conversation boundary, removes already-present pairs and unsafe sources, and supplies at most six complete pairs within 384 tokens. The full prompt reserves output and chat-template space. Actual server chat-template checks confirm the delivered prompts fit; the first Qdrant prompt had 532 tokens (J).

Dialogue source IDs remain separate from visual IDs. Object references propagate through `evidence.objects` on dialogue points. Existing object and visitor deletion callers delete those records through a payload filter. These references never enter `things.turns`, so they do not protect dialogue from retention or feed visual answers. Deletion also clears derived evidence cards. Records with unavailable sources or ignored objects are excluded, including pronoun-only replies.

The initial complete local pytest run found a test double missing the tokenizer method; that double was corrected. One subsequent gate run exceeded its 300 s test limit. A diagnostic run completed with 403 tests passing in 194.67 s. Baseline and first-prototype speech checks matched 40/44 texts each (J); short numeric answers produced digit or plural transcription mismatches. The checker remains unchanged.

The second integration reuses the existing retrieval instruction and one text block. Its extra food failure shows that clearer source delivery alone does not guarantee correct speaker attribution. A controlled Jetson diagnostic then replayed the same captured prompts as quotes and as native user/assistant roles, with and without image prefill. Native roles still failed the exact Qdrant question. Source-removal and neutral-topic controls also produced Qdrant guesses. These controls do not establish that the company/category distinction is the sole cause, or that the model has an inherent ceiling.

The counsel verdict permitted one representation diagnostic and required stopping if it failed the exact question. No native-role production path was built. Both prototypes are archived as `archive/dialogue-{v1,v2}.patch` against `314645d`; runtime source is restored. Recorded-voice, visual-recall, and conversation regressions were not run because neither candidate qualified. Existing ordinary answer failures remain separate from the recall score.

All seven opening reply sources were confirmed in each candidate's actual prompt, independently of `evidence_ok`. The maximum rendered prompts were 788 and 787 tokens, with output space available (J). Each of the three 44-turn speech checks matched 40/44 texts; the unchanged checker recorded four short-number mismatches per run.

System paging occurred in 52/209 and 20/210 one-second intervals overlapping responses (J). These intervals have boundary uncertainty, and kernel counters do not identify the paging process. Minimum sampled available memory was 986,583,040 and 1,007,783,936 bytes (J). Samples do not establish peak headroom or paging safety. `bench/results/2026-10-15-exchanges-analysis.jsonl` retains the derivation, raw-resource locations, and hashes. The protocol records the frozen criteria and commands. The first fixture's source paths were normalized only after SHA-256 equality checks; original bytes remain in `build/`.

The initial regression plan cited the obsolete 15-turn recall fixture. The current fixture has 21 turns. No candidate reached regression, and a future trial must establish its current baseline before setting that floor. General conversation memory remains open. The missing stored reply is a real code gap, but answer generation from supplied dialogue also needs a measured correction.

The [exchange task review](../reviews/20261015-211223-67375-review.md) approves the retained tests and records. Its suggested exact source-text checks are included in the analysis, with all seven opening replies confirmed. Before any future representation trial, merge overlapping user messages after scene changes; complete-pair deduplication can leave repeated questions and confuse corrections.
