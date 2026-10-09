# The assistant: retrieval feeds the brain, actions in code

Direction adopted in D61 on 2026-10-08; implementation status updated 2026-10-09. Labels: J measured on an Orin Nano, E measured elsewhere, U unverified. Gated GO WITH CHANGES (reviews/20261008-190813-295-design.md, D61).

## Summary

- Direction (Dylan, 2026-10-08): the robot is a conversational assistant first; memory is context, not the answer path. Retrieval feeds the LLM (one voice); every answer comes from the brain. Vector search is central, including for what the robot sees. People name objects ("Dylan's phone"), as in `refs/qdrant-edge-memory-robot`. No left or right logic (the robot cannot rotate). Open conversation, no guided questions. Answers longer than 64 tokens. A minimum retrieval score keeps the brain from answering from a random memory. v1 first, then measure headroom, then decide on a bigger brain or training.
- Current (D75): code answers stay. Retrieval into the brain scored 38/74 versus HEAD's 39/74 and missed the frozen rule by one M2 step. Evidence fixes raised code answers to 44/74, dev-only pending unseen probes. The alternate path is research/one-voice.patch; answers remain at 64 tokens and one sentence (D72). See research/grounding.md for the completed bake-off and D77's open retrieval/conversation questions.

## Proposal

The following describes the intended direction, not completed runtime features. D63 kept 64 tokens for v1. Longer answers and context require integrated memory, latency, and interruption measurements; D76 records live conversation swap.

1. **Turn flow.** ASR text -> action router -> (an action: run it in code, then the brain says one line about the result) or (a question or chat: embed once with bge, search every shard in parallel in Qdrant Edge, keep hits above each shard's minimum score, pass at most a few short evidence lines with ages to the brain with the current frame and the conversation window; the brain answers). Below every threshold, the brain answers as a plain assistant with no memory lines.
2. **Shards.** knowledge (facts, MaxSim over phrasings), conversation (statements and the robot's answers), objects (taught objects: crop views as a DINOv2 multivector plus a bge vector of the spoken name; sightings of recognized objects with times), people (face shots, D45), all existing or planned.
3. **Objects, crowd-safe** (adapted from the reference robot): YOLOE boxes and tracks; class names are only a hint. One focus object at a time: the largest stable track nearest the center (what a visitor holds up). The video view labels it with its learned name when a crop matches a taught object above the recognition threshold, else "Smartphone?" (detector class) or "???". "This is Dylan's phone" teaches the focus object (several crops from its track, its name as text); later sightings of a recognized object are stored with time. Recall by name searches the name vectors, then the object's latest sightings, and feeds them to the brain. Other tracks in frame are tracked, not taught.
4. **Actions.** name this, forget this object, ignore a class, remember me (consent), forget me. Routing alternatives below.
5. **Generation.** Up to about 200 tokens, two or three spoken sentences by prompt, streamed phrase by phrase to TTS (first audio unchanged by the cap).

## Alternatives and how each is measured

- Answer path: (A) retrieval lines into the brain (proposed) vs (B) today's code answers. Measure on dev memory questions and a one-time paraphrase set: answer correctness, answer-uses-evidence rate, answers from irrelevant memories (precision of the minimum score), first-audio p50.
- Action routing: (A) the resident brain as a zero-shot classifier (Jev-style: one forward pass, read the probabilities of a few action labels; no extra RAM) vs (B) the existing bge router with labeled example phrasings plus small slot rules vs (C) a separate small open classifier (GLiClass). Measure: action accuracy and false actions on dev phrasings and a one-time paraphrase set, added latency, RAM.
- Object vectors: DINOv2-small crops (M2.2b bake-off winner for re-identification) plus bge name text (proposed) vs SigLIP 2 for both crops and text. Measure: same-class re-identification at zero false matches (M2.2b data), recall by spoken name, ms per crop, RAM.

## Risk

The 2B ignored long context blocks (D43). The evidence becomes a few short ranked lines, and the miss rate is measured; if it stays high, the next lever is a bigger brain (Dylan: after v1), not more code paths.

## Sources

- Reference robot: `refs/qdrant-edge-memory-robot` (README, docs/architecture.md): YOLOE class names discarded, CLIP image and Nomic text vectors per taught view, one prominent unknown, recognition threshold with guesses shown below it.
- Jev (TypeSafe AI, hosted, judgment-only) and open versions (Featherless Simple Jev, Kev-8B): https://www.glean.com/blog/jev-zero-shot-classifier, https://thenewstack.io/featherless-simple-jev-classifier/, https://parallel.ai/blog/testing-jev (U on our hardware).
