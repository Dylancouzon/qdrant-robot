"""The knowledge shard: facts restored from a Qdrant server snapshot into Qdrant Edge on every
start, searched by comparing the visitor's question with each fact's question phrasings (MaxSim).
"""
import shutil
from pathlib import Path

import numpy as np
from qdrant_edge import EdgeShard, Query, QueryRequest

from robot.config import ROOT, SHARED

SNAPSHOT = ROOT / "knowledge/knowledge.snapshot"
# Below this cosine the best phrasing is not the visitor's question. Provisional: calibrate on
# eval/dev knowledge and off-topic questions (M1.4).
MIN_SCORE = 0.75


class Knowledge:
    def __init__(self, path: Path = SHARED / "memory/knowledge"):
        # Restored fresh each start: nothing the robot hears is ever written here.
        shutil.rmtree(path, ignore_errors=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        EdgeShard.unpack_snapshot(str(SNAPSHOT), str(path))
        self.shard = EdgeShard.load(str(path))

    def search(self, query: np.ndarray, limit: int = 2) -> list[tuple[float, str]]:
        """(score, fact) for the facts whose phrasings match a unit-length query vector."""
        hits = self.shard.query(QueryRequest(
            limit=limit, query=Query.Nearest([query.tolist()], using="questions"),
            with_payload=True, score_threshold=MIN_SCORE))
        return [(h.score, h.payload["fact"]) for h in hits]


if __name__ == "__main__":
    import tempfile
    import time

    from robot.text_embed import TextEmbedder
    embed = TextEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        k = Knowledge(Path(tmp) / "knowledge")
        q = embed(["what exactly is qdrant edge", "how is the weather today"])
        t = time.perf_counter()
        hit = k.search(q[0])
        ms = (time.perf_counter() - t) * 1000
        assert hit and "embedded" in hit[0][1], hit
        assert not k.search(q[1]), "off-topic questions must find nothing"
        print(f"selftest ok: {hit[0][0]:.3f} {hit[0][1][:50]}... ({ms:.2f} ms)")
