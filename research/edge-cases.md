# Known gaps and parked proposals

Some evidence paths below exist only in archive tags; see [archive/README.md](archive/README.md) to read them.

## Current priorities after the project review, 2026-10-15

The review covered runtime and thread ownership, speech, tracking, recognition, memory deletion, the monitor, deployment, evaluation, and result reporting. The enclosure branch and its worktree remain outside this task. Existing tests, fixtures, rubrics, thresholds, and model choices stay intact.

| Order | Remaining task | Finish when |
| --- | --- | --- |
| One | Improve held-object answers and recent recall. The latest recorded development replay scored 43/47 judged answers and 44/47 keyword checks; the earlier recall replay scored 16/21 (J). | Use held-object clips, rather than chair-dominated composites. Compare answer judgments and supplied evidence before changing runtime behavior. |
| Two | Retest lookalike recognition in good light. DINOv3 confuses differently colored controllers and some laptop pairs (J/E). | Measure both recognition and same-object answers on paired objects. Keep the parked color veto parked until evidence supports it. |
| Three | Finish Memory-tab polish. Group by visitor ID, retain the edited card's scroll and expansion, and show pending edits after polling ends. | Two visitors with one display name remain distinct. A slow edit has a visible outcome, and repeated view removal keeps its place. |
| Four | Complete booth acceptance. Per-capability quality, stranger identity, sustained detection, paging, offline startup, restart, deletion, physical latency, and the eight-hour run remain open. | Meet the targets and M4 checks in CLAUDE.md on the Jetson. Keep physical latency parked until that acceptance task resumes (D160). |

The cleanup fixes explicit result handoff, failed collection handling, full fixture coverage checks, persistent file-camera errors, settings-save failure responses, and mute-state reset. It also corrects stale setup guidance. The acceptance runner remains the entry point. Keep exploratory benchmarks available for reproducibility; split the large robot test file only when a focused change needs it.

Further harness work is bounded: preserve partial replay evidence on interruption, reject empty standalone judge input, propagate bake-off judge failures, and preserve locally enriched historical records during collection. `eval/replay.py` writes its rows only after `run` returns; `eval/judge.py` accepts an empty row list; `bench/brain_bakeoff.py` ignores the judge's exit code. `tools/jetson.py collect` overwrote added metadata in two old local results during this task; their committed versions were restored, and collected originals remain under `build/cleanup-collected-originals/`. The acceptance runner now rejects missing or incomplete results before judging.

The recorded replay's speech check passed 46/47 (J). Its remaining failure is a spelling difference: "Metrocentre via Bens" became "Metro Center via Benz" in independent transcription. Keep the failure visible until the checker handles equivalent spelling without weakening content or truncation checks. The four judged failures concern unprompted image commentary, the beach question, bears reported present after removal, and an incomplete same-object answer. No keyword result changed from the previous recorded run. Evidence: `bench/results/2026-10-15-243f49ff-replay-1792095965{,.judged}.jsonl`.

## Worker exceptions, 2026-10-15

Injected transcription and answer-worker exceptions reproduced incomplete queue accounting locally (E). Both workers now preserve the traceback, stop producers, and discard queued work. Input and answer waits report the failure, and shutdown releases the threads, shards, and model server. Live and replay failure paths close their resources.

The full Jetson probe passed a typed question with synthesized speech and both injected failures with isolated memories (J). Failures reached the caller within 0.17 s, and shutdown took about 0.72 s. Each subsequent case reopened the same test memory folder. Evidence: [worker-failure results](../bench/results/2026-10-15-worker-failure-1792101431.jsonl). Run `python -m bench.worker_failure --revision SHA` through `tools/jetson.py` to reproduce it.

The original live listening incident has no confirmed traceback. A native call that stops returning needs separate diagnosis if the stall returns. Automatic worker recovery remains outside this fix.

The [task review](../reviews/20261015-175840-62876-review.md) carries three caller-cleanup gaps under D71:

- A failing `Robot.close()` skips camera cleanup and drawing restoration in `bench/overlay.py`. Use a nested `finally` when this path needs repair.
- A health exception skips viewer, robot, camera, and temporary-directory cleanup in `bench/view_lag.py`. Wrap its benchmark body in `try/finally`.
- `eval/replay.py` retains its caller-owned `FileCamera` after completion or failure. Close it around `run()` when addressing replay resource cleanup.

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
| A yes/no answer phrased as a question ("Sure, why not?") or a yes with a later "no" ("Yes, no problem") | Read as unclear: the robot asks again or drops the question | Accept these if visitors say them | robot/people.py consent() |
| A question during a face-consent re-ask ("What do you see?") | Answered with the consent question again; the question goes unanswered | Drop the ask on a question and answer it | robot/main.py _consent() |
| Dev composites keep the closet chair in view from the first frame | The chair holds the focus, so replayed comparisons and naming can bind the chair, not the pasted object | Use full-frame or held-object clips for comparison fixtures; check live | eval/dev/recall.jsonl; D163 |
| Two of nine synthetic "Hey Edgy" lines missed ("Eti", "A ag") | The visitor repeats | Real booth voices before more aliases; arm B if needed | reviews/20261008-230525-97862-review.md |
| Background speech within 20 s of an answer becomes a follow-up | The robot answers another speaker | Check on the live day; tie follow-ups to the facing person | same |
| The follow-up clock uses queued WAV length, no speaker | The window boundary differs from playback | Measure with the speaker | same |
| Lines without the wake phrase still trigger a prefill | GPU waste | Skip prefill until woken | V1-B report |
| Focus not frozen at the naming turn's speech start | A wrong bind | Freeze at speech start | V1-B report |
| Earlier-frame ordinals skip views that match the present, and "after that" means the newest view | "First" or "after that" can pick the wrong object after three or more objects | Count all retained view runs and track the last recalled frame if visitor use shows it | robot/memory.py earlier_view(); reviews/20261010-210536-87090-review.md |
| A hand or the booth background sits in two crops of different objects held in one spot | The MaxSim score of two lookalike objects rises (black and silver laptop 0.835) and the answer says "not sure" at `same` 0.86; a closer lookalike scores above it | Treat as a limit; tune `same` in the Settings page | research/same-object.md |
| A yes/no comparison of the scene ("Have you seen this before?", "Is this the same as before?") with nothing held up | The robot answers "Hold it up, and I will compare." when the visitor means the scene | Accept it for the booth; route scene questions to sightings if a visit shows it | research/same-object.md |
| An object swapped in hand within about one second of the question | The pre-swap frames sit in `now.shots`, so the score mixes both objects | Take crops only after the focus settles; accept it for the booth | research/same-object.md |
| Two lookalike instances (two mugs of one model) | MaxSim up to 0.874 (E, D154), so the answer says "looks like the same mug", which is true for lookalikes | None; the wording stays "looks like" | research/same-object.md |
| Qualifiers outside the word lists ("last night", "at the office") still select the newest RAM frame | An answer from the wrong observation | Extend `_WHEN_WHERE` when observed | robot/memory.py; same review |
| Speech during a caption prefill waits for the first generated token before it interrupts | A slower next turn | Measure foreground delay in the paired run | robot/brain.py caption(); reviews/20261010-215023-40827-review.md |
| An interrupted or empty idle caption is retried on the next idle check | Wasted GPU work | Suppress unchanged retries until a new view or a question needs it | robot/main.py _describe_idle(); same |
| Speech during playback or its 0.3 s tail is discarded (half duplex) | A visitor cannot interrupt the robot | Measure normal follow-ups first; echo cancellation only if interruptions matter | D152 |
| A tunnel failure clears the page's unit reference | Stop is disabled until Start reattaches | Press Start, then Stop | tools/talk.py; reviews/20261010-225408-11584-review.md |
| A recall answer can add an extra article to captions starting with "this", "one", or "five" | Awkward speech | Extend the determiner list if heard | robot/memory.py showed() |
| An Ignore whose offer refreshes during embedding is rejected | The visitor presses again | Measure rejection rate in the live UI check | D151 |
| Naming fixtures paste objects with no person | No focus forms, naming not tested | Held-object scenes or the live day | V1-B report |
| A missed face on a person track that another person took over goes on with the earlier conversation | A told name and history reach the new person | Require the held face to be seen within the last turn | robot/main.py _converse() |
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

## File source decode errors (fixed during cleanup, 2026-10-15)

A later video decoding or seeking error stays set in FileCamera until a new source is shown. Every reader receives that error, and the detector publishes it through `detect_failed`. Regression checks cover both failures after another reader receives the error first. The evaluator therefore rejects a failed source instead of scoring a frozen frame.

Recorded-camera qualification also stops on a decode or seek failure, including an overstated AVI frame count. Replace the damaged recording and restart the session. This strict behavior keeps a frozen frame from appearing healthy; live USB capture uses a different source.

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

- FileCamera still images kept their original timestamp until 2026-10-12, so recognition rejected them after 0.75 seconds and the focus never became steady. `latest()` now stamps a still with the current time. Comparisons recorded before that change used recurring fixture timestamps; replays of stills after it exercise recognition and the focus as a live camera does. Evidence: reviews/20261010-140209-99264-design.md and robot/camera.py FileCamera.latest().
- The recorded knowledge-more-2 question splits into two answered lines (J). Keep the existing VAD/ASR implementation and score the split as a failure. Evidence: the same recorded replay; compare its occurrence across arms before drawing a model conclusion.

## Compact UI

- Removing a view reloads the gallery, resets its scroll position, and collapses Edit memory. Preserve the affected card state if repeated removal becomes disruptive.
- Evidence ages update when evidence changes. After a long idle period, the relative time can become stale. Refresh time labels if visitors encounter this.
- Stop and disconnect now reset the mute icon, accessible state, and disabled audio controls in `clearLive()`.

## Bounded overlay persistence

- A size dip followed by a detection gap can extend an undersized outline beyond its original size grace, for at most the 200 ms missing-detection grace. Action authority remains absent. If this becomes visible, also bound undersized carry by publication time minus admission time.
- The paired recorded-detection benchmark uses confirmed tracks for overlap suppression. Production also checks unconfirmed replacements, so the reported nine-frame outline gain can overstate production behavior. Use all matched detections when this comparison next informs a decision.

## Voice ignore (D164)

- A bare "Ignore that." meant as "disregard what I said" ignores the focused object. Restore in the camera card undoes it. No fix for v1.
- Anyone can say "Ignore that" over another visitor's named object and hide it for everyone, as the camera card already allows.
- Restore has no voice command; it stays in the camera card.
- "When did you last see it?" with a pronoun goes to the brain, not the named-object path (live 2026-10-12).
- If the speech-start focus object is unnamed, has lost the focus, and was never offered, "Ignore that" answers "I lost it." (review, D164).

## Live chat (D165)

- Speech without the wake word flips the status to "Hearing you", so the closed-conversation note can flicker in a noisy room. A short hold on the note would fix it.
- While `hiding` is set after "forget me", `_log` still appends background (unwoken) turns to the chat, so overheard speech can appear on screen.

## Camera and crop encoder (D167, D168)

- DINOv3 weighs shape over color, in recognition and in same-object answers: the dev black and silver laptop pair scores 0.882 ("same" at 0.857), and live a black controller showed the green name of a taught white one. Parked for a test in better light (D169).
- A gallery taught without the turning window (the visitor stops turning at once) gives 64 false matches against DINOv2's 31 on the viewpoint benchmark, at the same recognized-view gain. The window policy is unchanged at 108 false matches.
- At 15 fps in dim light, 1080p decoding costs 0.33 more CPU cores than 720p; the grain is still visible in dim rooms, and more light remains the real fix.
- The detector vocabulary has no game controller: a taught Xbox controller votes "book" and "camera" (live 2026-10-12). Names and crops still work; spoken answers avoid detector labels for same-object questions.
- With two named objects in view and neither held, "this one" cannot be resolved; there is no pointing or hand detector.
- A crash between deleting the old things shard and the new shard's first write loses the carried visitor records and Ignore rules (review, D168). A future encoder migration must also delete the sightings tagged with retired object ids: they have no visitor field, so "forget me" cannot reach them (done by hand on 2026-10-12).
- An unheld object in the teaching zone loses the target to anything inside a person box, such as a bottle at the side; "Ignore that" aimed at an unheld focus picks the held object instead.
- If the camera does not offer 1920x1080, OpenCV falls back to another size and the resize to 1280x720 distorts the aspect ratio.
- A track lost and re-detected with a new id between two turns counts as a changed view and drops the robot's answers; a swap in hand that keeps one track counts as unchanged. An idle prefill reads the tracks when its job runs, so a queued image can carry newer track ids.
- A same-object question embeds every earlier hold of the conversation in one batch; the largest batch and its effect on face cadence are unmeasured.
- "Same one as before?" without a leading verb, "Do you recognize this?", and "Am I holding the same controller?" (no past cue) still go to the brain, which says yes.
