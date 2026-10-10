<!-- Claude Code Opus; full session comparison: 30639f5 against the working snapshot; job review-mv2ghg0m-bhjfcg; 2026-10-10 -->

# Claude Code Adversarial Review

Target: working tree diff
Verdict: needs-attention

No runtime blocker, but do not commit yet: the main records still have readability faults and one evidence gap. The repo is cleaner than 30639f5 in STATE.md, the topic guides, and lessons.md. DECISIONS.md is harder to read than before.

Findings:
- [medium] STATE.md commands cannot be copied because spaces are missing (STATE.md:13-52)
  STATE.md is the only status file, and CLAUDE.md requires it to record exact commands. Several tokens are glued together. Line 32 has `tools/talk.py --release7f67670fa91e --port8765`, which fails if pasted. Line 34 has `robot.main --listen7070`. Line 13 has 'fixed50-word' and 'Edge0.8'. Line 50 has 'modelopus, scopeworking-tree' and 'nodeclaude-companion.mjs'. Line 52 has 'base30639f5'. Line 52 is prose and gives no exact next command, which the Context hygiene rules require. research/lessons.md has the same fault: 'release6781', 'from102.753px to36px(J)', 'passes54', 'Python3.12', and 'JetPack7'. The next session gets broken commands from the file that exists to resume work.
  Recommendation: Add the missing spaces between words and numbers in STATE.md and research/lessons.md. Put the next command in backticks exactly as a session would run it. Then grep for `[a-z][0-9]` to catch the rest.
- [medium] DECISIONS.md D140–D147 entries are compressed into unreadable text (DECISIONS.md:662-868)
  The new entries run words together, for example 'atmostone extraEdgequery and threecropperssecond', 'Withholdunfinishedsame-personsource', and 'Sdefaultselection remainsnexttask'. D143 alone has nine sub-entries. The D147 entries on lines 817–868 are not committed yet, but 'measured continuation', 'counsel', 'fixed comparison', 'pixel counsel', and 'clean camera fixture' have the same fault. Future sessions must read linked decisions before reopening an approach. For D140–D147, the decision log is now the hardest file in the repo to read, which works against the hygiene goal.
  Recommendation: Restore normal spacing in the uncommitted D147 entries before the commit. The committed D140–D146 entries can get a spacing-only correction with no content change, because append-only covers decisions, not typography. If that is not allowed, add one plain index to the D147 acceptance entry: the outcome of each of D140–D146 in one sentence, plus its evidence path.
- [medium] No recorded test run covers the main.py and test_things.py changes in this commit (bench/results/2026-10-10-d147-box-continuity.json:9-47)
  Compared with HEAD 47f6eff, this commit adds face-outline smoothing (`_face_outline`), admission and drawing resets in `_track`, and about 130 lines in test_things.py. The D147 audit records only the 54 test_focus runs on the Mac and the Jetson, and `required_commit_hook` is 'Pending'. It lists 'face and voice code' as unchanged, but that is true only against the private 6781 baseline. Against git history, the commit changes face drawing. Counsel 54509 said face sequences were needed before any new face filter. lessons.md line 20 repeats the claim that main and face code are byte-identical, which is misleading to anyone diffing from HEAD or 30639f5.
  Recommendation: Run the real pre-commit hook, which runs the full suite including test_things.py. Record its result, elapsed time, and the commit SHA in the audit and in STATE.md. Add a delta-against-HEAD note that names the face-outline smoothing and drawing admission, and qualify the 'unchanged' list as relative to 6781.
- [low] The cleanup broke the pointer to the 3080 WSL box access details (research/lessons.md:51-63)
  boxes/3080/README.md line 3 says the lead reaches the box with the address recorded in 'STATE.md, research/lessons.md, Machines'. The rewritten STATE.md and lessons.md no longer contain that address or a Machines section. It survives only in the 104 KB archive and in an old DECISIONS entry (X1). CLAUDE.md requires lessons.md to log machine access and setup.
  Recommendation: Add one bullet to the 'Machine and environment pitfalls' section of lessons.md with the box SSH target, the gpu.lock path, and the warning to leave Docker and Ollama untouched. Alternatively, update boxes/3080/README.md to point to the archive.
- [low] Main files link to evidence that is untracked or absent from this branch (STATE.md:40-42)
  STATE.md, lessons.md, and DECISIONS.md link to research/archive/lessons-2026-10-10.md and reviews/20261010-093839-99667-review.md. Both files are still untracked. STATE.md and lessons.md also cite bench/results/2026-10-10-wsl-checkpoint-validation.json, which exists only in the root worktree and is not on this branch. A partial `git add` would leave broken links. Another clone could not reach the WSL validation evidence at all.
  Recommendation: Stage research/archive/ and the 99667 review with the commit. Either commit the WSL validation JSON on this branch or label it in STATE.md and lessons.md as a root-worktree-only file with its full path.

Next steps:
- Fix the glued tokens in STATE.md and lessons.md, and write the next step as an exact runnable command.
- Rewrite the uncommitted D147 entries in DECISIONS.md in plain text, and add a readable D140–D146 outcome index.
- Run the real tools/githooks pre-commit hook and record the full-suite result (test_things.py included) and the commit SHA in the D147 audit and STATE.md.
- Restore the 3080 box access line in lessons.md, and stage research/archive/ and reviews/20261010-093839-99667-review.md.
- Optional: booth-ux.md and mac-audio-interface.md repeat the Ignore, Restore, and recognition paragraphs almost word for word. Keep the behavior in one file and link to it from the other so they cannot drift. The new README status paragraph also belongs in STATE.md.
