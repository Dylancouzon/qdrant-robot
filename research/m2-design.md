# M2 "It remembers": design brief

As of 2026-10-08. Builds on the M1 loop (`research/m1-slice-design.md`, D21 to D29) and the detector spike (`spike/detector`, `research/detector.md` there). Gated: GO WITH CHANGES (reviews/20261008-100431-34165-design.md, D37). Changes applied below.

## Summary

- Goal (STATE.md M2): recall removed objects, left and right observations, and earlier conversation, including after a restart. Dylan (2026-10-08): name an object by voice ("this is my phone") and recall it by name, labels on the video view, "forget my phone" deletes it, "ignore the chair" stops remembering it. 90% per capability; Edge query 10 ms p99; M1 speech targets held.
- Today the memory shard holds one point per turn: the frame JPEG, capture time, a caption, a 64x36 thumbnail, and the visitor's statement with a bge vector. Recall uses the newest captions (recency) and statement search.
- Proposed: a detector and tracker (YOLOE-26n booth vocabulary on TensorRT, measured) feeds an object memory: one point per track, with its crop vector, label, region, and first and last seen times. Named objects are points with several crop vectors as a multivector (MaxSim).

## Measured inputs (J, MAXN_SUPER, `research/detector.md` on `spike/detector`)

- YOLOE-26n booth vocabulary, TensorRT FP16, 384x640: 6.74 ms p50 alone; 12.8 ms at 15 fps while llama-server decodes; decode drops 34.6 to 31.7 tok/s (target 30). Raw TensorRT backend: 195 MB RAM. Tracker 0.6 to 0.8 ms p50 on the CPU.
- Peak 66.3 °C, RAM peak 3,233 MB with detector and LLM, no swap growth. M1 headroom with every M1 component: 1,886 MB (D28).
- Live camera in MAXN_SUPER: not yet run (OpenCV failed to open the camera after the reboot; `robot/camera.py` on `main` captures at 16 fps).

## Alternatives and how each is measured

1. **What to store when nobody speaks.**
   - (A, proposed) Object memory from the detector: a point per new track, updated when the track moves region or leaves; the crop is embedded once per track (and on explicit "remember this"). Scene-change frames stay as today's turn frames.
   - (B) Scene-change frames only, captioned in idle time (no detector).
   - Measure on recorded clips and fixture sequences: removed-object and left/right recall correctness, points per hour, GPU ms per hour, first-audio latency while the detector runs.
2. **Crop vectors (identity of "my phone" against another phone).** Label filtering cannot tell two phones apart (dev `m2-naming-phone-3`, `-4`), so M2.2b needs a crop embedder. Bake-off and design: the M2.2b section below.
3. **Naming, forgetting, ignoring.** "This is my phone": the crops of the track nearest the frame center (or the one the visitor holds) are stored as one named point, several crops as a multivector; later sightings MaxSim-match against named points and the label on the video view becomes the name. "Forget my phone": delete the point and its crops. "Ignore the chair": a persistent class rule (separate from named instances), so matching tracks are never stored; both kinds of rule survive restart. A name binds to a confirmed track, or the robot asks which one. Parsing runs in code on the transcript (as `shown` and `about_past` do today), not as LLM tool calls. Alternative: LLM tool calls; measure intent accuracy on dev phrasings and added first-token latency.
4. **Recall query.** Label, region, and time resolved in code with payload filters; recency ranks within the asked time window (D37). RRF over vectors only after filtering misses on distractor fixtures.
5. **Conversation beyond the window.** Statements already have vectors. Add the robot's answers as text points so "What did we talk about?" searches both sides.

## M2.2b: name, forget, and ignore objects (brief for the design gate, 2026-10-08)

**Embedder bake-off.** One embedder ships; the loser goes to `DECISIONS.md`.

- (A) SigLIP 2 base (`google/siglip2-base-patch16-224`), pooled image vector, 768-d. It fills the existing `image` slot size and could later serve text-to-crop search. About 86 M vision parameters (U); ViT-B/16 224 on TensorRT FP16 took 19.9 ms (J, `research/models.md`).
- (B) DINOv2-small (`facebook/dinov2-small`), CLS vector, 384-d, Apache-2.0. About 21 M parameters (U), so about four times less compute (U). Self-supervised features usually separate instances better than CLIP-family features (E, ILIAS and PeKit at large sizes, `research/models.md`); small sizes are unmeasured.
- Floor (no model): an HSV color histogram of the crop, 10 lines. If it meets the bar, no model ships.
- Label only fails by construction: every same-class distractor is a false match.

**How it is measured (Jetson, `bench/reid.py`, time box 90 minutes).** The dev composites paste one identical cutout at several scales, so they cannot measure re-identification. Use real multi-view footage instead: Objectron videos (cup, laptop, bottle, camera, book; C-UDA license; 15 MB per video, URLs checked), 10 instances per class.

- Crops come from our own detector box (`robot/detect.py`), as at runtime: 12 frames per video.
- Enroll each instance from 3 consecutive crops at the start (a held object turning a little). Positives: crops from the second half of the same video (other viewpoints). Negatives: every query crop of the other 9 instances of that class.
- Score: MaxSim, the best cosine over the enrolled crops, as Edge computes it.
- Split instances 5 and 5 per class. Set the threshold on the first half at the highest negative score (zero false matches). On the second half, report: true matches at that threshold, false matches, and rank-1 accuracy with two named instances of one class.
- Cost: TensorRT FP16 engine per arm (trtexec, reused `detect._TensorRT` runner), ms per crop p50 and p99 alone and while llama-server decodes, RSS and GPU memory added, decode tok/s change.
- Rule: zero false matches on the second half is required; then the most true matches wins; within 5 points, the cheaper arm wins. Results go to `bench/results/`. Crops stay in `shared/`, not in git.

**Design after the gate (code, no LLM tool calls).**

- Store: named points live in the memory shard, with a `crops` multivector (MaxSim, created with `UpdateOperation.create_dense_vector`, verified in the 0.8.0 stubs) and payload `name`, `label`. The unused `image` slot is deleted (`delete_vector_name`). Ignore rules are vectorless points with payload `ignore: <label>`. Neither has `ts` or `last_seen`, so retention never evicts them (D51).
- Naming ("this is my X", "remember this X as my X"): candidates are confirmed tracks in view whose label matches X (any non-person track when X is outside the vocabulary). One candidate binds. Two or more: the robot asks "the one on my left or on my right?", and the next turn answers with a side. Crops: the detector thread keeps the last four crops per in-view track, at least 0.5 s apart.
- Matching: a new track is embedded only when a named point of its kind exists (so normal booth traffic costs nothing). A match above the threshold tags the track's sighting `named: <id>`.
- Recall: "where is my X", "have you seen my X", "is this my X" are answered from tracks in view and tagged sightings. Anything else says it does not know or has not seen it. A same-class track below the threshold is never called the visitor's.
- "Forget my X": delete the named point and clear `named` from its sightings. "Ignore the chair": add a rule; `_sight` skips sightings of that label, and an answer about chairs says it is ignoring them. "Stop ignoring chairs" deletes the rule. Both survive restart because they live in Edge.
- Acceptance (frozen): `eval/dev/m2.jsonl` naming, forget, and ignore cases; a fresh one-time probe set in `eval/probes/m2d.jsonl` written before the code; no regression on other dev M2 cases; Jetson ms and RAM per new-track crop embedding.

## Memory budget

Detector 195 MB (J). SigLIP 2 base on ORT CUDA about 400 MB (U); DINOv2-small about 100 MB (U). Both options fit in the 1,886 MB headroom above the 1 GB aim if measured.

## Showcase

- "This is my phone" ... later "Where is my phone?": named-object recall with a multivector point (MaxSim) in Qdrant Edge, on the board.
- Labels on the video view come from the detector plus the named-object memory.
- Restart and "forget my phone" on stage: memories persist across a power cycle, and deletion is real (points and crops).

## M2.3a: labels on a video view

Goal (Dylan, STATE M2): a booth screen shows the robot's camera view with labels on tracked objects (and names of recognized, consenting visitors only while their face matches now). Alternatives, measured on the Jetson by added CPU and GPU time per frame, detection fps and decode with the view open, and end-to-end view lag:
- (A) MJPEG over HTTP from the robot process (stdlib `http.server` in a thread): draw the newest frame's track boxes and labels with OpenCV, encode JPEG at a capped rate (for example 10 fps, 960 px), serve `multipart/x-mixed-replace` to any browser on the booth LAN or a local screen. One new module `robot/view.py` reading the camera's newest frame and a snapshot of tracks.
- (B) A separate viewer process reading frames and track state from shared memory: isolates the robot process but adds IPC.
- (C) WebRTC: lower lag, far more code and dependencies.
The view never stores frames (no privacy impact on memory) and only draws names that the identity path already says aloud.
