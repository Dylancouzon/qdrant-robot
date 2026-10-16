# Robot interface and audio

The robot hears and speaks through its own USB audio device on the Jetson (ALSA `plughw:CARD=Device,DEV=0`, constants in `robot/audio.py`). The Mac page is the monitor and control UI: Start, Stop, Mute, a speaker volume slider, the camera view, and the transcript.

[STATE.md](../STATE.md) owns the current release and running session. [Booth behavior](booth-ux.md) defines focus and source validation. [Objects](objects.md) defines teaching and recognition.

## Start and stop

Run `.venv/bin/python tools/talk.py --release RELEASE_ID`, using the current release from STATE.md. Open `http://127.0.0.1:8765`, select **Start**, and wait for **Listening**. Start attaches to the Jetson unit `qr-robot` (token and release read from its environment), or starts it through `tools/jetson.py run robot`. Deployment alone starts no microphone or models. The monitor waits for a successful authenticated `/state` response before publishing readiness. Failed camera requests clear the image state, so the existing page poll retries automatically.

Say "Hey Edgy" to start a turn. Follow-up questions work for about a minute after an answer finishes. **Stop** stops the `qr-robot` unit and closes the tunnel. Closing the page, Ctrl-C, or losing the tunnel leaves the robot running and listening; Start attaches again. The unit does not start at boot. The local page remains open for another Start.

**Talking to** shows the selected visitor. **Stop head** cancels head movement and following while the robot keeps running. Servo startup requires the explicit calibration procedure in the [hardware guide](../hardware/SERVO.md). After that unit starts, the monitor attaches through its existing Start flow.

A transcription or answer-worker exception stops the session and preserves its traceback in the Jetson journal. Pending work is discarded before resources close. Start launches another session after the failed unit stops.

The Mac and Jetson can use the existing Wi-Fi network wherever its coverage reaches. All model inference and robot audio remain on the Jetson. The interface uses the Mac launcher and its SSH tunnel. An isolated hotspot needs another uplink for Internet access. Hotspot setup must use a separate control connection.

**Mute** and the **volume** slider act on the robot through the view's token-protected `/mute` and `/volume` endpoints, proxied by the local page. Mute silences the Jetson microphone input. Volume sets the USB `Speaker` mixer (0 to 100 percent), is saved in `shared/speaker-volume`, and is applied at robot startup. The default is 62 percent, also used when the saved level is unreadable or out of range. If saving fails after the mixer changed, the page shows that the level is set but not saved.

The robot does not hear itself. `Robot.hear` replaces every input chunk with silence while the speaker plays and for `SELF_VOICE_TAIL_S` (0.3 s) after the last phrase, for the USB microphone and replays alike. `Mouth` keeps the gate closed while a phrase is queued or its `aplay` runs, because `aplay` exits after the audio drains, then for the tail after the last sink call returns. A failed `aplay` is logged and the gate reopens.

All models and Qdrant Edge run on the Jetson. The Mac stores no recording. The Jetson retains session logs and generated answer WAVs.

Use one camera viewer. A second MJPEG subscriber replaces the first. Each session has a fresh view token, passed through environment and SSH stdin. The local page proxies camera/state access through its session cookie. Stop clears the live feed and transient conversation.

## What the page shows

The camera shows known object names, one orange "???" teaching focus, and admitted grey object outlines. Person detection supplies internal cues; the page draws verified face outlines instead of body boxes. Face identity uses only the current verified result on its exact source pixels. The status and transcript show Listening, Hearing you, Thinking, and Speaking.

A shared panel beneath the camera gives roughly 70% of its width to retrieved text and image cards. The remaining space shows personal memory points in Qdrant Edge and the current turn's timings. Conversation spans the full height beside both panels. Selecting a named object opens its Memory card. Search entries and source IDs stay expandable.

The centered tip says `Say "Hey Edgy, ..."` inside a neutral, dashed pill. It sits in the middle of an empty conversation and stays centered at the top during conversation. Examples rotate every 12 seconds without extra controls. Hover, keyboard focus, hidden tabs, and reduced motion pause rotation.

The map reads stored IDs from `seen` and named object points from `things`. Statements use violet, observations use teal, and recalled sources use pink. Lines connect evidence with its stored named-object ID. Stored IDs determine object positions; evidence positions derive from their IDs and object links. The positions are schematic. The map does not combine embedding spaces. Knowledge facts remain in the retrieved cards.

The authenticated `/memory_map` endpoint reads at most 128 recent turns, 64 recent sightings, 32 current or recalled IDs, and 64 named objects. It selects metadata without vectors or image bytes. Current-turn writes stay visible when their capture time is old. The browser polls once per two seconds while Live is visible, with one request in flight. A sampled count and total remain visible. Point IDs encode storage allocation time; new named objects carry immutable `created` metadata. Legacy objects with no creation time do not get a birth pulse.

A newly stored point gets a short arrival pulse. Recalled IDs pulse once per turn and remain pink while supplied to that turn. Current writes cannot count as recall. Initial snapshots and reconnects do not animate old points as births. Confirmed deletion clears cached map nodes and tooltips, rejects older responses, and reloads stored data. Missing points leave the map. Reduced motion retains the static recall color.

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

## Checks and limits

Run `npm --prefix tools/ui ci --ignore-scripts`, then `npm --prefix tools/ui test` for isolated DOM checks. `tools/gate.py checks` includes this harness. Node and jsdom are development dependencies; the Jetson runtime uses neither.

The [dated check report](archive/interface-checks-2026-10-16.md) retains paired Jetson runs, browser receipts, and measurement limits. These checks establish interface operation. Quality, paging, physical audible latency, and full M4 acceptance remain open in STATE.md.

## UI refresh checks, 2026-10-15

The [archived checks](archive/interface-checks-2026-10-16.md#ui-refresh-checks-2026-10-15) retain the earlier search-flow map and Memory refresh evidence.

## Stored memory map checks, 2026-10-16

The [archived checks](archive/interface-checks-2026-10-16.md#stored-memory-map-checks-2026-10-16) retain creation, recall, deletion, bounded polling, and browser evidence.
