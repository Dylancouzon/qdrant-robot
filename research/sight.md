# Sight: naming what the camera shows (M1.4)

As of 2026-10-08. Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Paced file video prerequisite (F0b, 2026-10-09)

F0's verified evidence improved the same 2B from 14/24 to 21/24 on development questions (D87). The next challenge needs moving observations inside one continuous robot process. FileCamera now exposes paced constant-rate videos alongside still images. The frozen Jetson input qualification passed; the existing 90 s clip remains development-only. Its earlier benchmark rotates frames by 180 degrees; preserve raw file orientation in FileCamera and verify orientation before semantic replay.

Option A is adopted: the existing latest/show interface uses one lock. Monotonic elapsed time selects the newest due source frame; adjacent reads advance sequentially, and a slow consumer seeks. Recorded fps, stored orientation, final-frame hold, and decoder release at switch/close remain fixed. Invalid finite fps/frame counts and failed reads raise errors. Evidence time is the playback start wall time plus source frame time; repeated reads keep the stamp. The caller owns the source across Robot restarts, and eval/replay.py closes it after all sessions.

J: release d7ed8b31a024 completed the 30 s run with 572/572 independent pixel matches, zero ambiguous indices, and all caller budgets met. The 1,331-frame development clip reports 15 fps. Concurrent detector/watcher/speech readers had latest() p95 of 15.38/14.11/15.07 ms against 66.67 ms; frame-age p95 was 15.56/33.54/15.31 ms against 133.33 ms. With the induced detector pause, the union exposed 444 indices (14.8 fps), skipping six. Caller rates were 14.7, 3.33, and 1 fps. Process RSS peaked at 83.34 MiB. These are file-source measurements with no models; detector throughput and full-stack paging remain unmeasured. Evidence: bench/results/2026-10-09-camera-source-1791529599845132270.jsonl, matching tegrastats, and 2026-10-09-f0b-operations.jsonl.

Option B adds a paced decoder thread that keeps only the latest frame. It handles codec timing without seeking, but adds decoding of frames the robot does not consume and a shutdown lifetime. Reopen it if a new codec or caller schedule misses the frozen budgets. A third option, pre-extracting every frame to JPEG, adds acquisition time and hundreds of MB for the 90 s clip; keep it as a fallback if both native video methods fail.

Acceptance compares still-image behavior, source frame indices and timing, delayed readers, end-of-file hold, switching, concurrent reads, and capture release. Measure 30 s of the existing clip on the Jetson through tools/jetson.py with tegrastats, reporting actual exposed-frame rate, whole latest() p50/p95, returned-frame age, and skipped due frames. Aim for the clip's recorded 15 fps; record misses. This standalone input measurement establishes no detector fps, memory safety with every model active, or perception accuracy. eval/replay.py closes its shared FileCamera after all sessions; Robot does not own the caller's source.

Allowed runtime change is robot/camera.py. Tests and bench/camera_source.py qualify it. Models, prompts, detector policy, and robot/main.py stay unchanged. Budget: under 2 MB new code/results; use shared/clips/live-items-1.avi without new downloads. The measured A result leaves B unimplemented; do not add the thread path speculatively. Design review GO WITH CHANGES: reviews/20261009-025338-83534-design.md. Add concurrent detector (15 Hz), watcher (0.3 s), and speech-start (1 s) callers, with a 0.5 s detector pause at 15 s. Freeze whole latest() p95 including lock wait at one source interval and returned-frame age p95 at two intervals, per caller. Require 100% frame-identity agreement against independent sequential decoding; record source indices, source rate, skipped frames, sample counts, and RSS. This is a small qualification, not acceptance-scale latency. Test B only if A misses these budgets or frame identity.

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
