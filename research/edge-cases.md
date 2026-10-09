# Edge cases (logged, not fixed, until v1 is tested end to end)

As of 2026-10-09. D71 (Dylan): v1 logs edge cases and tests the whole robot first, in case the architecture changes. Each entry: trigger, risk, candidate fix, and source. D77 also permits revisiting verified limitations with a concrete intervention and paired validation. Foundational retrieval and conversation questions are in research/grounding.md, object perception in research/booth-ux.md, and memory candidates in research/stack.md.

| Case | Risk | Proposed fix | Source |
| --- | --- | --- | --- |
| Two visitors speak within the 20 s no-face window | A told name reaches the second visitor | Answer told names only with a face match at the booth | reviews/20261008-215107-4264-review.md |
| "I'm tired" style lines read as names | A wrong name and a face offer | Listen for introductions only with a new unrecognized face (D70) | D70 |
| A reach toward the background puts it inside the person box | Background object takes the focus for about 3 s | A hand class or a depth camera | D67 |
| Turn frames showing an unidentified visitor | Survive "forget me" until retention | Link turns to the face seen in them | D54 |
| Swap grows at in-process replay restarts; Dylan reports live conversation swap | Paging may limit sustained conversation; live cause unknown | Separate restart churn from live active-turn paging; measure before a context increase | D66, D76; research/stack.md |
| Identical prompts give different answers | Noisy comparisons | Paired runs, the judge cache, more turns | D56 |
| Ignored statements filtered after retrieval | Relevant statements missed when the top hits are all ignored | Filter during retrieval | reviews/20261008-195032-46869-review.md |
| Detector mislabels or misses phones; trials stayed at nano 384x640 | No box means no focus or teaching, even with label-free matching | Compare detector/resolution on labeled real objects; a threshold-only change has orange and false-bottle counterexamples at 0.10 | D43, D64, D77; research/booth-ux.md |
| Two of nine synthetic "Hey Edgy" lines missed ("Eti", "A ag") | The visitor repeats | Real booth voices before more aliases; arm B if needed | reviews/20261008-230525-97862-review.md |
| Background speech within 20 s of an answer becomes a follow-up | The robot answers another speaker | Check on the live day; tie follow-ups to the facing person | same |
| The follow-up clock uses queued WAV length, no speaker | The window boundary differs from playback | Measure with the speaker | same |
| Lines without the wake phrase still trigger a prefill | GPU waste | Skip prefill until woken | V1-B report |
| Focus not frozen at the naming turn's speech start | A wrong bind | Freeze at speech start | V1-B report |
| "Do not forget my phone" or "Should I forget my phone?" matches the forget regex | An unintended deletion | Guard explicit affirmative actions before the forget branch; test negation and questions | D77; robot/things.py command(), robot/main.py _things() |
| Naming fixtures paste objects with no person | No focus forms, naming not tested | Held-object scenes or the live day | V1-B report |
| A missed face on one frame ends a continuing conversation | The visitor loses context | Check face detection on the live day first | reviews/20261008-233058-72473-review.md |
| Past-frame retrieval runs before the visitor check | A new visitor hears shared frame memories | Review after the whole v1 flow | same |
| A face step before every turn with history | About 60 ms before the first token | Gate on scene change or run it during speech | V1-B report |
| Bake-off harness: a running server can answer the health check before the requested model loads | A run labeled with the wrong model | Check the child process and the model identity | reviews/20261008-234551-20256-review.md |
| Bake-off harness: judge failures ignored | A partial verdict file unnoticed | Check the judge's exit code | same |
| Bake-off shape I adds the evidence instruction twice on newer prompts | Misleading shape comparisons | Add it only when absent | reviews/20261009-011200-49661-review.md |
| 64 recent sightings of one kind hide older kinds | A missing memory line | Page farther back if a live visit shows it | same |
| Sightings carry no details (colour, accessories) | "Which teddy had the hat?" fails | Detail from the crop or caption at sighting time | V1-E report |
| TOLD_MIN 0.5 lets unrelated statements through | Odd memory lines ("talk at four" for minutes) | Calibrate on dev with absent memories | V1-E report |
| Commands stored before V1-E come back as told lines in old shards | False ownership in old memory | Retention expires them (12 h) | V1-E report |

## File source decode errors (F0b review, 2026-10-09)

A later video decoding or seeking error raises from FileCamera.latest(). The detector loop can exit without setting detect_failed, so a replay may continue with stopped detection. Carry under D71; before relying on failure propagation in a continuous challenge, set detect_failed on source errors and make the evaluator fail. F0b source qualification completed without a decoding error. Evidence: reviews/20261009-030935-4181-review.md, robot/main.py _detect().

- F0c verification regeneration (D91): `eval/prepare_challenge.py verify` rewrites decoded images and metadata. A changed OpenCV environment could change frozen artifacts while verification succeeds. Current hashes match. Before using a different environment, check every freeze hash; move generation to prepare and make verify read-only if this helper is extended. Review: reviews/20261009-034031-43247-review.md.
