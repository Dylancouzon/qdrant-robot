# Cleanup review

Requested model: `claude-opus-5-5`. Job: `review-mv9znfli-hmti7x`.

Checking the remaining callers and test imports, then I will write the review.**Verdict: fix one issue before you commit.** The `eval/run.py` and settings changes are correct. The camera-failure fix only works when the detection thread reads the failed frame first.

I could not run the tests because Bash is blocked in this mode. I checked the changes by reading the code.

## Blocking

**1. Any of three threads can receive the camera decode error, and only one of them handles it** (`robot/main.py:431`, `robot/camera.py:101-119`)

- `FileCamera.latest()` releases the capture and raises only once. After that, every call returns the last good frame with no error.
- Three threads call `latest()`: the speech-start handler (`main.py:388`), `_watch` (`main.py:420`), and `_detect` (`main.py:431`). Only `_detect` catches the error and sets `detect_failed`.
- **Failure case:** `_watch` calls `latest()` first when the frame fails to decode. The error kills the `_watch` thread. `_detect` then gets the frozen frame forever, so `detect_failed` stays `None`. The check at `main.py:2215` passes, and the replay scores answers made from a frozen frame.
- If the speech-start handler reads the failure first, that thread dies, and the robot stops taking turns.
- The new test calls `_detect()` alone, so it does not catch this.
- **Fix:** make the failure stay set in `FileCamera`. Store the error and raise it again on every `latest()` call. Then every caller sees the failure, and `_detect` reports it. Add a test that calls `latest()` once from another caller first, then runs `_detect`.

## Remove before commit

**2. `result.json`** is untracked output from a 3D-printer slicer ("The input model file to the slicer can not be parsed"). It is not part of this change. Delete it or add it to `.gitignore`.

## Checked, no action

- **`eval/run.py`:** The run now names its own result file, so it can no longer pick up an old one. A failed collect now returns 2. `replay_rows` checks that:
  - the run is complete,
  - the step IDs exactly match the spoken steps (duplicates raise an error through `by_id`),
  - the fixture file is the same.
- **The fixture path check:** The Jetson stores the path relative to the repository, and `ROOT / recorded` resolves it back to the same file.
- **New result file names:** They match the `raw_paths` pattern and `run_order` in `tools/results.py`.
- **`eval/replay.py --output`:** Only a bare `.jsonl` filename passes, so the path cannot leave `shared/results`.
- **`_setting`:** If saving fails with `OSError`, the function returns `False`. `Settings.change` deletes the temporary file, and the active values stay the same. The new test covers this.
- **README:** The 300 s timeout matches `CHECK_TIMEOUT_S = 300` in `tools/gate.py:30`.
- **`talk.html`:** `return false` does not change behaviour, because `undefined` was already falsy at lines 198 and 203. `clearLive` disables the mute button and volume slider, and line 299 enables them again when `view_ready` is true.

Lead response: The camera failure is now retained for every source reader. The pre-existing slicer file `result.json` stays untouched, per Dylan.
