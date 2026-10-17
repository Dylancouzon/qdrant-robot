# Work queue and known gaps

## Next steps

**Loaded power and temperature feedback.** Mounted direction, watched ±60° travel at 40°/s, and cable clearance passed. Dylan reported good live motion. The [head guide](servo.md) records brief temperature trips, the requested cooling pause and 70°C head protection, and remaining qualification. Keep models, memory, consent, and deletion behavior intact.

| Priority | Task | Finish when |
| --- | --- | --- |
| Next | Loaded power, cooling, and transient temperature feedback. | Explain guard trips and qualify prolonged watched operation before unattended use. |
| Parked | General conversation and recent recall. | A changed mechanism improves varied topics while preserving passing privacy, visual, correction, and transfer cases. See [conversation](conversation.md#next-steps). |
| Parked | Booth acceptance. | Meet the targets and M4 checks in [CLAUDE.md](../CLAUDE.md). Physical latency remains parked under D160. |

Dylan confirmed assembly on 2026-10-16. Existing models, thresholds, fixtures, and rubrics stay fixed until a scoped change needs them.

## Current limitations

| Area | Remaining issue | Detail |
| --- | --- | --- |
| Conversation | Broad past cues and incomplete history caused regressions in archived stored-reply prototypes. General answer quality remains below target. | [Conversation](conversation.md#broader-stored-exchange-regression-2026-10-15) |
| Shutdown diagnostic | The unconfigured live unit logged `RuntimeError: _work stopped` during Stop, then deactivated successfully. A replacement calibrated unit started normally. Check the worker supervision path during graceful shutdown before treating an expected exit as a fault. | `bench/results/2026-10-16-ui-framing.json` |
| Servo qualification | Mounted direction, loaded motion, cable clearance through ±60°, Stop, and short service shutdown passed. The +70° attempt stopped 1.67° short; that range remains unqualified. Live following uses 40°/s, gentler acceleration/deceleration 40, and continuous corrections. Thermal pauses keep speech and vision available. Prolonged loaded power, the brief 65°C and 60°C reports, intermittent supply-guard trips, and the unmet 0.3 s provisional Stop goal remain open. | [Head control](servo.md#next-session-assembled-robot-testing) |
| Identity and privacy | Stranger acceptance and multi-visitor handoffs still need whole-robot qualification. | [Faces](faces.md), [recorded backlog](archive/edge-case-records-2026-10-15.md#earlier-recorded-backlog) |
| Perception | Lookalike objects, changed viewpoints, small objects, and tracking gaps can limit recognition. | [Objects](objects.md), [camera and encoder records](archive/edge-case-records-2026-10-15.md#camera-and-crop-encoder-d167-d168) |
| Resources and latency | Paging, sustained detection, and physical audible latency remain unresolved targets. | [STATE.md](../STATE.md), [stack](stack.md) |
| Evaluation | Replay can lose partial rows on interruption; standalone judging accepts empty input; bake-off judging can ignore failure. Keyword matching also accepts substrings. | [Evaluation pitfalls](experiment-ledger.md#evaluation-pitfalls), [recorded backlog](archive/edge-case-records-2026-10-15.md#earlier-recorded-backlog) |
| Host test timing | The actual-stream test exceeded 200 ms once at 222.11 ms (E); its isolated rerun passed unchanged. Runtime code and the limit stayed fixed. | [Validation record](../reviews/20261016-opus55-repo-cleanup.md#validation-follow-up) |
| Cleanup callers | Some benchmark and replay callers still need stronger resource cleanup after exceptions. | [Worker records](archive/edge-case-records-2026-10-15.md#worker-exceptions-2026-10-15) |
| Interface | Evidence ages refresh only when evidence changes. Focus pauses tips; leaving focus resumes rotation. | [Compact UI records](archive/edge-case-records-2026-10-15.md#compact-ui) |
| Location | Owner scoping works; UI-set physical location labels remain parked. | [Owner and location](owner-location.md) |

## Interface refresh, 2026-10-16

The centered tip, full-height conversation, shared evidence panel, stored memory map, and Memory galleries are complete. Creation, recall, deletion, reconnect, and bounded samples have regression checks. The [interface guide](mac-audio-interface.md) describes current behavior; the [dated report](archive/interface-checks-2026-10-16.md) retains measurements and limits.

## Lookalike recognition in good light, 2026-10-15

Dylan reported that the lookalike recognition bug is gone under good light. That retest is closed on his report. The color veto stays parked. Earlier benchmark limits remain unchanged.

## Enclosure qualification

The assembled enclosure passed watched travel and cable checks through ±60°. It still needs prolonged power, cooling, fan-noise, and speaker-echo checks. Earlier fit concerns remain in the [enclosure record](archive/enclosure-fit-checks-2026-10-16.md).

## Historical records

The [detailed records](archive/edge-case-records-2026-10-15.md) preserve all earlier cases and source reviews. They include fixed issues and parked proposals. Read the relevant dated section before reopening a case. [Archive tags](archive/README.md#evidence-from-earlier-archive-tags) retain older evidence that left the working tree.
