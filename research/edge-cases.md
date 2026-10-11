# Known gaps and parked proposals

Some evidence paths below exist only in archive tags; see [archive/README.md](archive/README.md) to read them.

## Earlier recorded backlog

As of 2026-10-09. D71 (Dylan): v1 logs edge cases and tests the whole robot first, in case the architecture changes. Each entry: trigger, risk, candidate fix, and source. D77 also permits revisiting verified limitations with a concrete intervention and paired validation. Foundational retrieval and conversation questions are in research/archive/grounding.md, object perception in research/booth-ux.md, and memory candidates in research/stack.md.

| Case | Risk | Proposed fix | Source |
| --- | --- | --- | --- |
| A running view token becomes stale during monitor attachment | The page can stay warming because authentication failures retry | Surface permanent authentication rejection if observed | tools/talk.py; reviews/20261011-114305-67106-review.md |
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
| An imperative deletion followed by a condition or correction ("Forget my phone? No, do not delete it") | Deletes despite the correction | Reject qualified or corrected commands before dispatch if seen in visitor use | robot/memory.py deletion_target(); reviews/20261010-205013-70268-review.md |
| Earlier-frame ordinals skip views that match the present, and "after that" means the newest view | "First" or "after that" can pick the wrong object after three or more objects | Count all retained view runs and track the last recalled frame if visitor use shows it | robot/memory.py earlier_view(); reviews/20261010-210536-87090-review.md |
| A combined question ("Is this the same as what I showed you before?") gets no earlier frame | Past-versus-present comparisons fail (`rc-compare`) | Design a comparison path with both views, tested against D25 blending | research/recall.md |
| Qualifiers outside the word lists ("last night", "at the office") still select the newest RAM frame | An answer from the wrong observation | Extend `_WHEN_WHERE` when observed | robot/memory.py; same review |
| Speech during a caption prefill waits for the first generated token before it interrupts | A slower next turn | Measure foreground delay in the paired run | robot/brain.py caption(); reviews/20261010-215023-40827-review.md |
| An interrupted or empty idle caption is retried on the next idle check | Wasted GPU work | Suppress unchanged retries until a new view or a question needs it | robot/main.py _describe_idle(); same |
| Speech during playback or its 0.3 s tail is discarded (half duplex) | A visitor cannot interrupt the robot | Measure normal follow-ups first; echo cancellation only if interruptions matter | D152 |
| A tunnel failure clears the page's unit reference | Stop is disabled until Start reattaches | Press Start, then Stop | tools/talk.py; reviews/20261010-225408-11584-review.md |
| A recall answer can add an extra article to captions starting with "this", "one", or "five" | Awkward speech | Extend the determiner list if heard | robot/memory.py showed() |
| An Ignore whose offer refreshes during embedding is rejected | The visitor presses again | Measure rejection rate in the live UI check | D151 |
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
| Many conversations without an object | Each keeps a pending guest number in RAM until restart | Drop abandoned entries when a conversation ends | reviews/20261011-024631-51048-review.md |
| More than 1,000 item Ignore records | Restart loads only the first 1,000, so cleanup can miss later copies | Page the load | same |
| Two visitors with the same display name | The Memory tab groups their objects under one heading (edits stay distinct by id) | Group by owner id | reviews/20261011-034135-6848-review.md |
| A Memory tab edit waits behind a long turn | The card stays after 5 s of polling with no message | Show "Saving..." when polling ends | same |
| A lookalike that appears during a teaching window, or carries another label, is not yet a confirmed same-label track | Its overlapping crop can enter the taught gallery (D154) | Check current detections instead of confirmed tracks for the overlap guard | reviews/20261011-013812-81300-review.md |
| Saving settings fails (disk full, permissions) | The page sees a dropped connection; the old settings stay active | Catch OSError and return a control failure | same |

## File source decode errors (F0b review, 2026-10-09)

A later video decoding or seeking error raises from FileCamera.latest(). The detector loop can exit without setting detect_failed, so a replay may continue with stopped detection. Carry under D71; before relying on failure propagation in a continuous challenge, set detect_failed on source errors and make the evaluator fail. F0b source qualification completed without a decoding error. Evidence: reviews/20261009-030935-4181-review.md, robot/main.py _detect().

- Continuous paging attribution (D93): progress activity labels describe one instant, while page deltas span the previous sample interval. Report active-labelled totals, and use full recorded turn intervals before attributing paging to active turns. Source decoder compatibility: Mac and Jetson OpenCV5.0.0 use FFmpeg avcodec61.19.101 and62.28.101. Identical smoke AVI bytes produce0/90 matching cross-platform pixel hashes; four Jetson switch/hold probes match their Jetson oracle. Record decoder builds and requalify under the deployed decoder after environment changes. Evidence: reviews/20261009-042113-94477-review.md and bench/results/2026-10-09-f0d-operations.jsonl.

- Mac audio interface (D122, Sol52230 PASS): a workflow-launcher timeout can leave its SSH descendant holding pipes and delay cleanup. If observed, reap the launcher process group on timeout. A queued Mute request can race with closing the native child stdin and raise ValueError; detach the child under the shared lock before closing pipes if observed. Normal native Start/Mute/Stop and warmup Stop pass. Both are carried under D71; no product architecture change.

- D124 preview, Sol77868 PASS: a second MJPEG viewer replaces the first, leaving its frozen image while state polling works. Dylan observed this; closing the duplicate and reloading the original restored motion. Keep one preview tab. Other disconnect recovery remains unimplemented; this incident did not prove socket timeout.
- D124 preview, Sol77868 PASS: overlapping speech transcripts can temporarily show another turn's status/evidence (robot/main.py:277). On observation, separate queued question text from the active answer. Dylan performs live testing; these optional display gaps do not justify another test or review pass.

- D127/D128 preview, Sol38457 PASS: a named object returning on a new undersized track cannot enter recognition and may remain invisible. If Dylan observes it, allow bounded recognition before excluding tiny unknown boxes.
- D127/D128 preview, Sol38457 PASS: speech interruption can drop a teaching-crop caption. Named vector recall remains available, but historical descriptions can be missing. If observed, retain only interrupted, still-selected crop work for idle retry.

- D129 display: continuous object replacement without a detectable tracking gap can retain the previous green display association for at most two seconds. Fresh crop matches alone authorize writes; a real miss immediately downgrades the label, and three misses restore global matching. No extra tracking machinery is justified by this carried risk.
- D130/D131 naming: teaching one physical object under different distinct names retains prior named records. The current continuous association re-verifies the latest explicit name. After a gap or restart, a global vector tie can recover an older alias. Historical alias migration remains outside this correction.

- D129-D131 review87875: after a tracking gap or restart, equal crop scores can recover an older alias. Historical rename/alias migration is outside this task. A possessive "What about Ana's smartphone?" parses the name without a reply mode; carry until observed.

- D136 review20183: a new turn can arrive during scripted Robot.reset after job drain and before recognition owner replacement. Existing external replay callers serialize reset and turns. Coordinate turn admission if this overlap becomes supported or observed; no admission redesign in the common booth continuity repair. Item-check departed-track retention was fixed through existing Focus lifecycle pruning.

- D138 review96960 PASS: a current selected object absent from an older verified source can briefly lose its overlay. Source geometry and epoch validation remain required. If a deployed recording shows disruptive gaps, prefer the current frame for that presentation. The bounded UI review has one early no-focus snapshot, with no rapid target alternation; continuous transition timing remains unqualified.

## Two-step teaching, 2026-10-10

- Right after "What should I call it?", an unrelated line such as "turn down the volume" becomes the name. Volume stays a UI control by design (Dylan, 2026-10-10), so no spoken volume command will be added; the visitor can say "forget my <name>". Evidence: reviews/20261010-232645-44755-review.md.
- A short bare statement (up to four words) after "What should I call it?" becomes the name. Prefer explicit naming forms if this shows up live.

## Full-stack model comparison observations, 2026-10-10

- FileCamera still images keep their original timestamp. Recognition rejects sources older than 0.75 seconds, while repeated detection can continue. This main-runtime behavior stays unchanged. The private fit comparison supplies recurring fixture timestamps so it measures active recognition. Evidence: reviews/20261010-140209-99264-design.md and robot/camera.py FileCamera.latest().
- The recorded knowledge-more-2 question splits into two answered lines (J). Keep the existing VAD/ASR implementation and score the split as a failure. Evidence: the same recorded replay; compare its occurrence across arms before drawing a model conclusion.

## Compact UI

- Removing a view reloads the gallery, resets its scroll position, and collapses Edit memory. Preserve the affected card state if repeated removal becomes disruptive.
- Evidence ages update when evidence changes. After a long idle period, the relative time can become stale. Refresh time labels if visitors encounter this.
- Stop or disconnect disables the microphone button but can leave its last mute icon and accessible state. Reset these in `clearLive()` if this causes confusion. The next connection publishes the correct state.

## Bounded overlay persistence

- A size dip followed by a detection gap can extend an undersized outline beyond its original size grace, for at most the 200 ms missing-detection grace. Action authority remains absent. If this becomes visible, also bound undersized carry by publication time minus admission time.
- The paired recorded-detection benchmark uses confirmed tracks for overlap suppression. Production also checks unconfirmed replacements, so the reported nine-frame outline gain can overstate production behavior. Use all matched detections when this comparison next informs a decision.
