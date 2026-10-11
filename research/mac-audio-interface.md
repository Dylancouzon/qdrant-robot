# Robot interface and audio

The robot hears and speaks through its own USB audio device on the Jetson (ALSA `plughw:CARD=Device,DEV=0`, constants in `robot/audio.py`). The Mac page is the monitor and control UI: Start, Stop, Mute, a speaker volume slider, the camera view, and the transcript.

D147's accepted live release is `7f67670fa91e`. It keeps the selected "???" style through confidence dips on the same admitted object. Dylan accepted this checkpoint as good enough. [STATE.md](../STATE.md) owns current releases, processes, and the next action. [DECISIONS.md](../DECISIONS.md) and [lessons.md](lessons.md) retain the development history.

## Start and stop

Run `.venv/bin/python tools/talk.py --release RELEASE_ID`, using the current release from STATE.md. Open `http://127.0.0.1:8765`, select **Start**, and wait for **Listening**. Start attaches to the Jetson unit `qr-robot` (token and release read from its environment), or starts it through `tools/jetson.py run robot`. Deployment alone starts no microphone or models. The monitor waits for a successful authenticated `/state` response before publishing readiness. Failed camera requests clear the image state, so the existing page poll retries automatically.

Say "Hey Edgy" to start a turn. Follow-up questions work for about a minute after an answer finishes. **Stop** stops the `qr-robot` unit and closes the tunnel. Closing the page, Ctrl-C, or losing the tunnel leaves the robot running and listening; Start attaches again. The unit does not start at boot. The local page remains open for another Start.

**Mute** and the **volume** slider act on the robot through the view's token-protected `/mute` and `/volume` endpoints, proxied by the local page. Mute silences the Jetson microphone input. Volume sets the USB `Speaker` mixer (0 to 100 percent), is saved in `shared/speaker-volume`, and is applied at robot startup. The default is 62 percent, also used when the saved level is unreadable or out of range. If saving fails after the mixer changed, the page shows that the level is set but not saved.

The robot does not hear itself. `Robot.hear` replaces every input chunk with silence while the speaker plays and for `SELF_VOICE_TAIL_S` (0.3 s) after the last phrase, for the USB microphone and replays alike. `Mouth` keeps the gate closed while a phrase is queued or its `aplay` runs, because `aplay` exits after the audio drains, then for the tail after the last sink call returns. A failed `aplay` is logged and the gate reopens.

All models and Qdrant Edge run on the Jetson. The Mac stores no recording. The Jetson retains session logs and generated answer WAVs.

Use one camera viewer. A second MJPEG subscriber replaces the first. Each session has a fresh view token, passed through environment and SSH stdin. The local page proxies camera/state access through its session cookie. Stop clears the live feed and transient conversation.

## What the page shows

The camera shows known object names, one orange "???" teaching focus, and admitted grey object outlines. Person detection supplies internal cues; the page draws verified face outlines instead of body boxes. Face identity uses only the current verified result on its exact source pixels. The status and transcript show Listening, Hearing you, Thinking, and Speaking.

The Qdrant Edge strip shows readable sources and saved object thumbnails. Selecting an object opens its Memory card. Details keeps search results and source IDs expandable. The retrieval-preparation timer includes work beyond Edge queries. Answer correctness still needs separate verification.

Focus assignments change at most once per three seconds. The selected admitted object keeps its "???" style while a matched detection continues at the existing LOW threshold. Source admission, visibility, Ignore, and pending preference checks still gate drawing. Actual detection gaps remove outlines. The existing 200ms size grace can expire during undersized observations.

Drawing coordinates use source snapshots and smoothing. Raw detector geometry remains authoritative for selection, crops, actions, and writes. Large raw motion, gaps, merges, and Ignore reset drawing history. A displayed "???" can remain visible while its current crop is ineligible for teaching.

## Teaching, recognition, and item controls

Say "Track this as my wallet" or "This is my phone" while showing one eligible object. Held-object and teaching-zone cues raise priority; another stable eligible object can also be selected. Explicit names preserve the visitor's wording independently of detector categories.

Each named Qdrant Edge point keeps at most three distinct crop vectors. Explicit reteaching merges diverse views only when the current crop matches that exact existing name. Otherwise, the current crop replaces the old gallery. Original/current anchors, aliases, and deletion links remain preserved. Automatic self-training is absent.

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
