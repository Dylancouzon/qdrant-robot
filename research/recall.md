# Recall of objects shown earlier

The visitor shows an unnamed object, the scene changes, and the visitor asks "What did I just show you?". The robot keeps each exchange's frame in RAM for the conversation window, captions one frame per view when idle, and answers from the selected frame's caption (D150). Paired Jetson runs: recorded 39 to 41/47, recall sessions 8 to 13/15, first audio 1.45 to 1.41 s p50 (J). The sections below record how the design got there.

## Evidence

The current brain's recorded development run (`bench/results/2026-10-10-gemma-full-stack.json`, arm `qwen-cuda`, 39/47 judged, J) has eight failures. `about_past()` fired on every past question, so no miss shows a wrong past or present choice. That does not prove routing is complete: combined questions still get no earlier evidence. An intent parser alone would not have fixed any of the eight.

| Cause | Items |
| --- | --- |
| No evidence for an earlier unnamed object | recall-stop-2, recall-moto-2, same-apples-2 (and hand-teddy-2, which also has an ASR error) |
| Model answer with adequate evidence | hand-teddy-3, same-apples-1, joke-1, intro-2 |

Two rules combine to leave the brain empty-handed:

- D127 writes no frames or captions for ordinary turns. `Memory.recent()` returns only captioned frames, so it returns nothing for an unnamed stop sign.
- After a scene change, `Robot._look()` keeps only the visitor's lines in history (D27). The robot's own earlier answer ("That is a stop sign") is dropped.

## Alternatives

Each option is kept in RAM for the conversation window only. Nothing new is written to Qdrant Edge, so D127 holds.

| Option | What reaches the brain on a past question | Main risk |
| --- | --- | --- |
| A. Earlier sight answers | The robot's earlier answers about what it saw, each with its age, after a scene change, only when `about_past()` fires | Generated text used as evidence; may pull the 2B to the old scene (D27) |
| B. Earlier frame | The frame from the earlier sight turn in place of the current one, for questions about something shown before | Combined questions ("Is this the same as...") need both images, which D25 found blends scenes; second image costs prefill time |
| C. Persist captions for every shown frame | Stored captions through `Memory.recent()` | Reverses D127; needs Dylan |

## Decision: option B

The design gate (2026-10-10, GO WITH CHANGES) rejected A, because the robot's earlier answers are generated text, not observed evidence. B uses the pixels the robot saw.

- **Retain.** Each exchange keeps the frame it looked at and its capture time, in RAM, in the same window as the conversation history. Anything that clears or trims the history clears or trims these frames: the visitor change, a reset, and "forget me".
- **Select.** A past question about something shown gets one retained frame that differs from the current view. "First", "second", and "last" pick by order; otherwise the newest differing frame is used. When earlier exchanges saw the same view as now, the current image answers. With no earlier exchange, nothing is selected and the robot says it does not know.
- **Label.** The selected frame replaces the current image, and the prompt states its age and that it is not the present. `brain.SYSTEM` says an unlabeled image is the present.
- **Log.** Each turn logs the selected frame's capture time, so `eval/replay.py` can score frame selection apart from the answer.
- **Known gap.** A combined question ("Is this the same as what I showed you before?") needs both images. It keeps today's behavior, and `rc-compare` measures it.

C (persisting captions for every shown frame) stays out of scope unless B fails.

## Result of option B (2026-10-10, J)

Paired replay, the same forget guard in both arms. Baseline release `cb7120f77e81`, candidate `53867a9`.

| Set | Baseline | Candidate |
| --- | --- | --- |
| Recorded development, 47 turns | 39/47 judged, first audio 1.45 s p50 | 38/47, 1.46 s |
| Recall sessions, 15 turns, synthetic voice | 8/15 | 10/15, 1.65 s |

The right frame reached the brain on every recall turn except the combined question. The 2B mishandles a labeled past image: it answers in the present tense ("You're showing me a stop sign") or talks about the image. `fruit-then-bus-3/4` regressed. The baseline passed them only from the visitor's own line in history. B is not adopted as built.

## Next: option B2, captions of retained frames

First design gate on B2: RETHINK (`reviews/20261010-212839-10410-design.md`), for a missing comparison plan and selection details. This section resolves those findings.

- **Select, then caption.** `earlier_view()` picks the retained Look, as in B. That Look's caption formats the answer in code: "You showed me <main object>, <age>." `shown()` no longer chooses among RAM Looks.
- **One caption path.** The existing worker captions each new retained view when idle (one caption per view run, not per duplicate frame). If the selected Look has no caption at question time, the turn captions it on demand through the same function. There is no image fallback, and a Look never borrows another Look's caption.
- **Combined questions.** The selected caption's main object and age go in as one "Memories" line beside the present image.
- **Boundaries.** Captions live on the Look, so visitor change, reset, deletion, and the shared privacy predicate clear them with the frame.
- **Log.** Each turn logs the selected Look, whether its caption was ready or made on demand, the caption time, and whether the answer came from code or generation.

### Comparison

One paired Jetson run per arm on identical inputs: the 47 recorded development turns and the 15 recall turns.

| Arm | What changes from the baseline |
| --- | --- |
| Baseline | Forget guard only (`e688d90`, already measured: 39/47, 8/15) |
| B-note | B with one revised EARLIER note: past tense, name the object, no talk about the image |
| B2 | Captions as above, B's image path removed |

Report judged answers, evidence selection, caption readiness and correctness, first-WAV p50 and p95, detection fps, and tegrastats headroom and swap separately. Adopt the arm with a judged gain and no capability loss. A one-line follow-up asked right after an answer measures the on-demand path.

## Result of option B2 (2026-10-10, J)

| Arm | Recorded, 47 turns | Recall sessions, 15 turns | First audio p50 |
| --- | --- | --- | --- |
| Baseline (`e688d90`) | 39 | 8 | 1.45 s |
| B (`53867a9`) | 38 | 10 | 1.46 s |
| B-note (`ac7395d`) | 41 | 11 | 1.47 s |
| B2 (`1740f0b`) | 41 | 13 | 1.41 s |

B2 fixed all three baseline recall misses. Its code answers take about 1.15 s to first audio. `bus-red-2` failed in B-note and B2 through the same untouched sight path, with the same ASR text ("root number"); it is decode noise. `rc-compare-1` (the 2B calls a Pepsi cup "my workspace") remains a sight miss. Tegrastats shows the same minimum unused RAM in every recorded arm (baseline 1,138 MB, B2 1,102 MB) and flat swap (B2 67 to 71 MB), so the RAM frames and captions cost no measurable memory in replay. This is not the full-stack stress run behind the 558 MiB headroom figure. B2 is adopted.
