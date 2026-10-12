# Same-object answers

Status: design, 2026-10-12, revision 2; design review GO with the changes below applied. Not built.

## Problem

"Is this the same thing I showed you before?" goes to the 2B brain with the present image and a Memories line. The 2B says yes by default. Dev `same-apples-2` fails this way: it calls teddy bears "the same thing" as the apples it saw earlier, and held-out shows the same yes-bias. A booth visitor will try this. A wrong "yes" makes the robot look dumb, and a right answer shows vector search at work.

## Proposal: answer comparisons in code, from what the robot tracked

1. **Held objects per turn.** At each answered turn, the robot resolves the visitor's object with `_target(turn)`. When that track is an object (not `BODY`), it keeps up to `SHOTS` crops of it in RAM. The crops come from the detected frames that own the boxes (`[(view_taken, *view), *reversed(views)]`, as `_bind` does), never from a camera frame cut with a later box. Each entry keeps the track id, the voted label, the crop capture times, and the turn time. A small deque holds the entries for one conversation. A new conversation and every deletion clear it, like `looked`. Nothing reaches disk, and no vector is computed until a comparison asks.
2. **Which questions.** `same_question(text)` in `robot/memory.py` holds for a yes/no question (an `is/are/was/does/did/have` opener) with a past cue ("before", "earlier", "showed", "again", "first", "last", "just") and either "same", "different", or "similar", or "this/that/it" ("Have you seen this before?"). "Like" counts only in "like the one before". Plain recall ("What did I show you just now?") and present questions keep their paths. The self-test includes these negatives: "Does this look like a phone?", "Is this the same color as my shirt?", "Is it different from a cup?", and "What did I show you just now?".
3. **The answer, first rule that applies:**
   - No object target now: "Hold it up, and I will compare." (code)
   - No earlier entry from another turn: the brain answers, as today.
   - Different label groups, between two different track ids (`KINDS` in `memory.py`): "No. Earlier you showed me {article(earlier)}; this is {article(now)}."
   - Same label group, or the same track id (a swap in hand can keep one id and its voted label): MaxSim of up to three crops on each side with the DINOv2 descriptor that named objects use. A score at or above `settings.match` gives "Yes, it looks like the same {label}." A score inside `settings.guess_band` below it gives "It looks similar, but I am not sure it is the same {label}." A lower score gives "No, that looks like a different {label}."
4. **Evidence.** The turn records both entries' capture times, the labels, and the score, and the answer names the object it compared. The answer is code-owned, so `turn.verbatim` is true and the brain is not called.

## Alternatives

- (B) Send both crops to the brain as two images. This costs about 256 more image tokens and up to 0.49 s more prefill (D39, J). The yes-bias is in the 2B's answer, so B likely keeps it.
- (D) Labels only: answer from the detector labels and skip DINOv2. It is cheaper and survives hand occlusion. It cannot tell two different mugs apart, and it answers "same" for every same-class pair. The proposal uses D as its first layer.

## Measurement

- Dev pairs on the Mac, at least five per category: same object at two views, two different objects of one class (including a swap in hand at one spot), two different classes, and real camera crops from `eval/dev/live` where they exist. Report both error directions: false "same" and false "different". The same-label score policy (`match`, `guess_band`) is set from these pairs, and both stay UI settings.
- The question gate gets dev cases with comparison phrasings that lack a show word ("Is this the same laptop as before?", "Have you seen this before?") and non-comparisons ("What did I show you just now?").
- Replays: dev fixtures give the focus 1.0 s (`STEADY_S`) to settle, so each comparison step has a real `wait` after `show`, as a visitor holds an object up. The builder confirms that replay turns get a target before claiming a fix.
- Held-out fixtures stay frozen; when held-out is next used, report comparison turns that got no target as a separate count.
- Integrated: one Jetson replay of `eval/dev/sessions.jsonl`, paired with the current release. The result must keep 42/47 or better and fix `same-apples-2` with no new miss.

## Known limits (to `research/edge-cases.md` when built)

- Hands and the booth background raise the score for two different objects held in one spot.
- "Hold it up, and I will compare" also answers "Have you seen this before?" when the visitor means the scene.
- Lookalike instances (two mugs of one model) score up to 0.874 (E, D154). The answer says "looks like the same", which is true for lookalikes.
