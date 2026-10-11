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

## M2.2b: name, forget, and ignore objects (2026-10-08)

Design gate GO WITH CHANGES (reviews/20261008-174532-2635-design.md); its changes are applied below.

**Bake-off result** (`bench/reid.py`, `bench/results/2026-10-08-reid-1791502259.jsonl`, CPU FP32 on the Mac; the scores do not depend on the machine). Views: 24 COCO phones and 24 COCO teddy bears pasted into other rooms, sides, sizes, and light (the change the fixtures show), and 8 Objectron cup and 8 camera videos (a real viewpoint change). Every crop is our detector's box. Each instance enrolls 3 crops and scores MaxSim against every other instance of any class, because the robot matches across detector labels. The threshold is the top other-instance score on the even instances, then tested on the odd ones.

| Arm | Threshold | Phones | Teddy bears | Cups | Cameras | False matches (same class, other class) |
| --- | --- | --- | --- | --- | --- | --- |
| HSV histogram (no model) | 0.964 | 7/22 | 5/35 | 0/12 | 2/6 | 0/625, 0/1,400 |
| SigLIP 2 base, pooled | 0.947 | 5/22 | 6/35 | 0/12 | 3/6 | 0/625, 0/1,400 |
| DINOv2-small, CLS | 0.831 | 12/22 | 8/35 | 5/12 | 2/6 | 0/625, 0/1,400 |
| **DINOv2-small, CLS and mean patch** | 0.822 | 15/22 | 15/35 | 5/12 | 2/6 | 0/625, 0/1,400 |

- The HSV floor fails: look-alike bears and black phones need a threshold that rejects most true matches. DINOv2-small ships; SigLIP 2 base is rejected (fewer true matches, about four times the compute).
- With two named objects of one kind, the right one scores higher in 621 of 625 pairs. Most misses are safe: the robot says it does not know or does not see it.
- Jetson cost (J, `bench/crop_cost.py`, `bench/results/2026-10-08-crop-cost-*.jsonl`): onnxruntime CUDA, FP32, 15.3 ms p50 and 17.2 ms p99 per crop, 262 MB RSS added to a process that already holds CUDA. Back-to-back crops cut llama-server decode from 34.8 to 18.4 tok/s. The robot embeds on its worker thread, which runs turns too, so a crop never overlaps a turn's decode. An FP16 model or a TensorRT engine would cut the RAM; neither is needed yet.

**Built (code, no LLM tool calls).**

- Store: `robot/things.py`, its own Edge shard `things` (as `robot/people.py`), so the memory shard's schema is unchanged. One point per name with a `crops` multivector (MaxSim) and payload `name`, `labels`, and `turns`. Ignore rules are vectorless points with payload `ignore: <label>`. Retention never touches this shard.
- Track and crop stay bound: `Sighting` carries its box, the sight job carries the frame it came from, and the robot keeps the last view (frame plus `Tracker.view()`) and three views 0.33 s apart.
- Naming ("this is my X", "this X is mine", "remember this X as my X") is an action, in code. It binds only the one candidate in view: the one confirmed track of X's kind, else the one object in view, whose own label joins the named labels (the detector calls the dev gold phone a bag). Otherwise the robot asks for it alone (no sides: the robot cannot turn). The crops come from the recent views of that track. The turn first waits, at most 0.5 s, for tracks confirmed after its speech start.
- Matching runs across detector labels (labels are hints, D61): once any object is named, every new non-person track is embedded, and at MATCH (0.822) or above its sighting is tagged `named`. The bound track is tagged even when its sighting is still queued.
- Questions about the object go to retrieval (Dylan, 2026-10-08: questions feed the brain, actions stay in code). `Robot.named_evidence` returns evidence lines (its caption from the naming turn, when it was named, each object in view with its score, the latest matched sightings), the matching track (None below MATCH), and the evidence ids. Until the lead routes these lines to the brain, `_mine` gives a minimal code answer from them: "Yes, your phone is here now", "I see a phone, but I am not sure it is yours", "I last saw your phone 20 seconds ago", and "Is this my phone?" scores the object nearest the center.
- "Forget my X" deletes the named point, the turns that named it (frame and statement), the tag on its sightings, and any pending tag for a queued sighting; the forget turn itself is not stored. "Ignore the chair" stores a rule: new tracks of that label are not stored, sighting recall skips the label, stored turn captions lose the clauses that name it, statements about it are not recalled, and "did you notice any chairs?" says it is ignoring them. "Stop ignoring chairs" deletes the rule. Both survive a restart.
- Checks: `robot/test_things.py` (naming, "which one?", same-kind distractor, restart, forget, ignore), `python -m robot.things`.

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
