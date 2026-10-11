# Recall of objects shown earlier

The visitor shows an unnamed object, the scene changes, and the visitor asks "What did I just show you?". Today the brain gets no evidence for that question. This file holds the design for closing that gap.

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
