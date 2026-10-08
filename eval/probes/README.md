# Generalization probes

Unseen phrasings that check a dev fix generalizes (review rule 6, `gates/review.md`). Replay them with `--oracle` (text, no audio). They are never tuned on: a probe that fails points to the fix, not to a new probe-specific change. Written 2026-10-08 for the past-statement prompt and the joke sentence cap.

`sight.jsonl` (2026-10-08): ten COCO val2017 photos (CC BY or CC BY-SA, not used elsewhere in `eval/`), one main object each, for the sight bake-off in `research/sight.md`.

`sight-hard.jsonl` (2026-10-08): ten cluttered COCO val2017 scenes (four or more object kinds, not used elsewhere), each asking about one object by position or role. `sight.jsonl` was too easy (9/10 at baseline) to separate the bake-off arms.

`m2.jsonl` (2026-10-08): M2.1 sightings probes, five sessions and eight scored steps (removed objects, left and right, "while I was away"). A green kitchen and four objects (backpack, orange, flower pot, books) from COCO val2017 that `eval/dev` and `eval/heldout` never show, composed by `eval/make_scenes.py ... probes`. Run once with `--oracle`.
