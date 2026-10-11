# Booth behavior: focus, labels, memory, and turns

Current behavior follows D140–D147. Dylan accepted live release `7f67670fa91e` as good enough. The final change keeps the selected "???" style through confidence dips on the same admitted object. [STATE.md](../STATE.md) owns live status. Earlier D63/D77 proposals remain historical in [DECISIONS.md](../DECISIONS.md); they do not describe the shipped interface.

## Visitor flow

1. Select **Start**, wait for **Listening**, and say "Hey Edgy". Follow-up questions work for about a minute after an answer finishes.
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

Raw size and confidence still govern focus selection, teaching, crop queries, and writes. The 120px minimum scales with source width. Drawing uses smoothed source geometry, matched-track LOW continuation, and the existing 200ms size grace. Actual gaps remove outlines; size expiry can also hide them briefly. Ignore and pending preference verification suppress drawing. No missing-track drawing cache was added.

## Recognition and item controls

Qdrant Edge stores explicitly named objects as crop multivectors. The [Mac interface guide](mac-audio-interface.md#teaching-recognition-and-item-controls) defines reteaching, recognition continuity, negative examples, and Restore. Unknown tracks stay in RAM; ordinary conversation records keep text without images. Face identity requires consent and source-specific verification.

## Runtime and practical limits

YOLOE-26s at 384x640 with TensorRT FP16 is the development default; nano remains the fallback. Detector-paced sources use one Recognition owner and replaceable latest slot. Object crop work stays bounded to three per second. View has one 15fps pacing deadline and validates source age, session, gallery, epochs, and viewer before emission.

The wake phrase is "Hey Edgy". The Mac client suppresses microphone input during playback. The view shows status, streamed answers, and supplied evidence. This session made no voice behavior changes.

The accepted interface can still blink after genuine detector losses or size expiry. Similar objects, changed viewpoints, occasional conversation stalls, and paging remain limits. External cup recognition reaches 73.78%; this does not establish general viewpoint coverage. Physical audible latency and the broader milestone targets remain open in STATE.md.

## Evidence

- [D147 accepted box behavior](../bench/results/2026-10-10-d147-box-continuity.json).
- [D143 completed-source delivery](../bench/results/2026-10-10-d143-face-delivery.json).
- [D144 false-claim rule](../bench/results/2026-10-10-d144-phone-recovery.json).
- [D145 negative vectors and Restore](../bench/results/2026-10-10-d145-ignore-continuity.json).
- [D146 detector and phone flow](../bench/results/2026-10-10-d146-detector-default.json).
- [Lessons and rejected alternatives](lessons.md), including the superseded D63/D77 auto-view and speech-gate proposals.
