# Knowledge snapshot

[facts.jsonl](facts.jsonl) contains curated facts and their question phrasings. [build.py](build.py) builds [knowledge.snapshot](knowledge.snapshot) through a Qdrant server. The robot restores that snapshot into its in-process Edge knowledge shard on startup.

[robot/knowledge.py](../robot/knowledge.py) owns retrieval. The pinned text embedding model is in [models.json](../models.json). Visitor speech never writes to this shard. [Qdrant Edge guidance](../research/qdrant-edge.md) documents the schema and supported primitives.
