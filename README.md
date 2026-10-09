# Qdrant Edge Robot

A robot that sees, listens, talks, and remembers on one Jetson Orin Nano Super 8 GB. Qdrant Edge stores and retrieves its observed evidence inside the robot process. The goal is stronger perception, sustained conversation, useful memory, and fluid interaction; targets are a floor (D76).

Start with [CLAUDE.md](CLAUDE.md), [STATE.md](STATE.md), and [research/lessons.md](research/lessons.md). Read the linked decisions before repeating an experiment. Current runtime choices and rejected alternatives are in those files; the reference architectures describe the starting point.

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
