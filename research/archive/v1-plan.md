# v1 plan: the Fable review of the assistant plan (adopted, D62)

As of 2026-10-08. Independent review by a Fable subagent with the whole repo as context, on Dylan's request; adopted by Dylan and the lead (D62). Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

Implementation status (2026-10-09, D75): first-phrase decode pause, wake/follow-up window, focus, and memory panel are wired. Evidence fixes stay; code answers stay because one voice missed the frozen M2 rule by one step. The 4B did not fit (D68). Intents, Formula decay, Rrf, diverse object views, and longer answers remain proposals. Read research/lessons.md and research/grounding.md before repeating the initial comparisons below. D77 permits challenging their assumptions with a concrete intervention and paired validation.

- Retrieval: never decide whether to search; always search. The question is embedded once with bge, and each Qdrant Edge search costs about 0.5 ms (J, D36), so four shards cost about 2 ms, less than any classifier that decides whether to search. Per-shard minimum scores are the gate, calibrated with absent-memory negatives (the pattern of `robot/knowledge.py`: MIN_SCORE 0.75, off-topic 0.74 or less, knowledge 0.81 or more, J). The only pre-retrieval decision kept: whether the image goes into the prompt (a stale image pulls the 2B off its memories, D27).
- Actions (side effects), ranked by the cost of a false action: (1) rules first: negation ("don't forget my phone" sits close to "forget my phone" in bge space) and slots ("my phone" vs "my face"); (2) one Qdrant Edge intents shard (one point per action, example phrasings as a multivector, MaxSim, about 1 ms) for paraphrases, replacing `robot/route.py` (the same mechanism: nearest examples over bge); (3) in the uncertain band, a confirmation question ("Do you want me to forget your phone?"), the consent state machine pattern.
- No LLM classifier in v1: llama-server runs one slot (`-np 1`), so a classification prompt evicts the prefilled frame and the answer re-prefills 256 image tokens plus history, about 0.2 to 0.3 s at 1,492 tok/s (J), on a path already at 1.61 s p50 against 1.2 s; D21 rejected model tool calls; D43 shows the 2B ignores correct evidence, so it is the wrong arbiter for side effects. The Jev-style brain classifier stays a measured experiment after v1, only if rules and the intents shard miss on a paraphrase set.

## The whole plan

- Build order: breadth first; compare the new answer path on the integrated visit before deleting code answers. The 2B/4B comparison is complete (D68, D74, D75); the 4B misses the memory floor. Live conversation uses swap (D76), so historical headroom snapshots cannot justify longer context. Evidence retrieval and caption quality remain interventions beyond prompt shape (D77).
- Over-engineered for v1: six Qdrant-forward features at once. Ship two that answer real questions: a `Formula` with an exponential time decay over `last_seen` times similarity (recency for "where is my phone"), and `Fusion.Rrf` over a statement prefetch and a sighting prefetch in the memory shard (one shard, so `Prefetch` works). `Mmr` only if same-kind sightings flood the top k on dev; `Facet` and named-vector text search wait. All exist in qdrant-edge-py 0.8.0 (stubs).
- Missing:
  - The real latency lever is TTS, not routing. In the audio integrated visit (bench/results/2026-10-08-replay-1791496489): ASR done 0.76 s, first token 0.91 s, first phrase 1.08 s, first audio 1.61 s (J). Synthesizing the first two-word phrase costs 0.53 s while Kokoro on CUDA runs at RTF 0.15 (research/stack.md): contention with llama decode or per-call setup.
  - 200-token answers at 28 tok/s take about 7 s; the single worker serializes looks, sightings, and captions behind a turn, so memory writes lag; four exchanges of 200 tokens plus 256 image tokens plus evidence approach `-c 2048`. Raise context or cut history, and verify that interruption cancels a long answer.
  - Booth noise: no recordings with babble yet; the 0.35 s hangover already splits questions on a clean microphone. Record booth-like noise before the speaker arrives.
  - "Qdrant hatch": grow the ASR fix list (`robot/asr.py` `_FIXES`) from logged misses; no embedding threshold rescues it.
- Biggest risks, ranked: the 2B ignoring evidence (D43; the visitor-gone answer invented a keyboard); audible latency with no speaker measured yet; ASR in noise with the camera microphone; RAM if a 4B is the answer to risk one.

## Initial recommendations and their status

1. Always retrieve; per-shard calibrated minimum scores are the gate. No "should I search" classifier.
2. Actions: rules first, one merged intents shard (replacing `robot/route.py`) second, confirmation in the uncertain band. No LLM classifier in v1.
3. TTS first-phrase contention was measured and decode pause landed (D66, D72).
4. The 2B/4B evidence and RAM comparisons ran; code answers remain (D68, D74, D75).
5. Ship two composable queries (decay Formula, Rrf of statements and sightings) and the memory panel; defer Mmr, Facet, and named text vectors.
6. Measure active-turn memory and paging before choosing longer context or history; then verify long answers and interruption.
7. Record booth noise and extend the ASR fix list from logged misses.

Dylan's addition (D62): push the robot further than anyone else; training is not off the table. Squeeze the bigger model if RAM allows, finish v1, live test, then decide optimizations and training from the biggest measured gaps.

## Sources

- Review inputs: CLAUDE.md, STATE.md, DECISIONS.md D35 to D61, research/assistant-design.md, robot/ code, bench/results/2026-10-08-replay-{1791496173,1791496489,1791494672}, reviews/20261008-190813-295-design.md, reviews/20261008-165842-36020-design.md, refs/qdrant-edge-memory-robot, qdrant-edge-py 0.8.0 stubs.
