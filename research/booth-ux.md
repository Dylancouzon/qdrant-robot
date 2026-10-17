# Booth behavior: focus, labels, memory, and turns

Current behavior follows D140–D147 and D159. The selected "???" and named-object outlines bridge detection gaps for at most 200 ms. Movement increases the drawing blend so the boxes follow motion while stationary jitter remains smoothed. [STATE.md](../STATE.md) owns live status. Earlier D63/D77 proposals remain historical in [DECISIONS.md](../DECISIONS.md); they do not describe the shipped interface.

## Visitor flow

1. Select **Start**, wait for **Listening**, and say "Hey Edgy". A wake-only phrase greets the freshly recognized selected visitor by name. Unknown visitors receive "Hi."; ambiguous selection keeps its existing clarification. A question after the wake phrase receives its normal answer. Follow-up questions work for about a minute after an answer finishes.
2. Hold up one object and say "Track this as my wallet" or "This is my phone". "Track this" alone makes the robot ask for the name.
3. Ask what the robot sees, what you showed it, or where it last saw a named object.
4. Select an eligible item and press **Do not track that** to save negative example vectors. **Restore** removes that preference.
5. Use explicit face-enrollment consent before asking the robot to remember a person. Forgetting deletes linked records and files.
6. **Mute** keeps the session connected with silent input. **Stop** releases the client's devices and Jetson session.

See [Mac audio interface](mac-audio-interface.md) for launch commands, camera playback, authentication, and device behavior.

## Focus and drawing

The page shows all unambiguous known objects, one orange "???" teaching focus, and admitted grey object outlines. Verified face boxes can have enrolled names; body outlines are omitted. Current face identity remains tied to its verified source pixels.

Stable, eligible unknown objects can become teaching candidates. Area, centrality, recent movement, held-object overlap, and teaching-zone placement raise priority. Scenery loses focus eligibility after sustained stillness. Held and zone cues do not exclude every other stable object.

New unknown assignments occur at most once per three seconds. Loss and recognition can remove an assignment before the next replacement. A challenger needs sustained priority after the existing hold interval. The selected admitted box keeps its "???" style through matched LOW-confidence observations. This style does not grant teaching or action authority to a weak crop.

Raw size and confidence still govern focus selection, teaching, crop queries, and writes. The 120px minimum scales with source width. Drawing uses smoothed source geometry, matched-track LOW continuation, and a 200 ms size grace. During a missing detection, the existing last box can draw for 200 ms after its last matched capture. The selected frame must follow that observation, and wall time also expires the drawing. A returning detection, overlapping replacement, Ignore, or pending preference check suppresses the carried outline. Publication checks these conditions again after JPEG encoding. Missing tracks never enter source geometry, teaching, crops, writes, or fresh recognition authority.

## Recognition and item controls

Qdrant Edge stores explicitly named objects as crop multivectors. The [Mac interface guide](mac-audio-interface.md#teaching-recognition-and-item-controls) defines reteaching, recognition continuity, negative examples, and Restore. Unknown tracks stay in RAM; ordinary conversation records keep text without images. Face identity requires consent and source-specific verification.

## Runtime and practical limits

YOLOE-26s at 384x640 with TensorRT FP16 is the development default; nano remains the fallback. Detector-paced sources use one Recognition owner and replaceable latest slot. Object crop work stays bounded to three per second. View has one 15fps pacing deadline and validates source age, session, gallery, epochs, and viewer before emission.

The wake phrase is "Hey Edgy". The Jetson suppresses its microphone input during playback and the following 0.3 s. The view shows status, streamed answers, and supplied evidence.

The interface can still blink after detection losses longer than 200 ms or size expiry. Face names still require positive recognition on the exact displayed source; negative results clear them immediately. Similar objects, changed viewpoints, occasional conversation stalls, and paging remain limits. External cup recognition reaches 73.78%; this does not establish general viewpoint coverage. Physical audible latency and the broader milestone targets remain open in STATE.md.

## Evidence

- [D147 accepted box behavior](../bench/results/2026-10-10-d147-box-continuity.json).
- [D143 completed-source delivery](../bench/results/2026-10-10-d143-face-delivery.json).
- [D144 false-claim rule](../bench/results/2026-10-10-d144-phone-recovery.json).
- [D145 negative vectors and Restore](../bench/results/2026-10-10-d145-ignore-continuity.json).
- [D146 detector and phone flow](../bench/results/2026-10-10-d146-detector-default.json).
- [Lessons and rejected alternatives](lessons.md), including the superseded D63/D77 auto-view and speech-gate proposals.

## Bounded persistence check

The paired Mac check keeps stationary jitter at 3.08 px RMS (E). At 20 px per detected frame, final movement lag falls from 37 to 18 px; at 40 px, it falls from 74 to zero (E). On the first 675 frames of an existing development clip, selected focus without an outline falls from 111 to 102 frames (E). This comparison uses confirmed tracks; production also suppresses carry around unconfirmed replacements. Its nine-frame gain can therefore overstate the production gain. It measures drawing, not detector quality.

The full-model live Jetson check receives 208 JPEGs during one oracle-text turn, with 139 ms median source age and 172 ms p95 (J). Its isolated memory has no enrolled faces, so named-face transitions remain covered by runtime tests rather than live acceptance. See `bench/results/2026-10-11-overlay-1791732278.json` and `bench/results/2026-10-11-overlay-1791732322.json`. Recreate the baseline with `git show c47f593:robot/focus.py > build/overlay/focus_baseline.py`, then run `python -m bench.overlay --baseline build/overlay/focus_baseline.py`.

## Named wake greetings

The identity answer path forms a wake-only greeting from the existing speech-start face match. The stored conversation name and continued body track supply no name for this answer. Pending confirmation and face consent keep their existing priority. Wake-only greetings remain in the transient conversation and do not become stored personal statements. Local real-Edge checks with synthetic face vectors cover names, aliases, absent or ambiguous identity, deletion, consent, and attached questions. See `bench/results/2026-10-16-wake-greeting.json`.

The [task review](../reviews/20261016-220041-93749-review.md) passed. Seven targeted regressions also pass on the Jetson with synthetic faces (J). The deployed release and live-test status are recorded in STATE.md.
