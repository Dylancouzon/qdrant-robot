# Runtime map

Read [architecture](../research/architecture.md) first. All inference and Edge shards run on the Jetson. [STATE.md](../STATE.md) owns the deployed release.

| Responsibility | Source |
| --- | --- |
| Turn lifecycle, actions, evidence, worker ownership, and shutdown | [main.py](main.py) |
| Camera and file-source timestamps | [camera.py](camera.py) |
| Detection, tracking, focus, and drawing continuity | [detect.py](detect.py), [focus.py](focus.py) |
| Active visitor, bounded following, and calibrated USB servo | [attention.py](attention.py), [head.py](head.py), [servo.py](servo.py) |
| Face vectors, consent, and visitor identity | [faces.py](faces.py), [people.py](people.py) |
| Serialized crop and face model owner | [recognition.py](recognition.py) |
| Named objects, multivector views, and Ignore rules | [things.py](things.py) |
| Statements, sightings, source files, retention, and deletion | [memory.py](memory.py) |
| Immutable knowledge snapshot and text embeddings | [knowledge.py](knowledge.py), [text_embed.py](text_embed.py) |
| Prompt, generation, and request routing | [brain.py](brain.py), [route.py](route.py) |
| VAD, ASR, speech synthesis, and USB audio | [asr.py](asr.py), [tts.py](tts.py), [audio.py](audio.py) |
| Authenticated view, controls, and memory-map API | [view.py](view.py) |
| Shared paths and saved recognition settings | [config.py](config.py), [settings.py](settings.py) |

## Regression map

| Area | Tests |
| --- | --- |
| Naming, owners, teaching, recall, forgetting, map snapshots, and publication | [test_things.py](test_things.py) |
| Drawing and source authority | [test_focus.py](test_focus.py), [test_recognition.py](test_recognition.py) |
| Identity, observations, and comparisons | [test_people.py](test_people.py), [test_sightings.py](test_sightings.py), [test_same.py](test_same.py) |
| Speech, audio, and failures | [test_speak.py](test_speak.py), [test_audio.py](test_audio.py), [test_workers.py](test_workers.py) |
| Shared selection, movement, calibration, and motor failures | [test_attention.py](test_attention.py), [test_head.py](test_head.py), [test_servo.py](test_servo.py) |
| Camera and authenticated HTTP routes | [test_camera.py](test_camera.py), [test_view.py](test_view.py) |

Use `rg -n '^    def |^def test_' robot/main.py robot/test_things.py` to locate a focused section. These large integration files share lifecycle fixtures; split them when a concrete change needs separation. Browser DOM checks live in [tools/ui](../tools/README.md#ui-development).
