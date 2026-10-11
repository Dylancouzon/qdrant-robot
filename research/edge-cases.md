# Known gaps and parked proposals

Some evidence paths below exist only in archive tags; see [archive/README.md](archive/README.md) to read them.

## Next-session object recognition discussion

Dylan accepted the D147 live checkpoint on 2026-10-10. Owner from the named introducer and UI-set Location are selected future requirements. Current code and memory schemas stay unchanged; same-owner grouping and background isolation remain parked under D148.

| Gap | Current evidence | Discussion for the next session |
| --- | --- | --- |
| Two items with the same name can leave neither recognized. | Dylan's live report; `Focus.associations()` abstains when multiple tracks claim one name. `Things.name()` keys each object point by name. | Implement the selected named-owner binding through a reviewed design. Decide whether one owner's two same-name objects form one shared logical object. Preserve ambiguity and consent/deletion safety. |
| Recognition crops retain background pixels inside the detection rectangle. | `robot/things.py` uses a rectangular `cut()` followed by square padding; it performs no segmentation masking. | Compare background isolation with the current crop on varied objects, hands, backgrounds, and negative examples. Its recognition benefit and Jetson cost remain unmeasured. |

The [reference crop implementation](https://github.com/Dylancouzon/qdrant-edge-memory-robot/blob/cfc0dd2c5bb540f08149213c43bd33ba2d0c27f9/robot/brain/detect.py) pads the box by 12%, dilates a supplied mask, and fills outside-mask pixels grey. Its pinned read-only local checkout verifies this behavior. A missing mask retains the rectangular background. Changing crop preprocessing also changes stored vectors; compatibility and any required reteaching need explicit measurement.

## Earlier recorded backlog

As of 2026-10-09. D71 (Dylan): v1 logs edge cases and tests the whole robot first, in case the architecture changes. Each entry: trigger, risk, candidate fix, and source. D77 also permits revisiting verified limitations with a concrete intervention and paired validation. Foundational retrieval and conversation questions are in research/archive/grounding.md, object perception in research/booth-ux.md, and memory candidates in research/stack.md.

| Case | Risk | Proposed fix | Source |
| --- | --- | --- | --- |
| Two visitors speak within the 20 s no-face window | A told name reaches the second visitor | Answer told names only with a face match at the booth | reviews/20261008-215107-4264-review.md |
| "I'm tired" style lines read as names | A wrong name and a face offer | Listen for introductions only with a new unrecognized face (D70) | D70 |
| A reach toward the background puts it inside the person box | Background object takes the focus for about 3 s | A hand class or a depth camera | D67 |
| Turn frames showing an unidentified visitor | Survive "forget me" until retention | Link turns to the face seen in them | D54 |
| Swap grows at in-process replay restarts; Dylan reports live conversation swap | Paging may limit sustained conversation; live cause unknown | Separate restart churn from live active-turn paging; measure before a context increase | D66, D76; research/stack.md |
| Identical prompts give different answers | Noisy comparisons | Paired runs, the judge cache, more turns | D56 |
| Ignored statements filtered after retrieval | Relevant statements missed when the top hits are all ignored | Filter during retrieval | reviews/20261008-195032-46869-review.md |
| Detector or crop matching misses objects across motion or changed viewpoints | No box means no focus or teaching, even with label-free matching | D146 now defaults to 26s at 384x640. Keep detector proposals separate from descriptor matching; measure broader object coverage before another change | D43, D64, D77, D146; research/booth-ux.md |
| Two of nine synthetic "Hey Edgy" lines missed ("Eti", "A ag") | The visitor repeats | Real booth voices before more aliases; arm B if needed | reviews/20261008-230525-97862-review.md |
| Background speech within 20 s of an answer becomes a follow-up | The robot answers another speaker | Check on the live day; tie follow-ups to the facing person | same |
| The follow-up clock uses queued WAV length, no speaker | The window boundary differs from playback | Measure with the speaker | same |
| Lines without the wake phrase still trigger a prefill | GPU waste | Skip prefill until woken | V1-B report |
| Focus not frozen at the naming turn's speech start | A wrong bind | Freeze at speech start | V1-B report |
| "Do not forget my phone" or "Should I forget my phone?" matches the forget regex | An unintended deletion | Guard explicit affirmative actions before the forget branch; test negation and questions | D77; robot/things.py command(), robot/main.py _things() |
| Naming fixtures paste objects with no person | No focus forms, naming not tested | Held-object scenes or the live day | V1-B report |
| A missed face on one frame ends a continuing conversation | The visitor loses context | Check face detection on the live day first | reviews/20261008-233058-72473-review.md |
| Past-frame retrieval runs before the visitor check | A new visitor hears shared frame memories | Review after the whole v1 flow | same |
| A face step before every turn with history | About 60 ms before the first token | Gate on scene change or run it during speech | V1-B report |
| Bake-off harness: a running server can answer the health check before the requested model loads | A run labeled with the wrong model | Check the child process and the model identity | reviews/20261008-234551-20256-review.md |
| Bake-off harness: judge failures ignored | A partial verdict file unnoticed | Check the judge's exit code | same |
| Bake-off shape I adds the evidence instruction twice on newer prompts | Misleading shape comparisons | Add it only when absent | reviews/20261009-011200-49661-review.md |
| 64 recent sightings of one kind hide older kinds | A missing memory line | Page farther back if a live visit shows it | same |
| Sightings carry no details (colour, accessories) | "Which teddy had the hat?" fails | Detail from the crop or caption at sighting time | V1-E report |
| TOLD_MIN 0.5 lets unrelated statements through | Odd memory lines ("talk at four" for minutes) | Calibrate on dev with absent memories | V1-E report |
| Commands stored before V1-E come back as told lines in old shards | False ownership in old memory | Retention expires them (12 h) | V1-E report |

## File source decode errors (F0b review, 2026-10-09)

A later video decoding or seeking error raises from FileCamera.latest(). The detector loop can exit without setting detect_failed, so a replay may continue with stopped detection. Carry under D71; before relying on failure propagation in a continuous challenge, set detect_failed on source errors and make the evaluator fail. F0b source qualification completed without a decoding error. Evidence: reviews/20261009-030935-4181-review.md, robot/main.py _detect().

- F0c verification regeneration (D91): `eval/prepare_challenge.py verify` rewrites decoded images and metadata. A changed OpenCV environment could change frozen artifacts while verification succeeds. Current hashes match. Before using a different environment, check every freeze hash; move generation to prepare and make verify read-only if this helper is extended. Review: reviews/20261009-034031-43247-review.md.

- Continuous paging attribution (D93): progress activity labels describe one instant, while page deltas span the previous sample interval. Report active-labelled totals, and use full recorded turn intervals before attributing paging to active turns. Source decoder compatibility: Mac and Jetson OpenCV5.0.0 use FFmpeg avcodec61.19.101 and62.28.101. Identical smoke AVI bytes produce0/90 matching cross-platform pixel hashes; four Jetson switch/hold probes match their Jetson oracle. Record decoder builds and requalify under the deployed decoder after environment changes. Evidence: reviews/20261009-042113-94477-review.md and bench/results/2026-10-09-f0d-operations.jsonl.

- F1a calibration ambiguity (D97): several questions name an object with two eligible descriptions. One expected source ID cannot establish instance resolution. Preserve the frozen calibration as source-ranking development data. Use separate disambiguated cases before claiming same-instance resolution. This does not change the24-case comparison. Evidence: reviews/20261009-060639-22828-review.md.

- F1a candidate limit (D98): 64 higher-ranked hits can fail hydration or ignored-kind checks and hide eligible sources beyond the limit. Carry under D71. If measured visits expose this loss, filter before limiting or fetch another bounded page. Source: robot/memory.py events(); reviews/20261009-064447-68946-review.md.

- F1b synthetic history patterns (D99): distractor sentence patterns recur across distinct invented venues. This limits generalization evidence. If varied visitor histories reduce recall, measure the gap in the selected final-candidate challenge without expanding the fixture freeze. Source: reviews/20261009-071035-215-review.md.

- F1c complete fixture inspection (D100): benchmark inspection scores the entire small fixture before selection. This can hide production candidate exhaustion and tie ordering. Qualify actual Memory.events filtering and ties against the unchanged fixture before adoption. The earlier 64-candidate risk remains carried. Sorting cannot order tied sources outside that pool; representative measurements must expose any loss before a larger-volume claim. F1d review: reviews/20261009-075131-50293-review.md. Source: reviews/20261009-073249-27709-review.md.

- F1f(D103): when a recalled timeline revises a time or location, the2B can omit the current value or combine old/new attributes. Two correction answers fail on both evidence arms. Carry them; revisit general grounding only if integration reproduces the gap. Keep fixtures, floors, and scenario rules unchanged. PASS reviews/20261009-084552-14016-review.md.

- F1g rejected prototype: oversized fixed question/image/facts raises inside the memory worker and can prevent queue completion. A future adopted path must reject the turn while preserving worker availability. No observed overflow in F1g. Source: reviews/20261009-095148-87405-review.md, robot/brain.py context().
- F1g code-answer turns query semantic slots even when generation does not use them. Measure this overhead in the next architecture comparison before moving selection; do not optimize an unmeasured small cost here. The legacy replay observer measures no evaluator-report time because it wraps Scheduler.report instead of reported(). Preserve this instrumentation gap; measure the executed reporter in the next diagnostic without repeating the rejected quality comparison.

- P2 split prototype only: bench/first_phrase.py and bench/memory_budget.py pass image dictionaries to the new text-observation messages argument; their old VLM calls can serialize base64 as text. Do not use them on the split branch until adapted. The existing continuous child-health check sees dialogue only; an observer failure during idle can remain undetected. Main-flow replay works, and current prototype is not adopted. Review20261009-133152-47754 logs both optional issues; no broad benchmark/framework rewrite belongs in the first runnable checkpoint.

- P2-R review140847: continuous source scoring and legacy brain bake-off assume final user content is a list. Tool-result content is text. Do not use those two callers on4f6b920 until their extraction preserves question/history/source roles. Existing replay/three-vote answer scoring remains usable. Source-role spike is not adopted, so this caller update is deferred.

- P2-T frozen brain_bakeoff.py calls old Brain prior/tokens methods, which the native adapter deletes. Use the preserved baseline revision or its existing directHTTP packet drivers before another frozen comparison. This limitation does not block visitor-flow adapter construction; do not add a product compatibility shim. Sol review20261009-164739-57998 lists this as optional.

- Mac audio interface (D122, Sol52230 PASS): a workflow-launcher timeout can leave its SSH descendant holding pipes and delay cleanup. If observed, reap the launcher process group on timeout. A queued Mute request can race with closing the native child stdin and raise ValueError; detach the child under the shared lock before closing pipes if observed. Normal native Start/Mute/Stop and warmup Stop pass. Both are carried under D71; no product architecture change.

- D124 preview, Sol77868 PASS: a second MJPEG viewer replaces the first, leaving its frozen image while state polling works. Dylan observed this; closing the duplicate and reloading the original restored motion. Keep one preview tab. Other disconnect recovery remains unimplemented; this incident did not prove socket timeout.
- D124 preview, Sol77868 PASS: overlapping speech transcripts can temporarily show another turn's status/evidence (robot/main.py:277). On observation, separate queued question text from the active answer. Dylan performs live testing; these optional display gaps do not justify another test or review pass.

- D127/D128 preview, Sol38457 PASS: a named object returning on a new undersized track cannot enter recognition and may remain invisible. If Dylan observes it, allow bounded recognition before excluding tiny unknown boxes.
- D127/D128 preview, Sol38457 PASS: speech interruption can drop a teaching-crop caption. Named vector recall remains available, but historical descriptions can be missing. If observed, retain only interrupted, still-selected crop work for idle retry.

- D129 display: continuous object replacement without a detectable tracking gap can retain the previous green display association for at most two seconds. Fresh crop matches alone authorize writes; a real miss immediately downgrades the label, and three misses restore global matching. No extra tracking machinery is justified by this carried risk.
- D130/D131 naming: teaching one physical object under different distinct names retains prior named records. The current continuous association re-verifies the latest explicit name. After a gap or restart, a global vector tie can recover an older alias. Historical alias migration remains outside this correction.

- D129-D131 review87875: after a tracking gap or restart, equal crop scores can recover an older alias. Historical rename/alias migration is outside this task. A possessive "What about Ana's smartphone?" parses the name without a reply mode; carry until observed.

- D136 review20183: a new turn can arrive during scripted Robot.reset after job drain and before recognition owner replacement. Existing external replay callers serialize reset and turns. Coordinate turn admission if this overlap becomes supported or observed; no admission redesign in the common booth continuity repair. Item-check departed-track retention was fixed through existing Focus lifecycle pruning.

- D136 review30274 PASS: uninterrupted object replacement before fresh verification can make Ignore use the accepted previous name's stored descriptors. If observed, verify the selected current crop before preference persistence. Final D136 moves inventory reads into admitted crop queries without a cache.

- D138 review96960 PASS: a current selected object absent from an older verified source can briefly lose its overlay. Source geometry and epoch validation remain required. If a deployed recording shows disruptive gaps, prefer the current frame for that presentation. The bounded UI review has one early no-focus snapshot, with no rapid target alternation; continuous transition timing remains unqualified.

- Intent/owner planning review91510: duplicate person names or several same-name objects within one owner can make selection ambiguous. Preserve uncertainty and ask which person or object is meant. D148's same-owner grouping policy remains undecided. Do not infer an owner for old unowned records. See research/answer-evidence.md; this is a future-build requirement, not an implemented fix.

## Full-stack model comparison observations, 2026-10-10

- FileCamera still images keep their original timestamp. Recognition rejects sources older than 0.75 seconds, while repeated detection can continue. This main-runtime behavior stays unchanged. The private fit comparison supplies recurring fixture timestamps so it measures active recognition. Evidence: reviews/20261010-140209-99264-design.md and robot/camera.py FileCamera.latest().
- The current Qwen/CUDA replay misses stored evidence for recall-stop-2 and recall-moto-2 (J). Later fruit recall also misses its expected evidence. Preserve these answer/retrieval failures for the paired comparison; do not repair source routing here. Root cause remains unverified. Evidence: private build/gemma-fit-20261010/full-stack/jetson-evidence/qwen-cuda-retry/runtime/results/recorded.jsonl, source ec7eae92a682.
- The recorded knowledge-more-2 question splits into two answered lines (J). Keep the existing VAD/ASR implementation and score the split as a failure. Evidence: the same recorded replay; compare its occurrence across arms before drawing a model conclusion.
