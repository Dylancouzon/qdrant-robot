# Qdrant Edge Robot

Edgy sees, listens, talks, and remembers on one Jetson Orin Nano Super 8 GB. Qdrant Edge stores observed evidence inside the robot process. The current brain is Qwen3-VL-2B with CUDA Kokoro.

Read [CLAUDE.md](CLAUDE.md), [STATE.md](STATE.md), and the [lessons index](research/lessons.md) before work. [Research topics](research/README.md) explain current behavior. [Decisions](DECISIONS.md) preserve binding choices.

**Next step: Qualify loaded power and temperature feedback.** The assembled head has cleared ±60° travel at 40°/s, and Dylan reported good live motion. The mounted software temperature cutoff is 65°C. The [handoff](STATE.md#next-step) records current jobs and remaining qualification. Conversation experiments and broader acceptance remain parked.

## Run the interface

```sh
.venv/bin/python tools/talk.py --port 8766 --release RELEASE_ID
open http://127.0.0.1:8766
```

Use the deployed release in STATE.md. Select **Start**, wait for readiness, and say "Hey Edgy". The robot uses its own USB microphone and speaker. **Stop** stops the robot. Closing the page or launcher leaves it running. Use one camera viewer.

Live shows the camera, conversation, retrieved text and images, stored memory points, and measured turn timings. Memory manages saved object views. Settings controls recognition. Read the [interface guide](research/mac-audio-interface.md) for teaching, consent, forgetting, audio, authentication, and recorded-camera checks.

## Repository map

| Area | Index |
| --- | --- |
| Enclosure CAD, print projects, and assembly | [Enclosure](hardware/enclosure/README.md) |
| Servo wiring, calibration, and runtime startup | [Hardware guide](hardware/SERVO.md) |
| Runtime components and regression tests | [robot](robot/README.md) |
| Deployment, monitor, models, checks, and result tools | [tools](tools/README.md) |
| Acceptance, fixture splits, speech checks, and judging | [eval](eval/README.md) |
| Exploratory benchmarks | [bench](bench/README.md) |
| Saved measurements | [results](bench/results/README.md) |
| Review receipts | [reviews](reviews/README.md) |
| Knowledge snapshot and facts | [knowledge](knowledge/README.md) |
| Architecture, operating guidance, and known gaps | [research](research/README.md) |
| Superseded plans and completed experiments | [archive](research/archive/README.md) |
| Optional Claude roles | [builder](.claude/agents/builder.md), [researcher](.claude/agents/researcher.md) |
| Historical WSL mailbox | [3080 box](boxes/3080/README.md) |

Pinned artifacts are in [models.json](models.json). Python dependencies are in [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock). Formatting uses [ruff.toml](ruff.toml) and [.gitattributes](.gitattributes). [Ignored paths](.gitignore) keep private media, models, raw journals, and temporary work outside git.

## Checks and evidence

```sh
python3 tools/gate.py checks
python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6
python3 tools/results.py bench/results/2026-10-15-243f49ff-replay-1792095965.jsonl
```

Checks include Python regressions and the locked jsdom UI harness. The pre-commit hook runs them. Reviews and remote work follow the [workflow](research/workflow.md).

Result summaries distinguish judged answers, keyword matches, retrieval checks, and input modes. A complete run does not establish acceptance. Synthesized speech timing does not measure physical audible latency. Targets and unresolved acceptance work remain visible in STATE.md.
