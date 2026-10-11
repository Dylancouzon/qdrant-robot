# Recognition import from the course robot (plan)

Revised 2026-10-11 after design gate `reviews/20261011-002548-97450-design.md` (GO WITH CHANGES), branch `spike/recognition-import`. Source: `refs/qdrant-edge-memory-robot` (cfc0dd2), the course robot. Dylan reports that it recognizes objects better than ours. This plan imports what can improve our recognition, adds owner-keyed objects, voice confirmation of near matches, and a memory tab. Labels: J measured on our Jetson, E elsewhere, U unverified.

## What the course robot does differently

| Part | Course robot (`robot/brain/detect.py`, `memory.py`, `core.py`) | Ours (`robot/things.py`, `robot/main.py`) |
| --- | --- | --- |
| Crop | YOLOE segmentation mask, dilated 7x7, outside filled grey (124), 12% box margin | Box crop with background pixels, padded square with grey 114 (D148 parked masking) |
| Crop choice | Best crop since the last query: confidence x sqrt(area) x capped Laplacian sharpness | Newest view; three shots 0.33 s apart |
| Encoder | CLIP ViT-B/32 vision, threshold 0.90 | DINOv2-small CLS plus mean patch, threshold 0.822 (D57, D64) |
| Storage | One point per taught view, one vector, no cap | One point per name, multivector of at most three views, MaxSim |
| Reteaching | Always adds a view | Adds views only when the new crop already matches; otherwise replaces every view |
| Near match | Within 0.05 under the threshold: an orange "guess"; one tap teaches that crop | Nothing |
| Memory tab | Object cards: views and sightings, rename, forget, drop one view, ignored list, location | None; the page has Ignore and Restore only |

Dylan's observation (2026-10-11): the course robot also adds many false positives to its memories. We import its masking, crop choice, and confirmation concept, and add admission rules it lacks.

## Our known gaps this plan targets

- Changed cup viewpoints: 121/164 (73.8%) recognized (J, D145).
- Re-identification bench: true matches 15/22 phones and 15/35 teddy bears at zero false matches; its queries change background, side, size, and light (E, `bench/results/2026-10-08-reid-1791502259.jsonl`).
- D148: crops keep background pixels; two objects with one name can leave neither recognized.
- Owner is not built (`research/owner-location.md`); "my phone" from two visitors is one point today.

## Evidence that shapes the order

- D141 (J): six diverse views gave the cup the same 92 fresh matches as the current three. Gallery growth alone is unsupported; views help only when they add real new viewpoints (explicit reteaching, confirmed near matches).
- `bench/reid.py` enrolls three views, uses the nano detector, and drops missing crops from the descriptor denominators. It cannot qualify 24-view safety as it stands.

## Step 0: classify the 43 cup misses

Before any change, sort each miss in the D145 replay (release `a9299a617f4c`) into detector miss, crop not eligible, descriptor score under threshold, or display failure. This uses existing replay output and decides which later steps can move the number. Descriptor misses favour steps 2 and 5; detector misses favour none of them.

## Step 1: owner and deletion contract (design gate)

- **Identity is separate from display.** Owner keys have three kinds. `person:<name>`: the speaker's face matched an enrolled person (`People` keys points by name). `told:<name>:<n>`: an unenrolled visitor told a name in this conversation (`Robot.told`), with the conversation's guest number, so two visitors who tell the same name stay apart; it is unverified, so it never equals `person:<name>`. `guest:<n>`: neither, with `n` from a persistent counter, one per conversation. Display names: "Ana", "Ana" (told), "Guest 3".
- **Point.** One point per (owner id, normalized name): uuid5 of both. The same owner's reteach always appends, even for a different physical object (Dylan). Different owners get different points.
- **Promotion.** Points move to a stronger key only within the same conversation: `guest` to `told` when the visitor tells a name, and `guest` or `told` to `person` when the visitor enrolls by face consent. If the target already has a point with that name, the views merge up to the cap, oldest-out. Nothing ever moves to `person` without the enrollment.
- **Rename.** Renaming onto a name the same owner already uses merges the two points the same way.
- **Labels.** "Dylan's mouse" on the overlay and the memory tab. Speech says "your mouse" to the owner and "Dylan's mouse" to others. Guests show as "Guest 3's mouse".
- **References everywhere.** Every caller that takes a bare name today takes an object reference (owner id, name): retrieval, sightings, Ignore exclusions, display associations, `Things.forget`, and `Memory.forget_named()`. "My mouse" resolves with the current visitor's owner id; "Dylan's mouse" with Dylan's.
- **Views.** Each view has a stable id and payload metadata in vector order: masked thumbnail path, time, location, source (`taught` or `confirmed`), and the turn that admitted it. Removing a view removes its vector, thumbnail, and turn link.
- **Deletion.** "Forget my mouse" deletes that point, its thumbnails, linked turns and sightings, any pending write or question for it, and the memory tab's cached entry. "Forget me" does this for every point the person owns. Existing unowned points stay keyed by name until reteaching creates an owned point.
- **Concurrency.** Gallery reads and edits run through the serial memory owner. Code releases the detector lock before it waits on that owner.

## Step 2: masked crops, compared separately from best crop

- **Mask.** YOLOE-26s-seg outputs mask coefficients (columns 6 to 37 of `(1, 300, 38)`) and prototypes `(1, 32, 96, 160)`. `robot/detect.py` copies only `output0` today. On a frame where a crop is embedded, also copy the prototypes (1.97 MB fp32) and keep the coefficient row with its detection. The mask comes from `sigmoid(coef @ protos)` in letterbox space, is upsampled, reversed through the letterbox offset and scale, cropped to the box, thresholded at 0.5, dilated 7x7, and the outside filled with grey 114.
- **Source lifetime.** TensorRT overwrites its buffers every inference, so a view keeps a copy of its frame, box, mask, time, and track epoch together. Teaching, recognition, and thumbnails use the same masked pixels.
- **Persisted evidence.** `_bind()` stores the masked crop, not the box crop. Masking reduces incidental pixels; it does not guarantee that no face remains.
- **Best crop.** A separate arm: quality = confidence x sqrt(area fraction) x min(Laplacian variance, 1200), times mask fill ratio. Arms: box/newest (baseline), masked/newest, box/best, masked/best.
- **Measure.** Extend `bench/reid.py` to the deployed 26s detector, count missing crops as misses, and add temporal crop choice. Calibrate on development instances and test on frozen separate instances. Then the D145 cup and D141 phone replays on the Jetson, paired with the current release, with RAM, detection fps, decode rate, and Edge p99. Separate matting (rembg class) is deferred.

## Step 3: gallery growth, cap measured

- **Cap.** 24 is the candidate. Measure 3, 8, and 24 views per point in the extended bench with real additional viewpoints, same-kind distractors, and competing owners with same-kind objects. Re-derive the threshold; zero false matches at the chosen cap.
- **Admission.** A view enters only from an explicit teaching turn or a confirmed near match, never from automatic recognition. It needs a mask covering at least 30% of its box (tuned on development data), a box above the crop-size floor, sharpness above a floor, no person or face class (D153), and cosine below 0.97 to every stored view.
- **Retention.** Keep the first taught view and drop the oldest other view. No similarity-based outlier rejection, because a second physical object is visually distant by design.
- **Measure** admission yield (taught crops that pass), restart persistence, and deletion.

## Step 4: memory tab

A second tab in `tools/talk.html`, served by `robot/view.py` and proxied by `tools/talk.py`.

- **Objects grouped by owner.** A card per object with its label, all masked view thumbnails (time, location, taught or confirmed), last seen time and place, and the sighting count.
- **Actions.** Rename, forget the object, and remove one view, each with a confirmation step and the object reference plus view id, so a stale page cannot delete the wrong item. Removing the last view forgets the object. Edits go through the serial owner.
- **Also.** Ignored items with Restore, and the location setter from `owner-location.md`.
- **Better than the course robot.** All views visible at once; live updates from a memory version number in `/state`; keyboard operable; alt text on each thumbnail; works at phone width. Thumbnails are bounded in size and the list is paginated.

## Step 5: voice confirmation of near matches

The robot asks "Is this your mouse?" when a crop scores just under the threshold. A "yes" admits that view as `confirmed`.

The robot asks only when all of these hold:

1. A conversation is active and the candidate's owner is the current visitor by face or told name.
2. The conversation has a blank: no speech, no turn, and no queued job for at least 4 s after the last answer (tuned live).
3. The near match is stable: the same focused track scored in [threshold − 0.05, threshold) on at least two queries over at least 3 s, and it never crossed the threshold. A true match in the meantime cancels the question.
4. No other question is pending; "What should I call it?" has priority.
5. Rate limits: one question per track, at most one per 60 s, at most three per conversation. A "no" mutes that object for that track's life.

- **Pinned question.** The pending question stores the object reference, the copied masked crop, the visitor, the track epoch, and an expiry (the 60 s follow-up window). Before admission, code checks that all still hold. A "yes" after expiry, from another visitor, or after the track changed admits nothing.
- **Reply.** "Yes", "yeah", "it is" accept; "no", "not mine" decline; any other line is an ordinary turn and drops the question. No wake phrase is needed inside the follow-up window.
- **Measure.** Scripted replays: questions per minute in a long session, no question during speech, false confirmations (a "yes" meant for something else), and recognition of the same viewpoint after a "yes".

## Tuning settings (Dylan, 2026-10-11)

The real camera and room differ from the bench videos. Benches choose policies; values are live settings on the page, saved in `shared/` like the volume, with bench defaults: match threshold, near-match band, teaching-window floor and length, the minimum time between admissions, the view cap, and the question delay and rate limits. A change applies to the next query without a restart.

## Order and gates

1. Step 0 (no gate, records only).
2. Design gate for step 1, then build it with a task review.
3. Step 2, then step 3, each with paired benches and a task review.
4. Step 4, then step 5, each with a task review.
5. One integrated Jetson replay, then a human checklist in `STATE.md`: teach "my mouse" twice with two mice, a changed-viewpoint question answered yes and no, memory tab edits, and "forget me". Remaining conversation, latency, and paging gaps stay visible.
