# Evaluation map

[run.py](run.py) owns acceptance from deployment through replay, collection, judging, and speech checks. Read the [evaluation rules](../research/workflow.md#evaluation) before a run. Every held-out use requires a decision entry.

| Area | Contents |
| --- | --- |
| [dev](dev/) | Development sessions, conversation, transfer, visual recall, people, and wake fixtures. |
| [heldout](heldout/) | Frozen acceptance sessions, images, synthetic speech, and recorded speech. |
| [probes](probes/README.md) | Exploratory fixtures kept separate from acceptance. |
| [replay.py](replay.py) | Run scripted fixture steps through the robot. |
| [judge.py](judge.py) | Grade answers with three votes and cached judgments. |
| [speech.py](speech.py) | Fetch generated speech and independently check its content. |
| [wake.py](wake.py) | Check wake-phrase development speech. |
| [make_scenes.py](make_scenes.py), [make_faces.py](make_faces.py), [make_wavs.py](make_wavs.py) | Prepare source scenes and synthetic speech. |
| [test_fixtures.py](test_fixtures.py), [test_replay.py](test_replay.py), [test_judge.py](test_judge.py), [test_run.py](test_run.py) | Check fixture integrity and evaluation orchestration without model calls. |

Image attribution stays beside each split: [development](dev/images/SOURCES.md), [held-out](heldout/images/SOURCES.md), and [probes](probes/images/SOURCES.md). Private team-photo composites remain ignored under `eval/faces/`.

Judged correctness, keyword matches, expected evidence, and speech checks measure different things. Read [saved measurements](../bench/results/README.md) and [current gaps](../research/edge-cases.md) before interpreting scores. This cleanup runs no held-out fixtures.
