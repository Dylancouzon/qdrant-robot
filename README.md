# Qdrant Edge Robot

A robot that sees, listens, talks, and remembers on one Jetson Orin Nano Super 8 GB. Qdrant Edge stores and retrieves its observed evidence inside the robot process. The goal is stronger perception, sustained conversation, useful memory, and fluid interaction; targets are a floor (D76).

Start with [CLAUDE.md](CLAUDE.md), [STATE.md](STATE.md), and [research/lessons.md](research/lessons.md), which lists every avenue tried and its outcome. [DECISIONS.md](DECISIONS.md) holds the binding choices; older history is in [research/archive/](research/archive/).

The current brain is Qwen3-VL-2B with CUDA Kokoro. The active task is in [STATE.md](STATE.md). Controls and limits are in [Mac audio interface](research/mac-audio-interface.md) and [booth behavior](research/booth-ux.md).

Use the [servo control guide](hardware/SERVO.md) to check the STS3215 through its USB adapter and external 5 V supply.

## Read evidence without running models

```sh
python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6
python3 tools/results.py --machine box-rtx3080 --model qwen3vl-2b --limit 4
python3 tools/results.py bench/results/2026-10-09-replay-1791521394.jsonl
python3 tools/results.py --release e9be9e321232 --json
```

The reader supports raw replay and brain bake-off JSONL files and their existing `.judged.jsonl` sidecars. It imports no robot code and makes no network or judge calls. Output keeps each file and variant separate, including machine, release, model, cases, and input mode. Directory searches use those two filename families. The limit selects the latest Unix run IDs in filenames, independent of model names; files without those IDs sort first.

`judged` counts answer verdicts. `keyword` counts the replay's heuristic `ok` checks; raw summaries call this `correct`. `retrieval` counts expected-evidence checks. For example, D75's M2 run has 62/74 keyword passes and 44/74 judged passes. Partial or absent judging stays explicit; stale answers, duplicate IDs, and unsupported files produce errors.

`complete` means the result has a final summary and its recorded counts agree. It does not prove acceptance or held-out generalization. Older files lack an expected suite count; JSON output leaves `expected_n` unknown. Missing footers and count mismatches show `incomplete`. Full system prompts and turn details remain in the original evidence files.

Oracle replays submit fixture text. Synthetic and recorded-voice replays include speech input. Logged-prompt bake-offs isolate brain evidence use. Live interaction needs its own measurements. A synthesized first phrase does not measure physical audible latency. The 64-token, 2,048-context runs do not establish long-conversation quality or paging safety.

## Local checks and reviews

```sh
python3 tools/gate.py checks
python3 tools/gate.py review "Task scope, changed paths, and evidence"
```

Checks report stage timings and stop on failure or a 120 s stage timeout. Module assertions share one interpreter. Review gates remain bounded and read-only; a tree changed during review cannot receive its stamp. The pre-commit hook blocks only deterministic failures and reminds about missing reviews.

Deployment and remote acceptance use [tools/jetson.py](tools/jetson.py) and [eval/run.py](eval/run.py). Read STATE.md before starting remote work. Topic evidence is indexed in [research/lessons.md](research/lessons.md); raw runs live in `bench/results/`, and reviews live in `reviews/`.

## Use the robot interface

```sh
.venv/bin/python tools/talk.py --release RELEASE_ID
open http://127.0.0.1:8765
```

Select **Start** to attach to the robot unit `qr-robot` on the Jetson, or start it. The robot uses the Jetson's own USB microphone and speaker. Deploy this interface through `tools/jetson.py deploy`, then replace `RELEASE_ID` with its printed release ID. The interface requires SSH access to `robot`, no other Jetson job, and that exact current release. Start uses the existing `tools/jetson.py run` workflow. Deployment alone starts no models or microphone.

Wait for **Listening**, then say "Hey Edgy". Follow-up questions work for about 20 seconds after an answer. **Mute** silences the Jetson microphone. The slider sets the speaker volume. The robot ignores its microphone while it speaks, with a short tail to prevent echo. **Stop** stops the robot unit and closes the SSH tunnel. Closing the page, pressing Ctrl-C, or losing the tunnel leaves the robot running; Start attaches to it again. The page stays open for repeated use.

Page loads start no microphone capture. The Mac stores no audio. The Jetson retains its existing session logs and synthesized answer WAVs. All models and Qdrant Edge run on the Jetson.

The page shows the annotated Jetson camera, verified face outlines and enrolled-face names, named objects, one "???" teaching focus, current status, and up to eight exchanges. Edgy's text appears during generation. The evidence panel shows supplied knowledge, recalled statements, and memory IDs. It reports evidence supplied, rather than asserting that a generated reply used every fact correctly. Consent, naming, recall, and forgetting remain voice actions.

Camera and live state use the token-protected Jetson view on loopback port 8090, forwarded through an SSH tunnel that carries only the view. Start reads the running unit's view token, or creates one when it starts the unit. The launcher sends it through environment and SSH stdin, never command arguments. The local page proxies the feed with its own session cookie; the Jetson token stays off the page. Stop clears the live camera and conversation. UI history stays in RAM; the original MJPEG view route remains available to existing clients.

Visual memory keeps explicitly named objects. Say "Track this as my wallet" or "This is my phone" for the orange teaching focus. Each object keeps at most three diverse crop vectors through verified explicit reteaching. Skipped queries preserve associations; repeated weak results remove labels. Person names use their verified source frame. Unknown detections stay in RAM; ordinary conversation memories keep text without images. Select an eligible item and press **Do not track that** to persist negative example vectors without saving an image. **Restore** removes that preference. Source, size, and confidence checks still govern teaching and actions. Similar-looking items and changed viewpoints can limit recognition.

For bounded recorded-camera qualification, launch the same page with `tools/talk.py --release RELEASE_ID --camera-file /existing/jetson/fixture.avi`. The file starts after model warmup, in its stored orientation. The robot still listens through its USB microphone. The camera status identifies the recording. Stop and restart the server without `--camera-file` to return to live capture.
