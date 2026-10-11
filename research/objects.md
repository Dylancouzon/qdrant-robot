# Named objects

The robot recognizes objects a visitor names ("this is my mouse") by DINOv2-small crop vectors stored as a multivector in the things shard and matched by MaxSim (D57, D64). This file describes how teaching, matching, owners, and the Memory tab work now (D154 to D156). The plan that led here is in [archive/recognition-import-plan.md](archive/recognition-import-plan.md). Labels: J measured on our Jetson, E elsewhere.

## Teaching

- A naming turn stores the focused track's crops, then opens a teaching window: the robot says "Turn it slowly so I can see all sides" and adds views from that same track for `window_s` (6 s).
- The window admits one view per `window_gap_s` (1 s), only above `window_floor` (0.70), and never while another same-label track overlaps the taught one. It ends on time, track loss, or a memory change.
- `add_vectors` in `robot/things.py` skips a view whose cosine to a stored view is at least `duplicate` (0.95) and keeps at most `views_cap` (24) views, dropping the oldest except the first.
- On 17 viewpoint videos the window recognized 530 of 816 later views, against 397 for fixed galleries (E, `bench/gallery.py`). Background masking lost hits (241 against 263 of 360) and is not used (`bench/crop_arms.py`).

## Owners

- Each conversation has one visitor id. An object point carries `owner`, `name`, and `key`; one point exists per owner and name, and the same owner teaching a second mouse adds views to it.
- Labels read "Dylan's mouse" or "Guest 2's mouse". An enrolled face stores its visitor id on the person point; a told name updates the visitor record. "Ana's mouse" resolves only to an enrolled Ana.
- `type`, `owner`, and `key` have keyword indexes, created on every open. `things.score` is 2.29 ms p99 with 200 objects of 24 views (J).
- "Forget me" deletes turns and evidence, then thumbnails, then the visitor's objects and record, and the person point last.

## Near-match question

When the focused object scores within `guess_band` (0.05) under `match` (0.822) for `ask_delay_s` (3 s), the robot asks "Is this your mouse?" It asks only after `ask_blank_s` (4 s) of silence, at most `ask_max` (3) times per conversation, 60 s apart, and once per track. "Yes" adds that view if the track is still in focus; "no" mutes it.

## Page

- **Settings** tab: sliders save when released. Recognition threshold, teaching time, and question count stay visible; other values are under Advanced. Values are validated and saved to `shared/settings.json`; a change applies to the next query.
- **Memory** tab: object cards grouped by owner show three thumbnails at a time, or one on a phone. Arrows and native scrolling reach every view. Edit memory exposes Remove view and Forget. Thumbnails are 160 px JPEGs in `shared/memory/things/thumbs`. Edits run on the conversation worker.
- **Live** tab: the camera fills most of the page. Four voice examples sit under it; session controls overlay the camera, and conversation bubbles use a scrollbar without visible speaker headings. The Qdrant Edge strip shows saved object thumbnails and readable sources. Details exposes search results and the retrieval-preparation timer, which includes work beyond Edge queries. Summaries resolve once per turn, stay out of logs, and clear when their sources expire or are deleted.

## Camera

The live feed is grainy in a dim room because the camera's auto exposure raises its internal gain; our 960 px preview encode adds no measurable noise (J, 2026-10-11). Requesting 15 fps instead of 30 fps did not lower the noise (7.34 against 6.29, J). More light on the subject is the fix.

The page uses the official Qdrant logo, Amaranth (`#DC244C`), Neon Blue (`#6047FF`), and black (`#0B0F19`) from [Qdrant Brand Resources](https://qdrant.tech/brand-resources/). Mona Sans is served locally from `tools/assets/` with its OFL license, so the page needs no external font requests.
