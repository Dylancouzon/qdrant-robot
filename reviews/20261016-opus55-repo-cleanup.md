# Opus 5.5 repository cleanup review

Requested model: `claude-opus-5-5`. Command: Claude Code companion `review --scope working-tree --model claude-opus-5-5`.

## Original review output

# Claude Code Review

Target: working tree diff

I'm checking whether the imports the bench scripts now use (`MODEL` and `MODELS`) exist in the robot modules.I'm verifying the new Qdrant Edge doc claims against the robot code, then I'll write up the review.**Verdict: safe to commit after two small fixes.** No code defects. The four bench edits import names that exist: `MODEL` at `robot/things.py:38` and `MODELS` at `robot/config.py:8`. The diff otherwise only moves and re-indexes documents. I could not run `tools/gate.py checks` because shell commands were denied in this session.

## What I checked

- **Anchors:** every new or kept link target exists. This covers `edge-cases.md#next-steps`, `objects.md#owners`, `mac-audio-interface.md#what-the-page-shows`, `experiment-ledger.md#evaluation-pitfalls`, and all four section links into `edge-case-records-2026-10-15.md`.
- **Moved archive files:** their relative links now go up one more level (`../`, `../../`) and resolve. The `gates/*.md` files, the research pages, and the D141 to D147 result files all exist locally.
- **Archive index:** the new file list in `research/archive/README.md` matches the directory exactly, with 31 files.
- **`research/qdrant-edge.md` claims:** the code confirms them. Knowledge restores from the snapshot (`knowledge.py:28`). Search uses `Query.Nearest`, and metadata reads use `scroll`, `retrieve`, and `count`.
- **Records:** the README results command points to a file that exists. D174 is consistent with `architecture.md` and STATE.md.

## Findings

1. **Medium, likely broken links.** Ten new GitHub links pin `6933803bcaf0…`. That SHA is the annotated tag object for `archive/2026-10-10/pre-cleanup`, not a commit. GitHub blob URLs normally take a commit SHA or a ref name, so these links can return 404. Use the commit `9751bb69b2f6…` or the tag name. The links are in `research/archive/experiments.md`, `gemma-fit.md`, `jetson-trt.md`, and `lessons-index-2026-10-10.md`.

2. **Low, stale text.** `research/archive/lessons-index-2026-10-10.md:3` still says "Relative links resolve from that former location". The diff rewrote those links to resolve from the archive, so the sentence is now false. Further down, the validation JSON is still described as existing "only in the root worktree at that absolute path", but its link now points to GitHub.

3. **Low, process drift.** STATE.md renamed "Next command" to "Next step" and no longer gives a command. `CLAUDE.md:14` and `research/workflow.md:47` still say STATE.md contains the next command. Put a command back, or update the rule in both files.

4. **Nit, leftover name.** `bench/same_pairs.py:26` still imports `MODEL as DINOV2`, but the encoder is DINOv3 and the docstring now says "configured crop vectors". Rename the alias to something like `ENCODER`.

5. **Nit, result rows.** `bench/crop_cost.py:76` now records `dinov3-small/model.onnx` and no longer says "fp32, 224x224". Old and new rows use different formats for the `model` field. That is acceptable, because `bench/README.md` already warns that old crop-cost records name DINOv2.

6. **Nit, repeated text.** Lines 3 and 5 of `research/archive/edge-case-records-2026-10-15.md` both point to the archive tags. Delete line 5.

The README dropped most of the detail on how `tools/results.py` reads results, such as run-ID ordering and what `complete` means. Short versions remain in `workflow.md:64` and the tool's `--help`, which is acceptable under the lean-records rule.

## Lead resolutions

The archive URLs now use the peeled commit SHA, verified as a commit with every referenced artifact present. Archive wording matches the repaired navigation. STATE.md includes a concrete starting command. The remaining encoder alias is `ENCODER`. Duplicate archive guidance is removed. Historical result formats and verdicts remain intact. The main session runs the required checks because the read-only reviewer could not run shell commands.

The final project task review passed after these fixes. The required pre-commit hook validates the complete staged change before commit.

## Validation follow-up

The initial commit hook passed 399 tests and failed the existing actual-stream timing case `test_completion_phase_and_encoding_margin_on_actual_stream[0.075-15]`. Its maximum received hold was 222.11 ms against the unchanged 200 ms limit (E). The stream implementation and test have no cleanup diff. The isolated strict rerun passed in 1.70 s without changes. The full hook is rerun before commit. Raw logs remain in `build/repo-cleanup/`.
