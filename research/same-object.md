# Same-object answers

"Is this the same thing I showed you before?" is answered in code, never by the 2B brain, which says yes by default (D163, D169). Code: `robot/main.py` `_hold` and `_same_answer`, `robot/memory.py` `same_question` and `same_thing`. Labels: J measured on our Jetson, E elsewhere.

## How it works

1. **The object now.** `_hold` takes the turn's target (`Focus.target`): the most salient object held up (its box at least 80% inside a person box), else the focus. A held object beats a focus that is not held, because a named object cannot hold the "???" focus and the focus moves to scenery (live 2026-10-12: a corner keyboard). It keeps up to `SHOTS` crops from the detected frames that own the boxes.
2. **Earlier objects.** Each answered turn with a held object adds an entry to `self.held` (RAM only; a new conversation and every deletion clear it). The visitor's named objects in the things shard also count, so a comparison still works after a restart.
3. **Which questions.** `same_question` holds for a yes/no opener (is, are, am, do, did, have, can, will, and similar) with "same", "different", or "similar" plus a past cue ("before", "earlier", "showed", "shown", "still", "one", and similar), or with "this", "that", or "it" plus a show or seen cue ("Have you seen this before?"). Negatives in the self-test: "Is this the same color as my shirt?", "Is it different from a cup?", "What did I show you just now?".
4. **The answer**, first rule that applies:
   - No object held: "Hold it up, and I will compare."
   - Nothing earlier: "I don't remember you showing me anything before, so I can't compare." when the question says "same", "different", or "similar"; otherwise the stored sightings answer.
   - Otherwise every earlier entry and named object is scored by MaxSim of DINOv3 crop vectors, and the best decides. Detector labels never decide: an object outside the 50-word vocabulary gets a guessed label (a game controller votes "book").
   - By the best score: at least `same` (0.857) "Yes, it looks like the same one."; within `guess_band` (0.036) below it "It looks similar, but I am not sure it is the same one."; lower "No, this looks different from the one you showed me." Answers name no label.
5. **Evidence.** `turn.compared` records both capture times, both labels, and the score; `turn.memories` cites the earlier turn's text point or the named object's latest turn.

## Calibration

- `same` sits at DINOv2's 0.86 operating point on the viewpoint benchmark, scored in the robot's direction (each crop held now against the earlier crops): no lookalike window reaches it (maximum 0.856), and 119 of 248 same-instance windows do, against 88 for DINOv2 at 0.86 (`bench/embed_arms.py calibrate`, E).
- A color veto (mean CIELAB of the middle half, Delta E 27) kept 99% of same-instance windows and vetoed 38% of lookalike windows (`bench/color_pairs.py`, E). It is parked: DINOv3's shape bias also shows in recognition, so the fix belongs there, after a test in better light.
- `bench/same_pairs.py` on dev stills is a check only: 12 of 12 same-object pairs answer "same".

## Measured (J)

Release `8894dec9ba00`: dev recorded-voice sessions 44/47 keyword with `same-apples-2` passing; recall 17/21 with `rc-compare-2`, `same-laptop-2`, and `same-clock-laptop-2` passing.

## Known limits

In [edge-cases.md](edge-cases.md): same-shape objects in different colors answer "same"; a comparison without a past cue goes to the brain; hands and the booth background raise the score for two objects held at one spot.
