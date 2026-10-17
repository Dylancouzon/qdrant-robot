# Work queue and known gaps

## Next steps

**Head button during delayed polling.** An older status response can briefly restore the previous button state (U). The controller still enforces cooling, fault, and fresh-input guards. Reject older responses if this becomes observable.

**Passive head displacement after motor shutdown.** Confirmed torque release does not establish a measured camera angle or physical settlement. Fault handling rejects transition captures and stores unknown pose. Physical stability after release remains unmeasured.

**Loaded power and temperature feedback.** Mounted direction, watched ±60° travel at 40°/s, and cable clearance passed. Dylan reported good live motion. The [head guide](servo.md) records brief temperature trips, the requested cooling pause and 70°C head protection, and remaining qualification. Keep models, memory, consent, and deletion behavior intact.

**Alternating following requests after reversal delay.** Rapid alternating detections can resume the original direction while reversals wait for confirmation. The simulated candidate reaches its travel limit under sustained 150 ms alternation (E). Check live camera feedback; if observed, require confirmation before resuming either direction after an interrupted reversal pause.

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
| False face on an object | The face detector found a 53 px face on the brown teddy bear (`m2-teddy-brown.jpg`) with no person in view. That face then owned the conversation, and every later faceless turn got "Please look at me and say it again" (J, `demo-things` in the 2026-10-17 demo baseline). A live presenter's own face and person track should carry the turns; a held teddy bear with the presenter out of view remains a demo risk. A face inside no person box is a candidate filter; it needs a check of close-up enrollment first. | [Memory demo plan](overnight-conversation.md) |
| Run-on replies | The one-sentence cap counts neither questions nor sentences under six words, so a reply made of questions and fragments runs to the 64-token budget ("I see... It's a bit like the way we're all moving through life, right?...", probe `fd-3`, J). It occurred once per 79-turn development run in both baseline and finalist. A cap on total words after the first sentence end is a candidate; it needs a fresh validation set (D207). | `eval/probes/forget-dialogue.jsonl` |
| Dialogue cue coverage | Exchange quotes need a past speech verb; "What number did you give me..." and six `recall-long` turns without a verb get none. A similarity gate cannot replace the cue: statement questions score as high as exchange questions (0.80 to 0.92 against 0.74 to 0.81, E). In validation, "What did you tell me about the freezing point?" also got no quote although the cue matches; trace it before changing retrieval. "And what was the fun fact about it?" got no quote and missed the earlier answer (validation, J). Broadening the cue reopens the 2026-10-15 "before a trip" regression; similarity-ranked exchanges are the measured alternative. | [Conversation](conversation.md) |
| Object deletion paraphrases | Forgetting an object deletes the visitor's turns naming the object or its label, all their stored answers, and the live conversation. A statement with a pronoun within the conversation window after the visitor named or asked about the object, or after another such linked statement, is linked to it and deleted with it. A paraphrase with neither the name nor a pronoun ("the striped thing came from Paris") survives, and so does dialogue quoting for that visitor, which resets. The focused probe could not exercise deletion: the fixture image shows no hand, so naming was refused. | `robot/memory.py` `forget_mentions`, `forget_answers` |
| Naming needs a held object | "That's my motorbike" gets "Hold it up and say it again": only held objects can be named. In the demo, name small objects while holding them. | [Objects](objects.md) |
| Stranger wording | A stranger asking a personal question gets "Please introduce yourself, or say who I should talk to." It leaks nothing, but the judge fails it as unhelpful in about half of the runs. | `robot/attention.py` |
| Benchmark temporary shards | `bench/recall_bench.py` leaves its temporary Edge shards in the system temp folder after each run (review 2026-10-17). Close the shards inside `TemporaryDirectory` contexts if repeated runs use noticeable disk. | `bench/recall_bench.py` |
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
