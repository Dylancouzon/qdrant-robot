# M2 "It remembers": design brief (draft)

As of 2026-10-08. Builds on the M1 loop (`research/m1-slice-design.md`, D21 to D29). Not yet gated.

## Summary

- Goal (STATE.md M2): recall removed objects, left and right observations, and earlier conversation, including after a restart; 90% per capability; Edge query 10 ms p99; M1 speech targets held.
- Today the memory shard holds one point per turn: the frame JPEG, its capture time, a two-part caption ("Main object: ..."), a 64x36 thumbnail, and the visitor's statement with a bge vector. Recall uses the newest captions (recency) and statement search (vector).
- M2 adds what the robot sees when nobody asks: observations stored on scene change, an image vector per observation for visual search ("Have you seen this before?"), and a caption text vector for semantic recall ("When did you see a red mug?", "Where did I leave my keys?").

## Alternatives and how each is measured

1. **What to store when nobody speaks.**
   - (A, proposed) An observation when the scene changes (the same thumbnail test that already drives the warm prefill), at most one per 5 s, captioned in idle time.
   - (B) Object-level memory: a detector (YOLO26n on TensorRT) with tracking; one point per new track with its crop, label, and region.
   - (C) A frame every N seconds.
   - Measure on recorded clips: recall correctness for removed objects and regions, points per hour, GPU time per hour, and first-audio latency during captioning (captions yield to speech).
2. **Image vectors for visual and text-to-image search.**
   - (A, proposed) SigLIP 2 base (patch16, 256) on ORT CUDA: one pooled vector per observation in the existing `image` slot; its text tower embeds questions for text-to-image search.
   - (B) No image vectors: search caption text vectors only (bge).
   - (C) Patch multivectors with MaxSim (deferred by CLAUDE.md until a measured miss).
   - Measure: recall@1 on similar-object fixtures (two mugs, two bags), latency per frame, and RAM.
3. **Semantic recall versus recency.**
   - (A, proposed) For past questions, fuse three Edge prefetches with RRF in one query: caption text vector (bge), image vector (SigLIP text tower), and recency (Formula with exponential time decay), with the region in a payload filter when the question names left or right.
   - (B) Recency only (today).
   - Measure: evidence-ID accuracy on dev memory fixtures, with distractor observations.
4. **Conversation beyond the window.** Statements already have vectors. Add the robot's answers as text points, so "What did we talk about?" can search both sides.

## Memory budget

1,886 MB minimum headroom with every M1 component (D28). SigLIP 2 base on ORT CUDA: about 400 MB (U). A detector on TensorRT: about 150 MB (U). Both fit within the 1 GB minimum if measured.

## Showcase (how is this possible?)

- "Have you seen this before?" with an object held up: an image-vector search over everything seen today, answered with when and where.
- Recency-weighted hybrid recall in one Edge query (RRF over text and image vectors plus time decay) is a Qdrant capability most stacks need three systems for.
- Restart and "forget me" on stage: memories persist across a power cycle, and deletion is real (points and JPEGs).
