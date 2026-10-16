# Robot interface and audio

The robot hears and speaks through its own USB audio device on the Jetson (ALSA `plughw:CARD=Device,DEV=0`, constants in `robot/audio.py`). The Mac page is the monitor and control UI: Start, Stop, Mute, a speaker volume slider, the camera view, and the transcript.

D147's accepted live release is `7f67670fa91e`. It keeps the selected "???" style through confidence dips on the same admitted object. Dylan accepted this checkpoint as good enough. [STATE.md](../STATE.md) owns current releases, processes, and the next action. [DECISIONS.md](../DECISIONS.md) and [lessons.md](lessons.md) retain the development history.

## Start and stop

Run `.venv/bin/python tools/talk.py --release RELEASE_ID`, using the current release from STATE.md. Open `http://127.0.0.1:8765`, select **Start**, and wait for **Listening**. Start attaches to the Jetson unit `qr-robot` (token and release read from its environment), or starts it through `tools/jetson.py run robot`. Deployment alone starts no microphone or models. The monitor waits for a successful authenticated `/state` response before publishing readiness. Failed camera requests clear the image state, so the existing page poll retries automatically.

Say "Hey Edgy" to start a turn. Follow-up questions work for about a minute after an answer finishes. **Stop** stops the `qr-robot` unit and closes the tunnel. Closing the page, Ctrl-C, or losing the tunnel leaves the robot running and listening; Start attaches again. The unit does not start at boot. The local page remains open for another Start.

A transcription or answer-worker exception stops the session and preserves its traceback in the Jetson journal. Pending work is discarded before resources close. Start launches another session after the failed unit stops.

The Mac and Jetson can use the existing Wi-Fi network wherever its coverage reaches. All model inference and robot audio remain on the Jetson. The interface uses the Mac launcher and its SSH tunnel. An isolated hotspot needs another uplink for Internet access. Hotspot setup must use a separate control connection.

**Mute** and the **volume** slider act on the robot through the view's token-protected `/mute` and `/volume` endpoints, proxied by the local page. Mute silences the Jetson microphone input. Volume sets the USB `Speaker` mixer (0 to 100 percent), is saved in `shared/speaker-volume`, and is applied at robot startup. The default is 62 percent, also used when the saved level is unreadable or out of range. If saving fails after the mixer changed, the page shows that the level is set but not saved.

The robot does not hear itself. `Robot.hear` replaces every input chunk with silence while the speaker plays and for `SELF_VOICE_TAIL_S` (0.3 s) after the last phrase, for the USB microphone and replays alike. `Mouth` keeps the gate closed while a phrase is queued or its `aplay` runs, because `aplay` exits after the audio drains, then for the tail after the last sink call returns. A failed `aplay` is logged and the gate reopens.

All models and Qdrant Edge run on the Jetson. The Mac stores no recording. The Jetson retains session logs and generated answer WAVs.

Use one camera viewer. A second MJPEG subscriber replaces the first. Each session has a fresh view token, passed through environment and SSH stdin. The local page proxies camera/state access through its session cookie. Stop clears the live feed and transient conversation.

## What the page shows

The camera shows known object names, one orange "???" teaching focus, and admitted grey object outlines. Person detection supplies internal cues; the page draws verified face outlines instead of body boxes. Face identity uses only the current verified result on its exact source pixels. The status and transcript show Listening, Hearing you, Thinking, and Speaking.

A shared panel beneath the camera gives roughly 70% of its width to retrieved text and image cards. The remaining space shows a Qdrant Edge search map and the current turn's timings. Conversation spans the full height beside the camera and shared panel. Visible pane headings and empty-state explanations are omitted. The map shows reported collections and displayed retrieval entries. Its connections describe the search flow, rather than vector positions or every raw hit. Entry counts can include summarized recall lines and filtered statements. Selecting an object opens its Memory card. Search entries and source IDs stay expandable.

A pinned conversation-style bubble rotates command examples every 12 seconds. It shows the wake phrase as part of each example and uses no extra controls. Tips pause during hover, keyboard focus, hidden tabs, and reduced-motion preferences. Map connections animate when retrieval changes. Ordinary status polls preserve the map and expanded details. Retrieval text stays off the camera image.

The latency values are retrieval preparation, speech-end to first text, and speech-end to the first synthesized phrase. Retrieval preparation includes work beyond Edge queries. Speech-ready time measures the synthesis handoff, rather than physical audible latency. Missing measurements show a dash. Each new turn clears the previous retrieval panel.

The Memory tab groups cards by visitor ID and shows object, view, and visitor counts. Search filters object and visitor names. Refresh reloads the stored objects. Editing preserves the open management controls, gallery position, keyboard focus, and page position. Queued edits keep a visible status and continue polling until their result appears. Confirmed voice deletion clears cached cards and rejects older in-flight reads.

Focus assignments change at most once per three seconds. The selected admitted object keeps its "???" style while a matched detection continues at the existing LOW threshold. Source admission, visibility, Ignore, and pending preference checks still gate drawing. Object outlines bridge detection gaps for at most 200 ms (D159). The existing 200 ms size grace can expire during undersized observations.

Drawing coordinates use source snapshots and smoothing. Raw detector geometry remains authoritative for selection, crops, actions, and writes. Large raw motion, gaps, merges, and Ignore reset drawing history. A displayed "???" can remain visible while its current crop is ineligible for teaching.

## Teaching, recognition, and item controls

Say "Track this as my wallet" or "This is my phone" while showing one eligible object. Held-object and teaching-zone cues raise priority; another stable eligible object can also be selected. Explicit names preserve the visitor's wording independently of detector categories.

Each named Qdrant Edge point belongs to a visitor. Naming starts a learning window that adds distinct views from the taught track. The default limit is 24 views, with the first view preserved. Explicit reteaching appends distinct views to that visitor's object. Recognition alone does not add views. Settings controls the learning window, view limit, and recognition thresholds (D154, D155).

A weak preferred-name match can make one additional global Edge query using the same crop vector. Competing claims abstain. Strong labels require agreeing queries; skipped queries preserve associations. Three actual below-SURE queries remove retained green confidence; below-GUESS misses also clear the verification preference. Weak descriptor and detector evidence together suppress a displayed name. Fresh query scores, source checks, and duplicate protection separately govern writes.

Select an eligible item and press **Do not track that**. Ignore verifies the exact current crop before borrowing a saved object's gallery. Unknown items use only that current crop. Persistent negative vectors live in the Things shard, outside ordinary recognition and recall. A previously matched preference survives two actual queried misses; the third releases it. Skips do not count, so concealment has no fixed elapsed-time bound.

**Restore** removes the preference through the existing serial recognition owner and clears matching display state. It bypasses the conversation queue. Session, gallery, preference-ID, and mutation-time checks still apply. Voice category rules such as "Ignore chairs" remain separate.

Only explicitly named objects keep visual evidence. Unknown tracks stay in RAM. Ordinary conversation memories store text without images. Face enrollment requires consent, and forgetting removes linked records and files.

## Runtime and recorded checks

The default detector is YOLOE-26s, with a fixed 50-word vocabulary, 384x640 input, and TensorRT FP16. YOLOE-26n remains the fallback. See [detector.md](detector.md) for pinned artifacts and preprocessing.

Each detected source enters one replaceable latest slot on the serial Recognition owner. Object crop queries remain bounded to three per second. View uses one 15fps deadline for completion waiting, JPEG rendering, retries, and pacing. Final validation checks source age, session, gallery, track epochs, and viewer authority before emission. Encoding and socket writes stay outside detection locks.

`OBJECT_MIN_SIDE=120` refers to a 1280px source width and scales with frame width. Detector LOW/HIGH are 0.10/0.25; unknown teaching admission is 0.25. These raw gates remain unchanged by the "???" style fix. YuNet uses 640-width input and maps its face result to source coordinates.

For recorded camera playback, add `--camera-file /existing/jetson/fixture.avi` to the launcher. FileCamera starts after warmup in stored orientation. Stop and restart the server without that option for live capture. Use temporary memories for automated controls; keep private media outside git.

## Evidence and limits

- [D147 box continuity](../bench/results/2026-10-10-d147-box-continuity.json): accepted live behavior and the final one-condition "???" fix. Genuine losses and size expiry can still blink.
- [D143 face delivery](../bench/results/2026-10-10-d143-face-delivery.json): completed-source publication and actual MJPEG accounting. Model budgets and source-specific identity guards remain fixed.
- [D144 false-claim suppression](../bench/results/2026-10-10-d144-phone-recovery.json) and [D145 Ignore/Restore](../bench/results/2026-10-10-d145-ignore-continuity.json): bounded development checks, with earlier native failures retained.
- [D146 detector default](../bench/results/2026-10-10-d146-detector-default.json): all 12 original phone checks pass, with 91.43% movement and 91.47% Restore coverage. Conversation stalls and paging remain open.
- [External cup](../bench/results/2026-10-10-d145-external-cup.json): 73.78% recognition across changed viewpoints. This remains a development gap, not a cue for scene-specific rules.

These bounded recordings and Dylan's live acceptance establish a usable checkpoint. They do not establish perfect smoothness, general instance recognition, sustained 15fps conversation, zero paging, or final milestone acceptance. Historical D134–D139 designs and rejected filters remain linked from DECISIONS.md and lessons.md, not current implementation guidance.

## UI refresh checks, 2026-10-15

The brief compared the earlier expandable evidence strip with a dedicated evidence row and search map. The shared panel follows Dylan's requested 70/30 split and leaves conversation at full height. The existing models, storage, retrieval policy, consent, and deletion paths remain in place. The additive API fields expose visitor IDs, deletion events, and existing timing milestones.

The design review requires truthful entry counts, tracked DOM checks, current browser checks, and a paired isolated Jetson smoke test. The DOM harness is `tools/ui/test_talk.cjs`. Run `npm --prefix tools/ui ci --ignore-scripts`, then `npm --prefix tools/ui test`. `tools/gate.py checks` also runs it. jsdom is a pinned development dependency. The robot uses no Node runtime.

The task reviews passed. The deterministic checks passed, including Python regressions, the DOM harness, and module assertions (E). Browser checks cover desktop and 390 px phone layouts, loaded thumbnails, keyboard expansion, gallery retention after changing data, and automatic tips (E). Evidence: [browser checks](../bench/results/2026-10-15-ui-browser.json).

The [accepted baseline](../bench/results/2026-10-15-ui-refresh-baseline-1792120775.json) and [candidate](../bench/results/2026-10-15-ui-refresh-candidate-1792121429.json) pass the same isolated naming, recall, thumbnail, queued view-removal, and deletion checks (J). The candidate also verifies separate visitor IDs and exact turn timing fields. Both runs use two typed turns, a repeated development image, and temporary memories. These checks establish interface behavior, rather than held-out answer quality or physical audible latency.

Live attachment on `b78d48ec189e` opens the camera and loads five existing objects with 15 saved views (J). The final local monitor refinements use singular counts and full-width images for objects with one saved view. These presentation changes keep the Jetson runtime unchanged.
