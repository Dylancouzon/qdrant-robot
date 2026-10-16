# General conversation

The retained conversation policy was validated in `f9b90b958023`. [STATE.md](../STATE.md) owns the deployed interface release. It keeps Qwen3-VL-2B, the existing reply policy, and four recent exchanges. Conversation-memory prototypes remain archived. Completed measurements and review receipts are in the [trial report](archive/conversation-trials-2026-10-15.md).

## Next steps

These conversation follow-ups are parked. Servo motor control and voice commands are the next project task.

1. Check the shared past-question decision against varied recall requests, future plans, corrections, and topic changes. The broad `before` cue currently admits future advice.
2. Test chronological history assembly that handles questions left without replies after scene changes. Keep source validation, visitor boundaries, and deletion intact.
3. Freeze a paired comparison before changing runtime behavior. Require gains across topics and preserve previously passing correction, privacy, visual, and transfer cases.

Keep the existing model and evidence requirements. A new trial needs a changed mechanism and fresh paired baselines. The exact Qdrant recall failure, false memory after deletion, general answer quality, and response-interval paging remain open.

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
