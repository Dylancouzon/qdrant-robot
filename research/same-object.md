# Same-object answers

Status: built on the Mac, 2026-10-12 (`robot/main.py` `_hold` and `_same_answer`, `robot/memory.py` `same_question`); the Jetson replay of `eval/dev/sessions.jsonl` is pending. Changes to the design: the "this/that/it" branch of `same_question` ignores "just", "first", and "last" (so "Did you just say that?" is no comparison), the answer cites the earlier turn's stored text point as evidence, the comparison scores every earlier object of the same kind or track and the best decides (with none, a question saying "same", "different", or "similar" gets the kind answer naming the newest earlier object, and any other goes to the stored sightings), and its threshold is the separate setting `same` (0.86, Advanced settings).

## Problem

"Is this the same thing I showed you before?" goes to the 2B brain with the present image and a Memories line. The 2B says yes by default. Dev `same-apples-2` fails this way: it calls teddy bears "the same thing" as the apples it saw earlier, and held-out shows the same yes-bias. A booth visitor will try this. A wrong "yes" makes the robot look dumb, and a right answer shows vector search at work.

## Proposal: answer comparisons in code, from what the robot tracked

1. **Held objects per turn.** At each answered turn, the robot resolves the visitor's object with `_target(turn)`. When that track is an object (not `BODY`), it keeps up to `SHOTS` crops of it in RAM. The crops come from the detected frames that own the boxes (`[(view_taken, *view), *reversed(views)]`, as `_bind` does), never from a camera frame cut with a later box. Each entry keeps the track id, the voted label, the crop capture times, and the turn time. A small deque holds the entries for one conversation. A new conversation and every deletion clear it, like `looked`. Nothing reaches disk, and no vector is computed until a comparison asks.
2. **Which questions.** `same_question(text)` in `robot/memory.py` holds for a yes/no question (an `is/are/was/does/did/have` opener) with a past cue ("before", "earlier", "showed", "again", "first", "last", "just") and either "same", "different", or "similar", or "this/that/it" ("Have you seen this before?"). "Like" counts only in "like the one before". Plain recall ("What did I show you just now?") and present questions keep their paths. The self-test includes these negatives: "Does this look like a phone?", "Is this the same color as my shirt?", "Is it different from a cup?", and "What did I show you just now?".
3. **The answer, first rule that applies:**
   - No object target now: "Hold it up, and I will compare." (code)
   - No earlier entry from another turn: the brain answers, as today.
   - Different label groups, between two different track ids (`KINDS` in `memory.py`): "No. Earlier you showed me {article(earlier)}; this is {article(now)}."
   - Same label group, or the same track id (a swap in hand can keep one id and its voted label): MaxSim of up to three crops on each side with the DINOv2 descriptor that named objects use. A score at or above `settings.same` (0.86) gives "Yes, it looks like the same {label}." A score inside `settings.guess_band` below it gives "It looks similar, but I am not sure it is the same {label}." A lower score gives "No, this looks different from the {label} you showed me." {label} names the earlier object, because a swap in hand keeps the old track and its voted label (seen in the Jetson replay).
4. **Evidence.** The turn records both entries' capture times, the labels, and the score, and the answer names the object it compared. The answer is code-owned, so `turn.verbatim` is true and the brain is not called.

## Alternatives

- (B) Send both crops to the brain as two images. This costs about 256 more image tokens and up to 0.49 s more prefill (D39, J). The yes-bias is in the 2B's answer, so B likely keeps it.
- (D) Labels only: answer from the detector labels and skip DINOv2. It is cheaper and survives hand occlusion. It cannot tell two different mugs apart, and it answers "same" for every same-class pair. The proposal uses D as its first layer.

## Measurement

- Dev pairs on the Mac, at least five per category: same object at two views, two different objects of one class (including a swap in hand at one spot), two different classes, and real camera crops from `eval/dev/live` where they exist. Report both error directions: false "same" and false "different". The same-label score policy (`same`, `guess_band`) is set from these pairs, and both stay UI settings.
- The question gate gets dev cases with comparison phrasings that lack a show word ("Is this the same laptop as before?", "Have you seen this before?") and non-comparisons ("What did I show you just now?").
- Replays: dev fixtures give the focus 1.0 s (`STEADY_S`) to settle, so each comparison step has a real `wait` after `show`, as a visitor holds an object up. The builder confirms that replay turns get a target before claiming a fix.
- Held-out fixtures stay frozen; when held-out is next used, report comparison turns that got no target as a separate count.
- Integrated: one Jetson replay of `eval/dev/sessions.jsonl`, paired with the current release. The result must keep 42/47 or better and fix `same-apples-2` with no new miss.

## Measured (E, Mac CPU)

`bench/same_pairs.py` runs the robot's detector and DINOv2 on `eval/dev` stills, one crop per side, at the `same` setting 0.86 and `guess_band` 0.05 (`bench/results/2026-10-12-same-pairs-1791830164.json`). `same` is separate from `match`: the first run used `match` 0.822 (`...-1791829112.json`) and gave one false "same", the black and silver laptop at 0.835. All numbers are in-sample: 0.86 was set on these same 27 pairs, so a held-out pair set must confirm them. At `same` 0.86: same object, 12 pairs: 11 "same", 0 "not sure", 1 false "different" (brown bear, 0.800, 0.01 below the band). Two objects of one class, 8 pairs: 0 false "same", 1 "not sure" (the laptops, 0.835), 7 "different" (0.19 to 0.78). Two classes, 7 pairs: 7 "different" from the label gate (MaxSim 0.02 to 0.27). False same 0 of 15 different pairs, false different 1 of 12 same pairs, 1 "not sure" in all. Composite images share pixels for one object, so the same-object scores are optimistic; real camera pairs (cat, motorcycle, stop sign) scored 0.93 to 0.99. The 0.86 value sits between the highest different pair (0.835) and the second-lowest same pair (0.889), so it rests on two close points.

## Known limits (to `research/edge-cases.md` when built)

- Hands and the booth background raise the score for two different objects held in one spot.
- "Hold it up, and I will compare" also answers "Have you seen this before?" when the visitor means the scene.
- Lookalike instances (two mugs of one model) score up to 0.874 (E, D154). The answer says "looks like the same", which is true for lookalikes.
