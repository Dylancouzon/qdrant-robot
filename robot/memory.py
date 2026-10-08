"""What the robot saw: one Edge point per observed frame, with its capture time, the JPEG on
disk as evidence, and a caption the VLM wrote from that frame in idle time. M1 recalls the
newest captioned frames; M2 adds SigLIP 2 image vectors and semantic search.
"""
import time
from pathlib import Path

import cv2
import numpy as np
from qdrant_edge import (
    Direction,
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    OrderBy,
    PayloadSchemaType,
    Point,
    QueryRequest,
    RangeFloat,
    UpdateOperation,
)

from robot.config import SHARED

IMAGE_DIM = 768  # the SigLIP 2 vector slot M2 fills; M1 points carry payload only


class Seen:
    def __init__(self, root: Path = SHARED / "memory"):
        self.frames = root / "frames"
        self.frames.mkdir(parents=True, exist_ok=True)
        path = root / "seen"
        if path.exists():
            self.shard = EdgeShard.load(str(path))
        else:
            path.mkdir()
            self.shard = EdgeShard.create(str(path), EdgeConfig(vectors={
                "image": EdgeVectorParams(size=IMAGE_DIM, distance=Distance.Cosine)}))
            self.shard.update(UpdateOperation.create_field_index("ts", PayloadSchemaType.Float))
        self.last_id = 0

    def add(self, frame: np.ndarray, said: str, ts: float | None = None) -> int:
        """Store one observation: a frame captured at `ts` and what the visitor said while it
        was in view. Each observation gets its own id, even for the same captured frame."""
        ts = ts or time.time()
        pid = self.last_id = max(self.last_id + 1, time.time_ns() // 1000)
        jpg = self.frames / f"{pid}.jpg"
        cv2.imwrite(str(jpg), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        self.shard.update(UpdateOperation.upsert_points([Point(pid, {}, {
            "ts": ts, "frame": jpg.name, "said": said})]))
        self.shard.flush()
        return pid

    def caption(self, pid: int, text: str) -> None:
        self.shard.update(UpdateOperation.set_payload([pid], {"caption": text}))
        self.shard.flush()

    def recent(self, before: float, n: int = 3) -> list[dict]:
        """Payloads (id, ts, frame, said, caption) of the newest captioned frames before
        `before`, newest first."""
        hits = self.shard.query(QueryRequest(
            limit=n, query=OrderBy("ts", Direction.Desc), with_payload=True,
            filter=Filter(must=[FieldCondition(key="ts", range=RangeFloat(lt=before)),
                                FieldCondition(key="caption", is_empty=False)])))
        return [{"id": h.id, **h.payload} for h in hits]


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        seen = Seen(Path(tmp))
        img = np.zeros((36, 64, 3), np.uint8)
        a = seen.add(img, "what is this?", ts=100.0)
        seen.add(img, "and this?", ts=200.0)
        assert seen.recent(before=300.0) == [], "uncaptioned frames are not memories yet"
        seen.caption(a, "a red mug in the center")
        assert [m["caption"] for m in seen.recent(before=300.0)] == ["a red mug in the center"]
        assert seen.recent(before=50.0) == []
        b, c = seen.add(img, "first turn", ts=300.0), seen.add(img, "second turn", ts=300.0)
        seen.caption(b, "a desk")
        seen.caption(c, "a desk")
        assert b != c and [m["said"] for m in seen.recent(before=400.0, n=2)] in (
            ["first turn", "second turn"], ["second turn", "first turn"]), "one frame, two turns"
        seen.shard.close()
        m = Seen(Path(tmp)).recent(before=300.0)[0]
        assert (Path(tmp) / "frames" / m["frame"]).exists(), "must survive a restart"
    print("selftest ok")
