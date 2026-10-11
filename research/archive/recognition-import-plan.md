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

Dylan's observation (2026-10-11): the course robot also adds many false positives to its memories. We tested its masking (rejected) and import its confirmation concept and memory tab, with admission rules it lacks.

## Our known gaps this plan targets

- Changed cup viewpoints: 121/164 (73.8%) recognized (J, D145).
- Re-identification bench: true matches 15/22 phones and 15/35 teddy bears at zero false matches; its queries change background, side, size, and light (E, `bench/results/2026-10-08-reid-1791502259.jsonl`).
- D148: crops keep background pixels; two objects with one name can leave neither recognized.
- Owner is not built (`research/owner-location.md`); "my phone" from two visitors is one point today.

## Evidence that shapes the order

- D141 (J): six diverse views gave the cup the same 92 fresh matches as the current three. Gallery growth alone is unsupported; views help only when they add real new viewpoints (explicit reteaching, confirmed near matches).
- `bench/reid.py` enrolls three views, uses the nano detector, and drops missing crops from the descriptor denominators. It cannot qualify 24-view safety as it stands.

## Done (D154)

- Step 0: every D145 cup miss is a descriptor score under the threshold during a viewpoint change; the detector found the cup on every frame (`bench/results/2026-10-11-crop-arms-1791693406.json`).
- Steps 2 and 3: masking lost hits and is not adopted; the teaching window beat fixed and simulated-confirmation galleries on 17 viewpoint videos (`bench/results/2026-10-11-gallery-1791694947.json`). Built: a 6 s window after naming, near-duplicate skipping, a 24-view cap with oldest-out keeping the first view, live settings on the page.

## Step 1: owner contract (design gate)

Revised after `reviews/20261011-014311-87056-design.md` (RETHINK).

### Alternatives

- **A. Re-keyed owners.** The point id is uuid5(owner key, name), with owner keys `person:`, `told:`, and `guest:`. Promotion (a guest tells a name or enrolls) moves every point, sighting link, Ignore copy, and pending window to the new key, across the things, memory, and people shards.
- **B. Stable visitor id (chosen).** Each conversation gets one random visitor id. Objects carry `owner = <visitor id>`; their point ids are random, and (owner, name) is a keyword-indexed payload pair. A guest or told visitor has a record in the things shard (display name, created at its first object). An enrolled person's visitor id is stored on the person point, which alone makes the visitor `person`. Each promotion is one write: telling a name updates the visitor record; enrolling adds the visitor id to the person point. No object, sighting, or link moves.
- **Measured by** the same Mac test script for both on paper, and B built: writes per promotion (A: one per point plus links in three shards; B: one), the failure window when the robot restarts mid-promotion (A: partly moved objects; B: none), and the checks in "Acceptance" below. B wins on every count without a build of A, so only B is built.

### Contract

- **Visitor resolution.** One function resolves the visitor once per turn, before any object action: a face match to an enrolled person gives that person's visitor id (stored on the person point); otherwise the conversation's visitor id. A new conversation (`_converse` returns new) allocates exactly one new visitor id and guest number. An undetectable visitor change inside one conversation stays a known gap.
- **Kinds.** A guest is "Guest N" (a persistent counter). Telling a name sets the record's display name. Face enrollment stores the visitor id on the person point; the person's name then takes display precedence. Existing enrolled people get a visitor id when the new schema initializes. Enrolling a name that already belongs to a different face is refused ("I already know someone called Ana"), so a second Ana never inherits the first Ana's objects.
- **Possessives.** "My mouse" uses the current visitor. "Ana's mouse" resolves only to an enrolled person named Ana; other told names are not addressable. An unresolved possessive answers "I don't know which mouse is Ana's" and never falls through to general sightings. The category fallback in `Things.named()` ("my watch" finds "my grandmother's watch") is constrained to the resolved owner.
- **Labels.** "Dylan's mouse" on the overlay and the page; speech says "your mouse" to the owner.
- **References.** Sightings and Ignore exclusions reference the object point id, not the name. `Memory.forget_named()` becomes forget by object id.
- **Views.** The object payload keeps one metadata entry per vector, in order: view id, time, source (`taught` or `window`), and a 160 px JPEG thumbnail under `shared/memory/things/thumbs/<view id>.jpg`. A view's thumbnail is its own file, so removing one view never touches another view's evidence. Eviction at the cap deletes the evicted thumbnail.
- **Deletion.** "Forget my mouse" deletes that owner's object with its linked turns and sightings, thumbnails, and the item Ignore points that exclude it, and ends a teaching window on it. "Forget me" deletes, in this order: the visitor's stored turns and linked evidence, thumbnails, then the visitor's objects, visitor record, and item Ignore points in one things-shard operation, and last the person point for an enrolled person. Each step keeps the references the next one needs, so an interruption can be retried; a startup sweep deletes thumbnails no view references. Category ignore rules ("ignore chairs") stay.
- **Existing data.** The Jetson holds development objects only; no booth data exists. On the first start of the new schema the robot closes and backs up the things shard (`things-backup-<date>`), then starts it empty. No name-only path remains.

### Acceptance (Mac tests, then one Jetson script)

Two visitors who both say "this is my mouse" get two objects. One owner who teaches two different mice gets one object with both views. A guest who tells a name, then enrolls, keeps the same objects. A second "Ana" cannot enroll over the first. Restart keeps owners, labels, and views. "Forget my mouse" during a teaching window stops admissions and removes files. "Forget me" removes all of a guest's objects. Ignore still hides an excluded object. On the Jetson: Edge p99, detection fps, RAM, and paging with `tegrastats`.

Cut from this step: rename, the memory tab, location, pagination, and voice confirmation (later steps). Rename and its (owner, name) collision rule come with the memory tab.

## Step 4: memory tab

A second tab in `tools/talk.html`, served by `robot/view.py` and proxied by `tools/talk.py`.

- **Objects grouped by owner.** A card per object with its label, all view thumbnails (time, location, and source), last seen time and place, and the sighting count.
- **Actions.** Rename, forget the object, and remove one view, each with a confirmation step and the object reference plus view id, so a stale page cannot delete the wrong item. Removing the last view forgets the object. Edits go through the serial owner.
- **Also.** Ignored items with Restore, and the location setter from `owner-location.md`.
- **Better than the course robot.** All views visible at once; live updates from a memory version number in `/state`; keyboard operable; alt text on each thumbnail; works at phone width. Thumbnails are bounded in size and the list is paginated.

## Step 5: voice confirmation of near matches

The robot asks "Is this your mouse?" when a crop scores just under the threshold. A "yes" admits that view as `confirmed` through the same `add_view` path as the window.

The robot asks only when all of these hold:

1. A conversation is active and the candidate's owner is the current visitor by face or told name.
2. The conversation has a blank: no speech, no turn, and no queued job for at least 4 s after the last answer (tuned live).
3. The near match is stable: the same focused track scored in [threshold − 0.05, threshold) on at least two queries over at least 3 s, and it never crossed the threshold. A true match in the meantime cancels the question.
4. No other question is pending; "What should I call it?" has priority.
5. Rate limits: one question per track, at most one per 60 s, at most three per conversation. A "no" mutes that object for that track's life.

- **Pinned question.** The pending question stores the object reference, the copied crop vector, the visitor, the track epoch, and an expiry (the 60 s follow-up window). Before admission, code checks that all still hold. A "yes" after expiry, from another visitor, or after the track changed admits nothing.
- **Reply.** "Yes", "yeah", "it is" accept; "no", "not mine" decline; any other line is an ordinary turn and drops the question. No wake phrase is needed inside the follow-up window.
- **Measure.** Scripted replays: questions per minute in a long session, no question during speech, false confirmations (a "yes" meant for something else), and recognition of the same viewpoint after a "yes".

## Tuning settings (Dylan, 2026-10-11)

The real camera and room differ from the bench videos. Benches choose policies; values are live settings on the page, saved in `shared/` like the volume, with bench defaults: match threshold, near-match band, teaching-window floor and length, the minimum time between admissions, the view cap, and the question delay and rate limits. A change applies to the next query without a restart.

## Order and gates

1. Step 1: design gate, build, task review, Jetson check.
2. Step 4 (memory tab), then step 5 (voice confirmation), each with a task review.
3. A human checklist in `STATE.md`: teach "my mouse" twice with two mice, turn an object during the window, a changed-viewpoint question answered yes and no, memory tab edits, settings changes, and "forget me". Remaining conversation, latency, and paging gaps stay visible.
