# Mac audio interface

D136 source is frozen on the protected `spike/mac-audio-interface` branch. Sol46346 passes tree `1d77da417dd52f59657dc283cfb00479e7b2453a` in151.57s/native0(E). Jetson candidate `623954f5cdb8` passes common recorded bottle learning, continuous labeling, persistent item ignore, reset, restore, and other-item descriptor checks. Independent actual browser review passes moving feed, source-bound face names, no copied card, and no tiny boxes. Normal live settings are restored Idle with microphone off. STATE.md owns live process and handoff status.

## Current behavior

One serial recognition owner handles faces and crop embeddings independently of conversation and detection. Background recognition admits at most three object crops per second, oldest due first; priority conversation batches keep the existing behavior. Bounded queues, source timestamps, gallery epochs, and detection-gap epochs reject stale work. Reset pauses admission before draining and closing owners.

The view shows all visible unambiguous named objects and one eligible unknown teaching focus. Drawing coordinates smooth stationary size changes; raw geometry governs selection, crops, and writes. Short detector dropouts retain drawing for200ms. A skipped query preserves the last accepted object association. An actual descriptor miss immediately removes confirmed display; three misses clear the chosen-name verification preference. Gaps, merges, forget, and ignore invalidate associations.

`OBJECT_MIN_SIDE=120` is the shortest side at1280sourcewidth, scaled to frame width. The user's green-capped foreground bottle measures126-127px(J). Detector low/high confidence0.10/0.25 and display admission0.25 are configurable in robot/config.py. Confirmed names continue and reverify at the existing0.10 tracker threshold; unknown teaching admission stays0.25. Teaching-zone and held-object cues raise priority without excluding other stable eligible objects. No scene coordinates or model threshold exceptions are added.

YuNet receives640-width input and maps face geometry/landmarks to original pixels before112x112 alignment. A person's name appears only on the exact verified source frame and source face box. Current body outlines remain anonymous. Positive publication uses original source time and current source-person continuity. The copied face card is removed. Existing two-shot support, face thresholds, consent, and deletion remain fixed.

"Do not track that" stores descriptors for the selected item in the existing Things shard. Preference points stay outside ordinary object queries, labels, and recall. Returning objects must pass preference verification before current-sight answers or persistence. One crop embedding serves recognition and exclusion. The UI lists current eligible targets and persistent ignored items, with a reachable Restore control. Category-ignore voice commands remain separate. Session/gallery/source/track checks, local authentication, Host/Origin checks, and bounded action queues protect controls.

Only named or explicitly tracked objects keep visual evidence in Qdrant Edge. Unknown detections stay in temporary context. Conversation memory stores text; consented people and ignore preferences remain persistent. Ordinary turn images do not create ambient visual history. Explicitly chosen names preserve visitor wording separately from detector categories. Existing legacy named links remain recallable; no historical purge or alias migration occurs.

The Mac client streams microphone audio to Jetson models and plays returned answer audio. Conversation text follows streamed replies and scrolls after layout. The transcript card shrinks and scrolls within the viewport. Startup stays Idle with microphone off. Stop releases the owned robot session. Use the original browser tab only: a second MJPEG viewer replaces the first and freezes its image.

## Bounded development evidence

The user authorized scoped checks and recorded/live review, and prohibited the full suite. Fifty initial checks14.32s, four restart checks3.13s,25 pending-ignore continuity checks4.39s, and27 final confidence checks5.39s all pass/native0(E). Changed-path lint, syntax, inline JavaScript syntax, and whitespace pass. Astra70897 counsel and Sol78941 schema gate return GO WITH CHANGES. Sol20183 finds a pending-ignore continuity blocker; the builder fixes it. Sol30274 passes the intermediate source. Actual recorded confidence dips then require the final correction and Sol46346 PASS.

The real Robot adapter uses FileCamera, ordinary teaching, the existing renderer, actual item controls, and temporary memories on the Jetson. Corrected candidate keeps the desired bottle name85/85 samples, compared with47/87(54%) on the prior renderer baseline(J). Ignore return44samples and reset52samples hide the item throughout. A distinct physical bottle remains outside its item-ignore descriptors. Restore persists after closing/reopening; its warm display tail passes90%. Both variants render then wait100ms, about9Hz rather than exact10Hz MJPEG pacing.

Corrected named-background detection averages14.79fps and JPEG rendering14.02ms median(J); baseline15.01fps/14.14ms. These bounded values do not establish sustained15fps while talking. One generated joke uses different history/output across variants, so its0.708s versus2.387s first-synth values are not a paired LLM latency conclusion. System swap stays104MB across84 candidate samples; stable occupancy does not establish zero active paging. Peak RAM6283/7485MB and temperature57.843C remain sampled diagnostics.

Keep both failed adapter receipts. The first candidate achieves81% names and74% raw restored samples because confidence dips0.2379/0.2056 erase a confirmed name. The final correction uses the existing continuation threshold. An extra two-name assertion assumes uncontrolled teaching binds distinct objects; independent review rejects that inference. Its final36samples show the latest known name and exactly one unknown together. A one-target diagnostic binds an overlapping chair crop and later loses its label; the exact cause remains unqualified. This fixture limits multiple-object qualification; it does not justify scene-specific product changes. The adapter's named-toy face metric is invalid outside person phases.

Private recordings are upright1280x720/15fps: background20s/300frames and person30s/450frames, without audio. Store only in ignored build/p2/recordings and Jetson shared/sessions. FileCamera starts playback after model warmup. Recorded-camera CLI uses paced zeros and keeps the microphone muted. The existing clip_sightings rotates upright files again; use FileCamera directly. Replay production-memory changes must be retained separately and the closed original backup restored before live handoff.

The60-frame background detector probe finds no microphone candidate; display changes cannot repair missing detection. Isolated19-frame face profiling gives1280-width median86.34ms/14matches and640-width33.53ms/15matches(J). Recorded-person matches do not establish stranger safety or integrated face-name continuity. The browser reviewer observes source-bound names on front-facing and partially turned frames, and anonymous outlines after turning away. Snapshot observations leave continuous jitter and leave/reenter timing unqualified.

## Carried limits and next work

Older object aliases can win after a long gap/restart; viewpoint diversity and detector coverage remain open. Reset callers currently serialize admission. An uninterrupted replacement can make Ignore use the previous accepted descriptors; verify a selected current crop if that behavior is observed. These limits are recorded in research/edge-cases.md. Do not add speculative machinery for them.

Dylan will start a separate session for WSL checkpoint export, TensorRT engines, and Jetson qualification after the current AWQ preparation ends. This session records its terminal native outcome and artifact inventory only. All final product targets and M4 remain unproven.

## Evidence

See D124-D137 in DECISIONS.md; bench/results/2026-10-09-liveview-repair.json; reviews/20261009-231341-46346-review.md; research/lessons.md. Prior preview receipts preserve D127-D135 implementations and their superseded physical results. Raw recordings, private memory, transcripts, and numerical locals stay outside Git.
