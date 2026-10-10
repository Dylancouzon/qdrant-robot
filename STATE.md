# State

Updated 2026-10-10. Dylan accepted the final D147 live preview as "Good enough". Detection work stops at this checkpoint. Repository hygiene and the requested Claude Code Opus review are complete. Keep the accepted runtime; detector, filter, and model proposals remain parked.

## Start here

Worktree: `/Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface`, branch `spike/mac-audio-interface`. The root worktree holds private recordings and the shared Python environment. Read [CLAUDE.md](CLAUDE.md), [current lessons](research/lessons.md), and [Mac interface behavior](research/mac-audio-interface.md). Historical details remain in [DECISIONS.md](DECISIONS.md) and the [lessons archive](research/archive/lessons-2026-10-10.md).

The overnight detection session starts after reviewed D139 handoff `30639f5` (2026-10-10 01:47 EDT). Opus compares that base with the final tree, including D140-D147. D147's final one-condition change also has an exact accepted-live baseline in ignored `build/d147/accepted-live-baseline/robot`.

## Accepted runtime

Jetson release `7f67670fa91e`; rollback `6781adbb7189` is retained. Default detector is YOLOE-26s, TensorRT FP16, 384x640, with the fixed 50-word vocabulary. Nano artifacts and release fallback remain. All models and Qdrant Edge 0.8 run on the Jetson.

Known object names retain bounded continuity. Object points hold at most three explicitly verified diverse vectors. Preferred weak matches reuse one crop vector for at most one global query. Item Ignore uses negative example multivectors; actual queried misses release a retained preference on the third. Restore uses the existing serial recognition owner. Source/session/gallery/track guards still protect actions, writes, identity, and deletion.

Drawing compares consecutive raw positions for large-motion resets and smooths face geometry only on adjacent verified sources. Final `???` styling keeps the selected source-admitted box through matched confidence dips. Raw geometry and eligibility still govern teaching, crops, and writes. Real detection loss and expired size grace can briefly hide a box; these are accepted limits.

The broader undeployed D147 face/name step and rejected median, Kalman, gated-Kalman, and optical-flow experiments are retained privately under ignored `build/d147`. They add no runtime code. Do not reopen them unchanged.

## Validation and evidence

- [D147 final audit](bench/results/2026-10-10-d147-box-continuity.json): 54 Focus tests pass on Mac and Jetson; final physical preview accepted by Dylan. [Sol task review](reviews/20261010-093839-99667-review.md) PASS in 247.30 s, native exit 0. Main and face/voice code match live baseline `6781adbb7189`; the final unknown change is one display condition. Against Git HEAD `47f6eff`, D147 also includes face-outline smoothing, drawing admission, and tests.
- First D147 received-video comparison reduces the artificial phone step from 102.753 px to 36 px (J). Baseline and candidate native exit 1 receipts remain failures, with 10/12 and 11/12 original checks. Private `build/d147/{baseline,candidate,live-candidate}` keeps actual JPEG bytes, offsets, hashes, and tegra.
- [D143 face delivery](bench/results/2026-10-10-d143-face-delivery.json), [D144 false-claim guard](bench/results/2026-10-10-d144-phone-recovery.json), [D145 Ignore/Restore](bench/results/2026-10-10-d145-ignore-continuity.json), and [D146 detector default](bench/results/2026-10-10-d146-detector-default.json) keep their bounded outcomes and failures.
- [External cup audit](bench/results/2026-10-10-d145-external-cup.json): changed viewpoints reached 121/164, or 73.78% (J), an open descriptor gap. This is development evidence, not held-out acceptance.

Final runtime SHA256: Focus `fa2e9f3ff548996e6223e5907b94eacf487858b0df5fb9f7125e6d4014fb7e77`; main `e086da9710d2ba9b0838b4b12aa8f9a00dac09f6ff5de23ea7bb8e045198f4e7`. Both match the deployed release. Final physical acceptance does not qualify perfect stability, broad false-positive safety, sustained 15 fps, or no paging.

## Running output and machine ownership

One live preview remains for Dylan: Mac PID 1311 (uv PID 1309), local execution session 78044, `tools/talk.py --release 7f67670fa91e --port 8765`, log `build/d147/final-preview.log`. Original Chrome tab 1202942045 is Listening with microphone capture active. Stop in that page releases its owned session; Ctrl-C stops the local server.

Jetson live unit `qr-live-mac-0c66822ccc30`, PID 429443, invocation `5bb152dc80264e70a4501371d305301f`, start 09:40:03 EDT. Its command runs `robot.main --listen 7070` through the existing GPU lock and tegra workflow. Do not open a second MJPEG subscriber. Screenshot `build/d147/final-preview-ready.jpg` proves readiness only.

Jetson alias `robot`, boot `09b4bb27-f975-441c-9d00-7af446ec7de6`. Last checked disk headroom 101 GB (J). Owned `caffeinate -dimsu` PID 65618 remains for the live preview; unrelated PID 36781 stays untouched. Previous sessions, models, memories, and closed backup `shared/backups/2026-10-10-before-d140.tar.gz` remain. Backup SHA256 `bf4ff898131cad2ae1ac0b5af1fc2a40061d3f07ece8f40c42f91a3bc0b267f1`.

All D147 diagnostic/test units have ended. The final Jetson Focus unit exited 0 (54 tests in 0.46 s); its tegra is collected. The clean 202-frame camera fixture and all 348,211,638 bytes verify locally, but PNG encoding gave 6.73 fps (J) and establishes no integrated performance result. No new runtime inference job is needed for documentation cleanup.

## Separate WSL work

The other session completed checkpoint validation and packaging. [WSL status](bench/results/2026-10-09-wsl-d136-status.json) preserves original quantizer native exit as unavailable. Its 17 private evidence files are independently checked against recorded sizes/hashes. Later validation and packaging preserve native exit 0; loading, answers, and Jetson fit remain unverified.

Root-worktree-only evidence: `/Users/dylanc/Documents/GitHub/qdrant-robot/bench/results/2026-10-10-wsl-checkpoint-validation.json`. Private validation logs and the transfer archive remain under that root worktree's ignored `build/p2`. Archive size is 8,437,452,800 bytes (E); SHA256 `aaf6b5170b427700b048e969d052e0cd8d40a11068e87782e35936c9974c4697`. D117 accepts direct checkpoints; another ONNX export or repeated quantization is unnecessary. The completed-job watcher was removed after preserving 27 historical records. Leave Docker/Ollama and other GPU locks untouched.

## Git and review checkpoint

Accepted product and cleanup commit `69e0101` follows the D140-D146 commits through `47f6eff`. Final D147 product changes are Focus/main/test_focus/test_things; documentation cleanup covers README, CLAUDE, STATE, lessons/archive, Mac interface, booth guide, decisions, audits, and reviews. Preserve all WSL owner content and include its validated whole-file metadata so the worktree can finish clean.

Repo standing approval permits commit and push after review and the real `tools/githooks` pre-commit hook. No main merge. Stage whole reconciled files; partial staging breaks gate index cleanup.

[Initial Opus review](reviews/20261010-opus-session-hygiene.md) and [final Opus verification](reviews/20261010-opus-session-hygiene-final.md) preserve both verdicts. Final verdict: approve, native exit 0. Opus verified all five findings were repaired, with no runtime, secret, or scope blocker. Historical decision spacing remains preserved; use the readable lessons index.

The real commit hook passed on `69e0101`: 90.77 s checks, including the full pytest suite in 88.44 s, native exit 0. The receipt is in the D147 audit; private log is `build/d147/final-commit-hook.log`. Its nonblocking stamp reminder reflects only README, CLAUDE, and 3080 README changes since the Sol review. All four recorded source hashes, two runtime and two test files, match the reviewed and deployed source.

No review or experiment remains active. Final bookkeeping records the approval and parked proposals; current Git history identifies that documentation commit. Next session command: `git status --short --branch`, from this worktree. Read D148 before discussing the parked object gaps; keep live `7f67670fa91e` and rollback `6781adbb7189` unchanged.

## Parked for the next session

[Known object gaps](research/edge-cases.md#next-session-object-recognition-discussion), D148: two same-name items can lose both labels, and rectangular recognition crops retain background. Discuss labeler ownership, shared names within one owner, and measured background isolation next time. These proposals authorize no implementation during this accepted checkpoint.

## Targets that remain open

Physical audible 1.2 s p50/2.0 s p95, 90% per capability with zero stranger identity claims, 30 tok/s decode, sustained 15 fps while talking, Edge 10 ms p99 at acceptance scale, minimum 500 MB headroom, and no turn paging remain unqualified. M4 also needs offline cold start, restart/deletion, held-out acceptance, and an eight-hour active run. The user chose this detection stopping point; these targets do not authorize more work in this session.
