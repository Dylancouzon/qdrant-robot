# M3 "It knows you": design brief

As of 2026-10-08. Labels: J measured on an Orin Nano, E measured elsewhere, U unverified. Gated: GO WITH CHANGES (reviews/20261008-115538-54937-design.md, D41). Changes applied below.

## Summary

- Goal (STATE.md M3): enroll a face only with consent, recognize returning visitors, handle a new visitor replacing the last, forget on request. 90% known-person recognition; zero false identities on held-out strangers.
- Pipeline: a new YOLOE person track (M2.1) triggers YuNet on the upper part of the person box (MIT weights; 2.59 ms on an Orin Nano CPU at 160x120, J from OpenCV Zoo), a similarity warp onto the five-landmark template (skipping alignment cost about seven points in the reference demo, E), then a face embedder. Event-driven: a few frames per new track, and on identity questions, never every frame.
- People in Qdrant Edge: one point per person, enrolled shots as a multivector (MaxSim), name and consent time in the payload. Query with one probe vector per frame. "Forget me" deletes the point and its shots.
- Licensing: not a constraint (D42: internal demo, nothing distributed); details in `research/faces.md`.

## Alternatives and how each is measured

1. **Embedder.**
   - (A) EdgeFace-S: IJB-C TAR@1e-4 95.63, 3.65M parameters, 306M FLOPs (E).
   - (B) insightface w600k_r50 (buffalo_l): 97.12 (E); heavier (R50, U on our board).
   - Fallback if both cost too much: SFace (5.09 ms CUDA FP16 on an Orin Nano, J from OpenCV Zoo). Licenses are not a constraint for this internal demo (D42).
   - Measure on the Jetson: recognition rate at zero false identities on held-out strangers, the margin between the highest impostor and the lowest genuine score, ms per face while the LLM decodes, RAM, detector fps.
2. **Claim score (zero false identities).** Shots per person stay bounded in one Edge point. Compare, at growing gallery size and shots per person:
   - (A) MaxSim over shots (each probe meets N times K shots: the risk grows with K).
   - (B) A pooled person vector (mean of shots) as a second named vector on the same point.
   - (C) Support from at least two distinct shots above the threshold.
   - The threshold comes from our own dev impostor maxima plus a margin, never from the reference demo's 0.35. Below it the robot says it is not sure, or asks. Quality and multi-frame checks only when measured errors justify them.
   - Measure: false identities on look-alike strangers (same sex, age, origin), recognition rate, as the gallery grows. Zero false claims on a finite held-out set is evidence, not a guarantee.
3. **Turn path.** Identity answered in code from the person track ("Do you remember me?", "What's my name?"), like `shown()`, versus giving the brain an identity line. Measure correctness and false claims on dev fixtures.

## Consent, replacement, deletion (privacy boundary)

- Enrollment only after a spoken yes to "May I remember your face?"; the consent time is stored with the point.
- A new person track always identifies again: a name never carries from one track to the next.
- "Forget me" deletes the person point, its shots, any pending write, and every stored frame, crop, and caption from that person's tracks (`robot/memory.py` saves whole frames, which contain faces); verified after restart.
- Without consent, no face vector is stored; frames still stored for object memory keep the faces in them, within the retention bound.
- No automatic greetings, no continuous face embedding, no identity path through the brain: identity questions are answered in code.

## Fixtures (before choosing)

Enrolled people with several shots each, held-out strangers including look-alikes, a new visitor replacing the last, consent refused, forget then return, restart. Development: public face sets (strangers, look-alikes). Held-out recognition: colleagues' photos and video frames in `eval/faces/` (gitignored; consent covers video content, D42).
