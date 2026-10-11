# State

Updated 2026-10-10. Branch: `spike/evidence-selection`. Read CLAUDE.md, this file, and [research/lessons.md](research/lessons.md) first. Builders this session: Sonnet sub-agents, the main session orchestrates (Dylan, 2026-10-10).

## Active task: recall of objects shown earlier

The eight failed recorded answers (39/47) include no evidence-selection error, so the intent parser is dropped. Three misses ask about an unnamed object shown before a scene change, and the brain gets no evidence for it. Design: [research/recall.md](research/recall.md).

1. Forget guard: done (`2a88558`); deletion needs an imperative (`robot/memory.py` `deletion_target`).
2. Design gate: option B, the earlier frame in RAM (GO WITH CHANGES). Fixtures frozen in `e688d90`: `eval/dev/recall.jsonl`.
3. Built and reviewed (PASS): `53867a9`.
4. Paired Jetson replay of B: recorded 39/47 to 38/47, recall sessions 8/15 to 10/15 (J). The right frame arrives, but the 2B mishandles a labeled past image. Not adopted; see `research/recall.md`.
5. B-note arm (B with a past-tense note, `ac7395d` in worktree `build/wt-bnote`): recorded 41/47, recall 11/15 (J). B2 (captions of retained frames, code answers; design and review passed): Jetson arm running. Adopt the better arm after a per-capability check.
6. Then command set v2 (Dylan approved, 2026-10-10): distinct verbs ("remember me", "remember this", "forget ..."); the robot asks for names and confirms deletions; introductions no longer offer face enrollment; unknown objects get a teach-the-command reply. Design gate, frozen dialogue fixtures, then build.

Parallel builder (worktree): the UI ignore dropdown keeps items about 8 s after they leave the frame, and spoken ignore is removed (Dylan, 2026-10-10).

Four misses are model answers with adequate evidence (hand-teddy-3, same-apples-1, joke-1, intro-2). Owner and location payloads (Dylan, 2026-10-10) need their own design gate. RAM headroom follows.

## Robot

- Jetson: `ssh robot`; MAXN_SUPER, boot `09b4bb27`. Accepted release `7f67670fa91e` (still on disk). `current` points at unadopted candidate `4d1aaab22abd` from the paired replay; switch back to the accepted release before any live demo.
- Running jobs: none on the Jetson. The live Mac preview is paused.
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
