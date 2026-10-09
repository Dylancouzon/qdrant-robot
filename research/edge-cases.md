# Edge cases (logged, not fixed, until v1 is tested end to end)

As of 2026-10-08. D71 (Dylan): v1 logs edge cases and tests the whole robot first, in case the architecture changes. Each entry: the trigger, the risk, a proposed fix, the source. Promote an entry to a task only when the integrated visit or a live test day shows it.

| Case | Risk | Proposed fix | Source |
| --- | --- | --- | --- |
| Two visitors speak within the 20 s no-face window | A told name reaches the second visitor | Answer told names only with a face match at the booth | reviews/20261008-215107-4264-review.md |
| "I'm tired" style lines read as names | A wrong name and a face offer | Listen for introductions only with a new unrecognized face (D70) | D70 |
| A reach toward the background puts it inside the person box | Background object takes the focus for about 3 s | A hand class or a depth camera | D67 |
| Turn frames showing an unidentified visitor | Survive "forget me" until retention | Link turns to the face seen in them | D54 |
| Swap grows at in-process replay restarts | Swap during long runs | Measure in a real process restart and the eight-hour run | D56, D66 |
| Identical prompts give different answers | Noisy comparisons | Paired runs, the judge cache, more turns | D56 |
| Ignored statements filtered after retrieval | Relevant statements missed when the top hits are all ignored | Filter during retrieval | reviews/20261008-195032-46869-review.md |
| Detector mislabels or misses phones | Named phones not recognized | Label-free matching (done); detector vocabulary later | D64 |
