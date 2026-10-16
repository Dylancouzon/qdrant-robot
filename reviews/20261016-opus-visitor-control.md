# Claude Code Review

Target: branch diff against 45f618a4cf21228ba04dc46deadb7c156393f684

I am reading the diff for `robot/main.py` and `robot/head.py`, and next I will check how `face_track`, `self.face`, and `session_id` are used.I confirmed one bug in the inspection error path. Now I am checking whether the new view reset in `_track` can leave `focus` as `None` before it is rebuilt.I found a likely selection-order bug in `robot/attention.py`. Next I am reading the servo helper, since it can drive real hardware.I found two bugs to fix before merge, and one behavior change for Dylan to decide on. The head controller, the servo helper, and the cleanup and cancellation code look sound. I did not run the tests, because the review was read-only.

## Fix before merge

**1. An introduction can select the wrong person** (`robot/attention.py:42-47`)
- `choose()` selects the sole unknown face before it checks whether the introduced name matches a recognized face.
- Example: enrolled Dylan stands beside a stranger and says "I'm Dylan." The stranger becomes the active visitor and gets the told name "Dylan".
- After that, Dylan's "This is my phone" goes to the stranger's owner ID, and the head follows the stranger.
- `name_in` also matches "I'm Italian" or "I am French" (any capitalized word after "I am"). Before this branch, those false matches had no effect. Now they switch the speaker to the stranger.
- Fix: check name matches among recognized faces first, then fall back to the sole unknown face. The `test_attention.py` scenario still passes with this order, because "Sam" matches no enrolled person.

**2. The inspection error "no camera image" gets overwritten** (`robot/main.py:1384-1387` with `1093`)
- When `shot[0]` is None, `_inspect` sets `selection_error` and returns before it resolves the visitor.
- `_answer_turn` then calls `_resolve_visitor`, and `_whois` sets `turn.selection_error = error` unconditionally. This usually clears the error.
- Result: the brain answers "What is on your left?" from the center frame and never moves the head.
- Fix: resolve the visitor before the None check, or keep the error if `_whois` already has one.

## Decide before the physical adapter

**3. The active visitor never expires** (`robot/attention.py:48-53`, `robot/main.py:1739-1742`)
- `self.face` changes only in `_converse` and in reset. The new checks reject exactly the cases where `_converse` used to start a new conversation (D60).
- After the first visitor leaves, a new visitor alone gets "Please introduce yourself" for every question. The same happens to a visitor whose face is not detected after `CONVERSATION_S`, because they get `NOT_YOU`.
- Two unknown faces block each other. An introduction gets "one at a time", and a plain question gets "introduce yourself". Only one person leaving the view ends this. At a booth, one bystander face in view is enough to cause it.
- `research/servo.md` says that selection persists through new arrivals. It does not say that selection persists after the active visitor leaves.
- I recommend that the selection expire after `CONVERSATION_S` with no matching face, which restores the old new-conversation path.

**4. A small hold can reset the whole view on real hardware** (`robot/head.py:110-122`)
- `hold()` sets the goal to the measured angle. If that differs from `sent` by any amount, the head sends a move, sets `moving`, and increases `view`.
- `_head_view` then clears object tracks, `views`, offers, `ready`, and `session_id`.
- The simulated motor reaches its exact target, so tests do not show this. A real encoder reads in steps of about 0.088°, so the readback rarely equals the commanded float.
- On hardware, every turn start and every preview without a recognized face can reset the view. "This is my phone" then answers "I lost sight of it", and sightings stop.
- Fix: skip moves smaller than the encoder step, or do not count them as a view change.

**5. Recall drops all sightings from other head angles** (`robot/main.py:2383`)
- `_same_view` makes sense in `_sighted`, which compares regions. `_recall` does not use regions.
- One following correction of 3° removes every earlier sighting from "what did you see?" answers.
- I think the filter prevents "it is not in view now" for an object that is still visible under a new track. Filtering by the labels in the current view does that without losing the other memories.

## Low

- **A delayed head command can override a later Stop** (`robot/main.py:1330`). If the wake check fails when the line is heard but passes when the turn runs, `_motion_request` issues a newer generation. A Stop spoken between those two moments is then overridden. The Stop turn says "Stopped." but does not request a stop again.
- **Unused code:**
  - `people.face()` has no production caller.
  - `located_face` is called only by `test_people.py`.
  - The `frame` parameter of `_enroll` is now unused.
  - The `shot[0] is not None` test at `main.py:1385` repeats the check before it.
  - `test_things.py:1580-1581` sets the same `monkeypatch` line twice.
- **Face embedding cost:** `located_faces` now embeds every face of at least `MIN_FACE` on each preview, one at a time. With groups, this cost grows with the face count, against the 15 fps detection target. I saw no measurement with more than two faces.

## Checked with no findings

- **`tools/servo.py`:** it limits writes to RAM registers, checks limits and supply, uses 20% torque, and turns torque off in `finally`.
- **Lock order:** it is always `detecting` first, then the head lock, and I found no reverse path.
- **Turn cleanup:** `finish()` in `finally` always clears `paused`.
- **Rejected selections:** they write no history, no told statements, and no prompt.
- **Head limits:** every path clamps or rejects goals outside ±70°.
- **Stop control:** `/stop_head` checks the session token and cookie.
