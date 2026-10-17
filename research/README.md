# Project topic index

The architecture is settled. Open the relevant row for the active task. Trial outcomes and rejected approaches stay in the ledger; current behavior stays in topic files.

| Topic | Read |
| --- | --- |
| Architecture and component overview | [Architecture](architecture.md) |
| Operating rules, reviews, evaluation, deployment, and recovery | [Workflow](workflow.md) |
| Previous experiments and failure pitfalls | [Lessons index](lessons.md) |
| Servo work, parked tasks, and known gaps | [Remaining work](edge-cases.md#next-steps) |
| Enclosure, printing, and assembly | [Enclosure](../hardware/enclosure/README.md), [trial history](experiment-ledger.md#enclosure) |
| Shared active visitor and bounded head movement | [Head control](servo.md) |
| Conversation memory, exact regressions, next steps, and fixtures | [Conversation](conversation.md) |
| Monitor, audio controls, and session lifecycle | [Robot interface](mac-audio-interface.md) |
| Focus, overlays, and visitor interaction | [Booth behavior](booth-ux.md) |
| Detector models and preprocessing | [Detector](detector.md) |
| Named objects and crop vectors | [Objects](objects.md) |
| Same-object answers | [Same-object comparison](same-object.md) |
| Recall and conversation evidence | [Recall](recall.md) |
| Consent, face matching, and identity | [Faces](faces.md) |
| Edge shards and queries | [Qdrant Edge](qdrant-edge.md) |
| CUDA, runtimes, memory, and speech costs | [Software stack](stack.md) |
| Wake phrases | [Wake word](wakeword.md) |
| Implemented ownership and parked location proposal | [Owner and location](owner-location.md) |
| Binding decisions | [Decisions](../DECISIONS.md); search by ID before opening entries |
| Saved verdicts and measurements | [Reviews](../reviews/), [results](../bench/results/); use tools/results.py for summaries |
| Superseded plans and older history | [Archive index](archive/README.md) |

Completed conversation experiments are in the [dated trial report](archive/conversation-trials-2026-10-15.md). The archive index also lists their rejected patches and base commits.

Source and artifact directories have their own indexes in the [repository map](../README.md#repository-map). Dated [interface checks](archive/interface-checks-2026-10-16.md) and [edge-case records](archive/edge-case-records-2026-10-15.md) preserve detail outside current guidance.

Mounted calibration and speed trials are in [the dated report](archive/mounted-servo-trials-2026-10-16.md). [The evidence manifest](archive/mounted-servo-evidence-2026-10-16.json) locates complete raw traces; current result files retain outcomes and summaries.
