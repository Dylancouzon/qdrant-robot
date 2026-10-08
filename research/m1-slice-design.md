# M1.2 vertical slice: design brief

As of 2026-10-08. Evidence: `research/stack.md`, `research/endpointing.md`, D19 to D22, `bench/results/2026-10-08-*`.

## Summary

- Goal: the thinnest robot that does one real thing on the Jetson alone: a visitor asks about an object, hears the answer, removes the object, and asks what they showed. Plus knowledge questions about Qdrant from the Edge knowledge shard.
- Brain: Silero VAD and Parakeet TDT 0.6B v2 (CPU) in front of Qwen3-VL-2B Q4_K_M on llama.cpp (GPU); speech in is provisional until real voices test it (D24). Retrieval runs in code every turn; memories and facts enter the prompt as labeled lines; no model tool calls (D21, D22).
- Latency plan: prefill the system prompt and the current frame when speech starts (llama-server prompt cache: cold 964 ms, cached 98 ms to first token, J). Measured from end of speech (replay, 15W, J): transcript 0.68 s, first token 0.83 s, first phrase 1.13 s, first synthesized audio 1.68 s p50.

## Alternatives and how each is measured

1. **Process layout.**
   - (A, proposed) One Python process that owns everything except the LLM, which runs as a supervised `llama-server` child on localhost (streaming SSE, built-in prompt cache, image hashing, grammar-free chat template).
   - (B) The LLM in-process through ctypes on our own `libllama` and `libmtmd`, with our own KV prefix management.
   - Measure: RAM of the child's extra CUDA context (B saves it), added latency per turn of HTTP and SSE parsing, and code size. Switch to B if A costs more than 150 MB or 20 ms per turn.
2. **Brain.** (A) Qwen3-VL-2B behind the speech-in stack (20/21 dev, 0.80 s cold first token, about 1.6 GB). (B) Gemma 4 E2B omni with audio in (14/21, 0.95 s, about 3.5 GB). (C) Qwen3.5-2B (18/21). Measured in `bench/brain_bakeoff.py`; held-out eval and real voices decide later.
3. **Past-object recall in the slice.**
   - (A, proposed) A `memory` Edge shard with one point per turn: the bge vector of the question plus the answer, a timestamp, and the stored frame (JPEG path) as evidence. Every turn searches it with a score gate and adds lines such as "4 minutes ago the visitor asked 'what is this?'; you saw and said: 'a red mug'".
   - (B) Re-show the stored frame itself to the VLM for past questions. That is more faithful but adds an image encode (about 0.5 to 0.9 s).
   - (C) M2's design: SigLIP 2 image vectors per frame and per tracked object with left, center, and right regions.
   - Measure: memory-recall correctness on dev fixtures and its latency cost. The slice uses A; M2 replaces it with C and keeps B for "look again".

## Turn loop (one process, threads plus bounded queues)

- Audio source: microphone (`arecord` raw 16 kHz) or a WAV file for scripted sessions; 80 ms chunks.
- Speech in: Silero VAD on each 32 ms frame. Speech start grabs the frame and prefills it if the kept-warm look is stale; the line end hands the audio to Parakeet in its own thread, whose transcript starts a turn.
- Turn: embed the text (bge-small, ORT CUDA), search knowledge and memory shards (Edge, one owner thread), build the user message (frame, facts, memories, question), stream from llama-server, cut phrases, synthesize with Kokoro (ORT CUDA), play or save WAVs. Log stage timestamps.
- Barge-in: a new `LineStarted` while speaking cancels generation and playback.
- Write the turn to the `memory` shard after the answer.
- Startup check: available RAM after all components load must cover a reserve for M2 and M3 components (detector, face models, SigLIP 2: 1.0 GB budget) plus 1.0 GB headroom; otherwise report the gap.

## Revision 2026-10-08: speech in, and the 4B candidate

Measured after the first replays (D24). Alternatives for speech in, each measured on the Jetson with `bench/asr_bench.py` on the same 20 fixture WAVs:

1. (A, adopted) Silero VAD (CPU, one thread, 0.35 s hangover) plus Parakeet TDT 0.6B v2 int8 on the CPU (four threads) for the line: 0.8% WER, line end 0.34 s p50, transcript 0.61 s p50, about 1,050 MB.
2. (B) Moonshine Tiny Streaming alone: 4.3% WER, 0.46 s; it heard "Qdrant" as "current" or "grant", which broke knowledge retrieval in the replay.
3. (C) Moonshine segmentation plus Parakeet: the final pass waited for the prefill or slowed under contention (0.95 s); with `skip_transcription`, lines ended later (0.73 s) and a monologue split.
4. (D) Parakeet on the GPU (fp32 3,152 MB; int8 994 MB, 0.23 s): no faster than the CPU, and it contends with the brain's prefill.

Next measurement: Smart Turn v3 to cut the hangover, and real voices.

Brain candidates kept for bake-offs: Qwen3-VL-4B (Q4_K_M, 2.5 GB plus mmproj). Replay at 15W: 9/12 with keyword scoring (both scorer errors), passes the scene-change and greeting cases the 2B fails, first phrase 2.1 s p50 against 1.1 s. Decision waits for a larger dev set and a judge.

## What is out of the slice

Detector, tracking, faces, SigLIP 2, Smart Turn, speculative generation, display. Each comes with its milestone.

## Open risks

- Synthetic voices flatter ASR (0.8% WER). Real voices, names such as Qdrant, pauses, and booth noise on 2026-10-08.
- No speaker on the Jetson yet: output is WAV files plus a Mac client until a USB speaker arrives.
- 15W mode caps the GPU at 625 MHz; Super mode needs Dylan.
