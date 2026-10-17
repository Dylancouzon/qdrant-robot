# General conversation

The robot keeps Qwen3-VL-2B, the existing reply policy, and four recent exchanges. [STATE.md](../STATE.md) owns the deployed release. Earlier full-exchange prototypes remain archived. Completed measurements and review receipts are in the [trial report](archive/conversation-trials-2026-10-15.md).

## Personal statement recall

Statement queries require the resolved visitor ID and apply its payload filter before similarity ranking. Every statement belongs to its visitor, including general statements. Enrolled visitors can recall their own statements from earlier conversations within the existing 12-hour ordinary retention. Guests retain temporary conversation IDs; a reset or restart gives them a new identity. Consent-based enrollment reuses the guest's visitor ID, preserving earlier statements from that conversation. Curated knowledge remains shared.

The runtime still delivers at most two matching statements with their source IDs. Missing or ambiguous visitor identity blocks personal retrieval. Ignored-object suppression and "forget me" deletion remain in place. Old unowned points do not qualify for personal recall. A false enrolled-face match now risks disclosing earlier-conversation statements; stranger qualification remains open.

New bare acknowledgements such as "okay", "thank you", "yes", "no", "um", and "hmm" receive no statement vector. Raw diagnostic turn records and short-term dialogue remain available. Questions and device actions keep their existing evidence rules. Existing filler vectors are not rewritten; ordinary retention removes them over time. This change adds neither stored assistant replies nor conversation summaries.

D206 supersedes D70's statement-scoping clause. Claude Opus 5.5 checked the [minimal plan](person-memory-plan.md) before implementation. Its [review](../reviews/20261017-opus55-person-memory-plan.md) required explicit recording of the changed sharing rule and separate enrolled/guest acceptance checks. Both corrections were applied before code changes.

The pre-change memory backup is `shared/backups/pre-person-memory-1792214398165463000/memory/` on the Jetson. It was copied with closed shards under the shared job lock. The [task review](../reviews/20261017-011944-59900-review.md) passes. Full release checks pass in 277.78 seconds (E). The [isolated Jetson check](../bench/results/2026-10-17-person-memory.json) passes all seven query, admission, persistence, and deletion checks with qdrant-edge-py 0.8.0 (J). It uses a temporary store and no models; live answer quality remains unmeasured.

## Deferred next steps

1. Retrieve complete exchanges for explicit conversation-history questions. Fix retrieval eligibility and duplicate history before revisiting the archived prototype.
2. Choose retention beyond 12 hours only when returning-visitor use requires it. Named-object evidence already follows its own protection rules.
3. Improve transcript admission only for observed recognition errors; preserve useful short statements and ordinary dialogue.
4. Add recency weighting only after demonstrating stale results displacing relevant evidence.
5. Consider offline consolidation only after measuring a need. Retain source IDs, corrections, and visitor deletion links in any summaries.

The broad `before` cue still admits future advice. History assembly can retain questions without replies after scene changes. The exact Qdrant recall failure, false memory after deletion, general answer quality, and response-interval paging remain open. Keep the existing model and evidence requirements, and use a fresh paired comparison before expanding dialogue retrieval.

## Stored exchange prototype, 2026-10-15

The prototype adds replies and source references to existing turn points. It retrieves at most six complete exchanges within 384 tokens. The [initial trial](archive/conversation-trials-2026-10-15.md#stored-exchange-prototype-2026-10-15) used 44 development turns across six sessions.

| Arm | Judged answers | Topic recall | Opening replies supplied |
| --- | --- | --- | --- |
| Accepted baseline | 34/44 | 1/6 | 2/7 |
| First prototype | 38/44 | 5/6 | 7/7 |
| Second integration | 37/44 | 4/6 | 7/7 |

All measurements are J. The first prototype gained four recall passes without losing a passing answer in this fixture. Both integrations failed the original Qdrant question despite receiving its source. All arms retained the same post-deletion false-memory answer after the stored exchanges were deleted. Generated dialogue remains separate from observed evidence.

## Broader stored-exchange regression, 2026-10-15

The unchanged first prototype and a fresh accepted baseline each completed 92 development turns. The [full report](archive/conversation-trials-2026-10-15.md#broader-stored-exchange-regression-2026-10-15) retains commands, resources, speech checks, and reviews.

| Suite | Accepted, judged | First prototype, judged |
| --- | --- | --- |
| [Recorded voice](../eval/dev/sessions.jsonl) | 43/47 | 43/47 |
| [Visual recall](../eval/dev/recall.jsonl) | 16/21 | 16/21 |
| [Conversation](../eval/dev/conversation.jsonl) | 4/18 | 4/18 |
| [Transfer](../eval/dev/conversation-transfer.jsonl) | 2/6 | 0/6 |

All measurements are J. Only the two transfer answers below lost previously passing judgments. Original evidence checks stayed at 5/5 recorded and 9/9 visual recall. Independent speech results stayed unchanged. Both releases paged during response intervals. The accepted conversation baseline varied from an earlier 7/18 to 4/18; its cause remains unconfirmed.

| Regression ID | Visitor request | Prototype failure |
| --- | --- | --- |
| `conversation-language-1` | Switch from desk organization to learning words before a trip. | It echoes the request instead of suggesting a starting step. |
| `conversation-language-2` | Keep language practice to ten minutes daily. | It only acknowledges building a routine. |

The first prompt contains four unrelated desk exchanges because `about_past` matches "before a trip". Scene-change handling also leaves duplicate visitor questions without replies. The follow-up inherits the weak answer. These traces identify retrieval and history problems; no ablation isolated their individual effects.

## Earlier comparisons

History retention, usefulness instructions, longer replies, and installed Qwen3.5-2B all failed qualification. Their metrics, tradeoffs, and archived patches are indexed in the [trial report](archive/conversation-trials-2026-10-15.md#paired-development-comparison-2026-10-15) and [experiment ledger](experiment-ledger.md#retrieval-and-answers).

## Reproduction and evidence

Use [tools/results.py](../tools/results.py) to read existing runs without models. The [contextual judge](../bench/conversation.py) grades actual preceding replies against frozen rubrics. Empty keyword lists measure neither usefulness nor correctness. These development runs establish neither held-out acceptance nor physical latency or sustained conversation.

| Evidence | Fixtures | Results and derivation |
| --- | --- | --- |
| General dialogue and transfer | [18 turns](../eval/dev/conversation.jsonl), [six turns](../eval/dev/conversation-transfer.jsonl) | `bench/results/2026-10-15-conversation-*`; [protocol](../bench/results/2026-10-15-conversation-protocol.jsonl). |
| Stored replies | [44 turns](../eval/dev/exchanges.jsonl) | `bench/results/2026-10-15-exchanges-*`; [analysis](../bench/results/2026-10-15-exchanges-analysis.jsonl). |
| Broader regression | The four suites above. | `bench/results/2026-10-15-dialogue-regression-*-replay-1792114624*`; [protocol](../bench/results/2026-10-15-dialogue-regression-1792114624-protocol.jsonl), [analysis](../bench/results/2026-10-15-dialogue-regression-1792114624-analysis.jsonl). |

The [archive index](archive/README.md) lists all five rejected patches and their base commits. Raw journals, original result bytes, resource samples, and audio remain in ignored `build/` and on the Jetson.
