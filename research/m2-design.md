# M2 "It remembers": design brief

As of 2026-10-08. Builds on the M1 loop (`research/m1-slice-design.md`, D21 to D29) and the detector spike (`spike/detector`, `research/detector.md` there). Not yet gated.

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
2. **Crop vectors (identity of "my phone" against another phone, and text-to-image).**
   - (A) SigLIP 2 base pooled vector: one model for crop-to-crop and text-to-crop.
   - (B) DINOv2-small for crop-to-crop identity (stronger on instances, U), plus bge on labels and captions for text.
   - (C) Patch multivectors (deferred until a measured miss).
   - Measure: recall@1 for named-object re-identification with a same-class distractor (two phones, two mugs), text-to-crop recall@1, ms per crop, RAM.
3. **Naming, forgetting, ignoring.** "This is my phone": the crops of the track nearest the frame center (or the one the visitor holds) are stored as one named point, several crops as a multivector; later sightings MaxSim-match against named points and the label on the video view becomes the name. "Forget my phone": delete the point and its crops. "Ignore the chair": a named point flagged `ignore`; matching tracks are never stored. Parsing runs in code on the transcript (as `shown` and `about_past` do today), not as LLM tool calls. Alternative: LLM tool calls; measure intent accuracy on dev phrasings and added first-token latency.
4. **Recall query.** (A) For past questions, fuse prefetches with RRF in one Edge query: label or caption text vector, crop vector (text tower if A in 2), and recency (Formula with time decay), with the region as a payload filter for left or right. (B) Recency only (today). Measure evidence-ID accuracy on dev memory fixtures with distractors.
5. **Conversation beyond the window.** Statements already have vectors. Add the robot's answers as text points so "What did we talk about?" searches both sides.

## Memory budget

Detector 195 MB (J). SigLIP 2 base on ORT CUDA about 400 MB (U); DINOv2-small about 100 MB (U). Both options fit in the 1,886 MB headroom above the 1 GB aim if measured.

## Showcase

- "This is my phone" ... later "Where is my phone?": named-object recall with a multivector point (MaxSim) in Qdrant Edge, on the board.
- Labels on the video view come from the detector plus the named-object memory.
- Restart and "forget my phone" on stage: memories persist across a power cycle, and deletion is real (points and crops).
