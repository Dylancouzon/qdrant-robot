# Recall of objects shown earlier

A visitor shows an unnamed object, the view changes, and the visitor asks "What did I just show you?". The robot keeps each exchange's frame in RAM for the conversation window, captions one frame per view when idle, and answers from the selected frame's caption (D150). Nothing new is written to Qdrant Edge, so D127 holds.

## How it works

- **Retain.** Each exchange keeps the frame it looked at (`Robot.looked`), trimmed with the conversation history. A visitor change, a reset, "forget me", "forget my X", and an item Ignore clear it. One privacy decision (`_store()`) governs both text storage and frame retention.
- **Caption.** The serial worker captions the newest frame of each view when no speech, turn, or job is waiting, with the stored-caption prompt. A question that finds its frame uncaptioned captions it on demand through the same function.
- **Select.** `earlier_view()` picks the frame for a past question about something shown: "first" and "second" count views from the oldest, otherwise the newest view that differs from now. An unchanged view uses the current frame. Time and place qualifiers ("yesterday", "on the left") skip RAM and use stored memories.
- **Answer.** A plain recall is a code answer: "You showed me a clock, 21 seconds ago." A comparison ("Is this the same as before?") sends the present image with one Memories line for the earlier object. A failed caption answers that the robot could not tell.
- **Log.** Each turn records the selected frame, whether its caption was ready or made on demand, and whether the caption reached the answer. `eval/replay.py` credits evidence only on delivery.

## Results (J, 2026-10-10)

Paired Jetson replays, same forget guard in every arm. Development: 47 recorded-voice turns (`eval/dev/sessions.jsonl`) and 15 synthetic recall turns (`eval/dev/recall.jsonl`, frozen before the build).

| Arm | Recorded | Recall | First audio p50 | Outcome |
| --- | --- | --- | --- | --- |
| Baseline | 39/47 | 8/15 | 1.45 s | |
| B: earlier frame sent as a labeled past image | 38/47 | 10/15 | 1.46 s | Rejected: the 2B answers in the present tense or talks about the image |
| B-note: B with a past-tense instruction | 41/47 | 11/15 | 1.47 s | Rejected for B2; answers still drift |
| B2: captions, code answers (current) | 41/47 | 13/15 | 1.41 s | Adopted |

Minimum unused RAM stayed about 1.1 GB in every arm, with flat swap. Held-out (third use, real voices): 17/26 for both baseline and B2.

## Known gaps

- A visitor-change reset also clears the RAM frames, so recall fails when the face leaves the frame between turns.
- The code answer names only the caption's main object ("a donut" for a bag with a banana and a donut).
- Ordinals skip views that match the present; "after that" means the newest view.
- An intent parser was considered first. The eight baseline misses contained no wrong past or present choice, so it was not built (`archive/answer-evidence.md`).
