# Making a small brain use retrieved memory (grounding)

As of 2026-10-09. Initial research by Sonnet; D74 and D75 record completed comparisons. Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

- Current result (J, D75): evidence fixes stay. M2 HEAD 39/74, retrieval into the brain 38/74, fixed code answers 44/74; visitor 16, 17, and 16/21. Code answers remain because the frozen one-voice rule missed by one M2 step. The M2 gain is dev-only; exact files and compact queries are in research/lessons.md. The alternate path is research/one-voice.patch.
- Prompting (no published numbers at 2B): opinion plus instruction framing (evidence as narrated memory, "answer from it") cut the memorization ratio from 35.2% to 9.1% and raised exact match 6.2 to 48.6 on GPT-3.5 (E, 175B; also LLaMA-2-7B); counterfactual demonstrations cut it from 53.3% to 7.0% (E); place evidence at the start or end, best right before the question (Lost in the Middle, E, larger models); llama.cpp supports assistant prefill (for example "From my memory,"), gain U. Side effect: "say unknown" instructions can lower accuracy on normal contexts (FaithEval, E): test plain chat too.
- Models: Vectara leaderboard (summarization, 2026-09-22): Qwen3-4B 5.7%, Gemma-3-4B-it 6.4%, Phi-4-mini 23.5% hallucination (E); no 1 to 3B models or VLMs listed; no faithfulness numbers found for Qwen3.5-2B, Gemma 4 E2B, SmolVLM2, LFM2-VL, InternVL3, MiniCPM-V (one paper: Gemma 4 E2B faithfulness 0.784, E, unchecked).
- Training: RAFT (Llama-2-7B): one gold document plus four distractors, gold present in 40% to 100% of examples, chain-of-thought answers HotpotQA 35.3 vs 25.6 (E); gains at 1 to 3B U. Unsloth lists about 5 GB VRAM for a Qwen3.5-2B bf16 LoRA (E, vendor): a 10 GB RTX 3080 should fit; GGUF export with the vision projector for a Qwen3-VL LoRA is U (merge, then convert_hf_to_gguf.py, expected, not confirmed).
- Grammars (GBNF, json_schema) would force citations on every turn and break free chat: skip.
- The initial prompt/model recommendation was exercised in the bake-off below. D76 and D77 require a concrete intervention or disputed assumption before repeating it. Training remains open; prior prompting results do not establish that a LoRA fixes missing evidence.

## F0 sufficient-evidence diagnostic (2026-10-09, D87)

J: on release 51bdbb62cea6, the same Qwen3-VL-2B generated answers for 24 development questions with original versus verified sufficient evidence. Question, system, history, image policy, and 2K/256-image/64-output/one-sentence limits stayed fixed. The three-vote judge scored 14/24 versus 21/24, with seven paired wins and zero losses. Evidence questions scored 12/20 versus 19/20; four unchanged sight/chat controls scored two/four in both arms. The 11 unchanged packets had equal verdicts, with nine byte-identical answers.

Three sufficient-arm failures remain: a general spider question, the missing red handbag, and the current-room description. F0's eight-failure trigger for language specialization is unmet. Prioritize observation detail, source-linked retrieval, and dialogue continuity; revisit training if correct production evidence still leaves at least eight failures on a comparable development diagnostic. This upper bound does not establish a deployed gain, physical latency, active paging safety, long conversation, or held-out performance. Both arms forced generation, including cases the deployed robot answers in code.

Evidence: bench/results/2026-10-09-bakeoff-evidence-probe-1791527749.jsonl and its .judged.jsonl; f0-evidence-20261009-023549.tegrastats; bench/results/2026-10-09-f0-operations.jsonl. Manifest SHA256: 31451ef2d419add469b3d4fa6ce14d93bf655d3fc6026f7a391751d9122808ca. Query: `python3 tools/results.py --cases eval/dev/evidence-probe.jsonl --limit 1`.

## Mac bake-off result (2026-10-08, D74)

- Five brains x nine prompt shapes on the robot's own retrieval prompts (bench/brain_bakeoff.py; m2 /74, visitor /21; code answers 41, 17): qwen3vl-2b 32,14 (current) -> 38,14 (evidence first) or 37,14 (shape I, evidence words after the image, keeps the frame prefill); lfm2vl-3b up to 43,15 (but larger, a longer re-prefill, misreads composites); gemma4-e2b up to 37,15; qwen35-2b up to 31,13; qwen3vl-4b up to 42,16 (does not fit).
- The gap is mostly the evidence: lines without colours or details, contradictory lines, "your right" for the robot's right, missing "the visitor told you" lines, ownership claimed from weak matches. Even the 4B fails those rows. A LoRA is not the next step.

## Foundation audit: retrieval and sustained conversation (D77)

- Verified in merged code: `Memory.recent()` returns three recent captioned frames; `_recall()` uses that list and recent sightings. `Memory.add()` writes only the `said` vector. An image slot is declared but not populated; captions have no semantic query. A BGE caption index with source/time filters is a candidate, with no new vision model implied. Compare recalled evidence and answers on older scenes against the current recency path. D27's stale-context result protects present questions; it does not forbid semantic recall.
- Verified caption contract mismatch: CAPTION requests "Main object... . Around it...", but `Brain.caption()` shares `answer()` and its one-sentence stop. The earlier AST probe demonstrated that stop; its contribution to benchmark misses is unproven. Candidate: separate caption stopping from spoken-reply limits, then measure evidence detail and stale claims.
- Verified structures, unproven effect: `Robot.jobs`, `lines`, `turns`, `uncaptioned`, and `audio.Mouth` playback are unbounded. Speech start does not cancel queued playback. Candidate: cancel stale playback and bound replaceable work; measure queue depth, delay, memory, and interrupted turns together. These structures are not an established cause of live swap.
- Conversation continuity is open: scene-change prefill drops assistant messages to avoid stale visual claims (D27). Test retaining linguistic context while removing stale visual context. Existing context-budget probes sized a synthetic 1,300-token prompt plus 64 output tokens; bake-offs used 2K/64/one sentence. No 4K or 8K sustained-conversation result was found. Measure active-turn paging before selecting a longer context; see research/stack.md.

Code evidence: robot/memory.py `add()` and `recent()`; robot/main.py `_recall()`, `_look()`, and work queues; robot/brain.py CAPTION, `answer()`, and `caption()`; robot/audio.py `Mouth`. These are candidate interventions, not H1 runtime changes.

## Sources

- https://arxiv.org/abs/2307.03172
- https://ar5iv.labs.arxiv.org/html/2303.11315
- https://arxiv.org/html/2410.03727v3
- https://arxiv.org/html/2403.10131v2
- https://github.com/vectara/hallucination-leaderboard
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- https://unsloth.ai/docs/de/modelle/qwen3.5/fine-tune
