# State

Updated 2026-10-10. Branch: `spike/evidence-selection`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders this session: Sonnet sub-agents, the main session orchestrates (Dylan, 2026-10-10).

## Active task: recall of objects shown earlier

The eight failed recorded answers (39/47) include no evidence-selection error, so the intent parser is dropped. Three misses ask about an unnamed object shown before a scene change, and the brain gets no evidence for it. Design: [research/recall.md](research/recall.md).

1. Forget guard: done; deletion needs an imperative (`robot/memory.py` `deletion_target`). Not deployed yet; ships with the recall release.
2. Design gate on recall options A (earlier sight answers) and B (earlier frame). In progress.
3. Freeze new show-then-ask development sessions, build the chosen option, check locally.
4. One paired Jetson replay of `eval/dev/sessions.jsonl` (recorded voice) plus the new sessions. Adopt on a judged gain with no capability loss.
5. Then one held-out use with both arms in the same run (third use; record it in DECISIONS.md).

Four misses are model answers with adequate evidence (hand-teddy-3, same-apples-1, joke-1, intro-2). Owner and location payloads (Dylan, 2026-10-10) need their own design gate. RAM headroom follows.

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

## Next command

`cat research/recall.md`
