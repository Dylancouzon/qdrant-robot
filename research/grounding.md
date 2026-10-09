# Making a small brain use retrieved memory (grounding)

As of 2026-10-08 (researcher, Sonnet). Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

- Problem (J, V1-B): Qwen3-VL-2B ignores correct memory lines in its prompt; retrieval into the brain lost to code answers (m2 34/74 vs 41/74, visitor 15/21 vs 17/21). Qwen3-VL-4B does not fit (D68).
- Prompting (no published numbers at 2B): opinion plus instruction framing (evidence as narrated memory, "answer from it") cut the memorization ratio from 35.2% to 9.1% and raised exact match 6.2 to 48.6 on GPT-3.5 (E, 175B; also LLaMA-2-7B); counterfactual demonstrations cut it from 53.3% to 7.0% (E); place evidence at the start or end, best right before the question (Lost in the Middle, E, larger models); llama.cpp supports assistant prefill (for example "From my memory,"), gain U. Side effect: "say unknown" instructions can lower accuracy on normal contexts (FaithEval, E): test plain chat too.
- Models: Vectara leaderboard (summarization, 2026-09-22): Qwen3-4B 5.7%, Gemma-3-4B-it 6.4%, Phi-4-mini 23.5% hallucination (E); no 1 to 3B models or VLMs listed; no faithfulness numbers found for Qwen3.5-2B, Gemma 4 E2B, SmolVLM2, LFM2-VL, InternVL3, MiniCPM-V (one paper: Gemma 4 E2B faithfulness 0.784, E, unchecked).
- Training: RAFT (Llama-2-7B): one gold document plus four distractors, gold present in 40% to 100% of examples, chain-of-thought answers HotpotQA 35.3 vs 25.6 (E); gains at 1 to 3B U. Unsloth lists about 5 GB VRAM for a Qwen3.5-2B bf16 LoRA (E, vendor): a 10 GB RTX 3080 should fit; GGUF export with the vision projector for a Qwen3-VL LoRA is U (merge, then convert_hf_to_gguf.py, expected, not confirmed).
- Grammars (GBNF, json_schema) would force citations on every turn and break free chat: skip.
- Ranked: (1) about 1 h of prompt work (memories last, opinion plus instruction, prefill, 2 to 3 counterfactual demos); (2) about 2 h model swap A/B (Qwen3.5-2B, Gemma 4 E2B); (3) 1 to 2 days RAFT-style LoRA with synthetic data, 20% without relevant evidence, and a GGUF round trip.

## Sources

- https://arxiv.org/abs/2307.03172
- https://ar5iv.labs.arxiv.org/html/2303.11315
- https://arxiv.org/html/2410.03727v3
- https://arxiv.org/html/2403.10131v2
- https://github.com/vectara/hallucination-leaderboard
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- https://unsloth.ai/docs/de/modelle/qwen3.5/fine-tune
