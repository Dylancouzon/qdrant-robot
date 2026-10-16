# Qdrant Edge in the robot

The project pins `qdrant-edge-py` 0.8.0. Verify capabilities against that installation's `qdrant_edge/__init__.pyi`, rather than current upstream `master`. Dependencies and model artifacts stay pinned in [pyproject.toml](../pyproject.toml), [uv.lock](../uv.lock), and [models.json](../models.json).

| Shard | Stored evidence | Runtime owner |
| --- | --- | --- |
| `knowledge` | Curated facts with question phrasings as a multivector. Recreated from the shipped snapshot on startup. | [knowledge.py](../robot/knowledge.py) |
| `seen` | Visitor text, selected visual sources, captions, and named-object sightings. | [memory.py](../robot/memory.py) |
| `things` | Owner-scoped named objects with crop multivectors, saved views, visitor records, and Ignore rules. | [things.py](../robot/things.py) |
| `people` | Consented face shots with visitor links. | [people.py](../robot/people.py) |

The Edge shards stay inside the robot process. All inference runs on the Jetson. Embeddings come from the robot's pinned models. Face enrollment needs explicit consent. Forgetting deletes linked points and source files. [Objects](objects.md), [faces](faces.md), and [recall](recall.md) define each flow.

## Reading and updates

Similarity search uses `QueryRequest` with `Query.Nearest`. Ordered queries use indexed payload times. Metadata reads use `scroll`, `retrieve`, and `count`, with selected payload fields and vectors disabled. MaxSim combines multiple question phrasings, crop views, or face shots within a point. The [memory-map guide](mac-audio-interface.md#what-the-page-shows) describes bounded UI reads.

Version 0.8.0 also exposes `Fusion.Rrf` and `Fusion.Dbsf` for prefetch fusion. The robot's current query paths do not require a new fusion layer. Check installed stubs before introducing a primitive. The [official reading API](https://qdrant.tech/documentation/edge/edge-api/reading-data/) explains request mechanics.

[tools/jetson.py](../tools/jetson.py) owns deployment and collection. Keep closed-shard backups and rollback releases. The [historical SDK survey](archive/edge-sdk-notes-2026-10-07.md) preserves earlier capability comparisons and issue notes; it does not establish current upstream release status.
