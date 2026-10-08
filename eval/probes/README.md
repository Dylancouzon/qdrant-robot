# Generalization probes

Unseen phrasings that check a dev fix generalizes (review rule 6, `gates/review.md`). Replay them with `--oracle` (text, no audio). They are never tuned on: a probe that fails points to the fix, not to a new probe-specific change. Written 2026-10-08 for the past-statement prompt and the joke sentence cap.

`sight.jsonl` (2026-10-08): ten COCO val2017 photos (CC BY or CC BY-SA, not used elsewhere in `eval/`), one main object each, for the sight bake-off in `research/sight.md`.

`sight-hard.jsonl` (2026-10-08): ten cluttered COCO val2017 scenes (four or more object kinds, not used elsewhere), each asking about one object by position or role. `sight.jsonl` was too easy (9/10 at baseline) to separate the bake-off arms.

`m2.jsonl` (2026-10-08): M2.1 sightings probes, five sessions and eight scored steps (removed objects, left and right, "while I was away"). A green kitchen and four objects (backpack, orange, flower pot, books) from COCO val2017 that `eval/dev` and `eval/heldout` never show, composed by `eval/make_scenes.py ... probes`. Run once with `--oracle`.

`m2.jsonl` (2026-10-08, spent by M2.1: 0/8) and `m2b.jsonl` (2026-10-08, written before the M2.2a code, run once: 8/9): composites on backgrounds used nowhere else in `eval/`, for removed, left/right, still-there, and where questions.

`m2c.jsonl` (2026-10-08, written before the M2.2a re-review fixes, run once: 7/8): kitchen background (COCO 343466) with two teddy bears, a clock, and two dogs, for same-kind objects on one side, past against present, an object that moved sides, and "it". Two object instances were swapped before the run because the detector mislabeled them (a clock as poster, a dog as person); the phrasings were frozen. These probes test the answer logic, not the detector.

`m2d.jsonl` (2026-10-08, written before the M2.2b code; run once with `--oracle`): naming, recall by name, forget, ignore, and the "which one?" question, on a bright kitchen (COCO 445846) with objects no other set shows: two black phones (a smartphone and a flip phone), two golden teddy bears, a paper coffee cup, and a Coca-Cola bottle. Same-class pairs share a color, so a color match alone cannot pass. Before the first run, the left and right steps became region-free questions ("can you see my phone?"), because Dylan dropped left and right (the robot cannot turn).
