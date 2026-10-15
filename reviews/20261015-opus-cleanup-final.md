# Cleanup review

Requested model: `claude-opus-5-5`.


Target: working tree diff

I am checking the remaining test wiring with read-only search, because Bash is blocked in this mode.I found no blocking defect, so you can commit after one fix to the records. I could not run the tests, because Bash is blocked in this mode. I checked each claim by reading the code.

## Verified

- **`eval/run.py` result handoff:** The run now names its own result file, so it cannot pick up an old run's file.
  - `replay_rows` requires exactly one complete `replay` summary, an exact match of the spoken-step IDs, and the same fixture file.
  - `by_id` rejects duplicate IDs.
  - `replay.py` writes `"cases": str(path)` as a relative path. `ROOT / recorded` resolves that path back to the same file. `n_expected` counts the same `"say"` steps that `replay_rows` expects.
  - A failed collect returns 2. A failed replay prints its exit status before collection.
- **`replay.py --output`:** It accepts only a bare `.jsonl` filename. It checks the name before the replay starts, so a path cannot leave `shared/results`.
- **Persistent camera error:** All three readers now see the failure: `_heard_start`, `_watch`, and `_detect`.
  - In `--camera-file` mode, the main loop at `robot/main.py:2214-2216` raises when `hear()` raises or when `detect_failed` is set. The process exits.
  - The new text in `research/edge-cases.md` says that recorded-camera qualification "stops", and that is correct.
  - `show()` clears the error, and the test covers the case where another reader gets the error first.
- **Settings write failure:** On an `OSError`, `Settings.change` removes the temporary file in `finally` (`robot/settings.py:74-75`) and keeps the active values. The new test reaches this path through `_control`.
- **`pyproject.toml` `testpaths`:** It covers every `test_*.py` file in `robot/`, `eval/`, and `tools/`. `bench/` has no tests. `tools/gate.py checks` passes explicit file lists, so this setting affects only a bare `pytest` run.
- **Docs:** No stale "at most three views" or "20 seconds" text remains outside `DECISIONS.md`. `DECISIONS.md` is append-only, so its old D64 entry can stay.

## Fix before commit

1. **`STATE.md` will be false at commit time.** It describes a running `qr-replay` job and a local fix that is not deployed yet. The replay runs on `94a07aadc5dc`, and that release does not include the final camera-reader fix. The fix changes only error paths, so the replay is still good evidence for normal turns. However, the release you commit will have a different hash. Rewrite `STATE.md` after you collect the replay, and name the release the replay ran on.

## Minor

2. **`research/edge-cases.md:72`** still lists "Saving settings fails" as an open edge case. This diff fixes it, so remove or update that row. The file-source section and the mute line were updated correctly.
3. **The review files will not satisfy the review check.** `tools/gate.py` looks for files named `*-review.md` that start with a tree stamp. `20261015-opus-cleanup-*.md` has neither, so the pre-commit hook will remind you about a missing review. This is acceptable because Dylan chose Opus reviews for this task, and the reminder does not block the commit (D17).
4. **`eval/run.py:72` can report the wrong cause.** If a fixture `"say"` step has no `"id"`, `by_id` raises `KeyError`. The script then prints "invalid replay result", but the defect is in the fixture. Current fixtures always have IDs, so I recommend no change now.

`result.json` stays untracked, as Dylan asked. Stage only the listed paths.


Lead response: Final STATE is written after collection and deployment. The resolved settings-failure backlog row is removed. The repository Codex task gate runs separately. The pre-existing slicer file stays untouched.
