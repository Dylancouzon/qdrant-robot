# Sight: naming what the camera shows (M1.4)

As of 2026-10-08. Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

- Result (D39): 512 image tokens did not beat 256 beyond noise (cluttered probes 7/10 vs 5/10, easy 8/10 vs 9/10, dev 40/47 both) and cost up to 0.49 s on scene-change turns. 256 stays; detector labels are next. The token cap, not the JPEG width, sets the resolution.

- Problem: sight is the largest failure class. Held-out real voices (D38, use 2): four of eight failures name the wrong object or weather (a mug, a banana called a donut, a skateboard, sunny called cloudy). Dev fails similar cases (teddy bears as "stuffed animals", D33; "same as before" questions).
- Today: Qwen3-VL-2B Q4 sees a 672-pixel-wide JPEG capped at 256 image tokens (`robot/brain.py`, `--image-max-tokens 256`). The frame is prefilled when the scene changes, usually before the visitor finishes speaking (D21), so image tokens cost little first-audio latency when the scene is static.
- Detector on `spike/detector`: YOLOE-26n booth vocabulary, 12.8 ms per frame at 15 fps while the LLM decodes, 195 MB (J).

## Alternatives and how each is measured

- (A) More image tokens: 256 to 512 or 768, with a wider JPEG (896 or 1,024 pixels). One flag and one constant. Cost: prefill time on a scene change (about 0.17 s per 256 tokens at 1,492 tok/s, J) and KV memory.
- (B) Detector labels in the sight prompt: "Detected: mug (left), banana (center)" from YOLOE on the frame the turn uses. Gives exact names for vocabulary objects; adds the detector to the M1 runtime (it is needed for M2 anyway, D37). Risk: false labels the 2B repeats as fact; labels outside the vocabulary add nothing.
- (C) A and B together.
- Measure on the Jetson: judged correctness of dev sight steps (synthetic and real voices), then a one-time probe set of unseen COCO images (`eval/probes`, never tuned on); first-audio p50 and p95 on scene-change turns separately from static turns; prefill ms; RAM headroom. Never held-out until a counted run.

## Decision rule

Take the simplest option whose dev sight gain holds on the probes, with first-audio p50 no worse than 0.1 s on all turns.
