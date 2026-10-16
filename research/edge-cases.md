# Work queue and known gaps

## Next steps

**Physical servo qualification.** Shared visitor selection, ownership, following, and left/right inspection pass the [finite-speed simulation](servo.md). The serial runtime requires an explicit calibration file. After assembly, verify mounted direction, travel, cable clearance, power, and stopping. Keep models, memory, consent, and deletion behavior intact.

| Priority | Task | Finish when |
| --- | --- | --- |
| Next | Assembled-head calibration and qualification. | Verify bounded physical movement, stopping, cable clearance, and power behavior. |
| Parked | General conversation and recent recall. | A changed mechanism improves varied topics while preserving passing privacy, visual, correction, and transfer cases. See [conversation](conversation.md#next-steps). |
| Parked | Booth acceptance. | Meet the targets and M4 checks in [CLAUDE.md](../CLAUDE.md). Physical latency remains parked under D160. |

The enclosure worktree remains outside this task. Existing models, thresholds, fixtures, and rubrics stay fixed until a scoped change needs them.

## Current limitations

| Area | Remaining issue | Detail |
| --- | --- | --- |
| Conversation | Broad past cues and incomplete history caused regressions in archived stored-reply prototypes. General answer quality remains below target. | [Conversation](conversation.md#broader-stored-exchange-regression-2026-10-15) |
| Servo qualification | Mounted direction, load, cable clearance, intermittent supply-guard trips, and the unmet 0.3 s provisional Stop goal need assembly testing. | [Head control](servo.md#next-session-assembled-robot-testing) |
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

## Historical records

The [detailed records](archive/edge-case-records-2026-10-15.md) preserve all earlier cases and source reviews. They include fixed issues and parked proposals. Read the relevant dated section before reopening a case. [Archive tags](archive/README.md#evidence-from-earlier-archive-tags) retain older evidence that left the working tree.
