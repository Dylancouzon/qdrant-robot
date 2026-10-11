# State

Updated 2026-10-10. Branch: main. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first.

## Active task: intent parsing for evidence selection

Goal: answer quality. Of the 8 failed recorded answers (39/47, current Qwen/CUDA), 4–5 chose the wrong evidence: past questions sent to the camera, and combined "now and before" questions. The plan is [research/answer-evidence.md](research/answer-evidence.md).

1. Rerun the held-out set on the deployed release as the baseline (third use; record it in DECISIONS.md).
2. Design gate: rules vs independent BGE similarity scores, both with Qwen fixed. A linear multi-label head only if both miss unseen paraphrases.
3. Build the winner and run a paired Jetson comparison on development questions. Adopt only on a judged gain with no capability loss.

Owner and location payloads (Dylan, 2026-10-10) come after the parser and need their own design gate.

## Robot

- Jetson: `ssh robot`; current release `7f67670fa91e`, previous `6781adbb7189`; MAXN_SUPER. Boot `09b4bb27`.
- Running jobs: none. The live Mac preview is paused.
- WSL box: idle.

## Targets (floor, not ceiling)

| Target | Latest | Status |
| --- | --- | --- |
| 90% correct per capability | Dev recorded 39/47 (83%); held-out 18/26 (2026-10-08, `bench/results/2026-10-08-replay-1791470020.judged.jsonl`) | Miss |
| Zero false identities on strangers | M3 dev 33/33; no stranger acceptance run | Unmeasured |
| 1.2 s p50 / 2.0 s p95 audible | 1.59 / 2.09 s first WAV from recorded questions; physical audible latency unmeasured | Close miss (secondary) |
| 30 tok/s decode | 29.1 tok/s | Close miss (secondary) |
| 15 fps detection while talking | Below 15 during synthesis | Close miss (secondary) |
| Edge 10 ms p99 | 0.49 ms at 1,000 points (D36) | Met; retest at full retained volume |
| 500 MB headroom, no swap in a turn | 558 MiB; paging in 36/48 turns | Miss |

M4 also needs a Jetson-connected speaker and microphone (Dylan), offline cold start, restart and deletion checks, physical latency, and an eight-hour run. Milestone gates: only M1 has a verdict (2026-10-08).

## Known risks to fix soon

- "Do not forget my phone" matches the forget regex: a possible unintended deletion (`research/edge-cases.md`). It risks a fixed outcome, so D71 allows a fix.

## Next command

`cat research/answer-evidence.md`
