"""The robot's memory, one Qdrant Edge shard: one point per turn, holding the frame it saw (JPEG
on disk as evidence, capture time, a caption the VLM wrote from that frame in idle time) and
what the visitor said. Statements carry a bge vector, so later questions find them by vector
search ("What drink do I like?" finds "I really love espresso"). M2 adds SigLIP 2 image vectors.
"""
import re
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
    Query,
    QueryRequest,
    RangeFloat,
    UpdateOperation,
)

from robot.config import SHARED
from robot.text_embed import DIM as TEXT_DIM

IMAGE_DIM = 768  # the SigLIP 2 vector slot M2 fills
THUMB = (64, 36)  # width, height
TOLD_MIN = 0.5   # bge cosine: relevant statements scored 0.53 to 0.72, unrelated 0.45 to 0.53
# Questions about the past get recent memories; questions about now do not, because a stale
# caption in the prompt pulls a 2B brain away from the image (D27).
_PAST = re.compile(r"\b(did|was|were|had|showed|shown|saw|seen|earlier|before|ago|yesterday|"
                   r"last time|previous(ly)?|remember|recall|first|after that|again)\b", re.I)


def thumb(frame: np.ndarray) -> np.ndarray:
    """64x36 grey thumbnail: enough to tell whether two frames show the same scene."""
    return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), THUMB)


# Past questions that also point at the present ("Is this what I showed you?") need the image.
_NOW = re.compile(r"\b(this|these|that one|now|here|right now)\b", re.I)
# ASR ends some questions with a period ("is Qdrant written in Rust."): the opening word decides.
_ASKS = re.compile(r"^(what|where|who|whom|whose|when|why|how|which|is|are|was|were|do|does|did|"
                   r"can|could|will|would|should|have|has|tell me)\b", re.I)


def about_past(question: str) -> bool:
    return bool(_PAST.search(question))


def about_now(question: str) -> bool:
    return bool(_NOW.search(question))


def is_question(text: str) -> bool:
    return text.rstrip().endswith("?") or bool(_ASKS.match(text.strip()))


class Memory:
    def __init__(self, root: Path = SHARED / "memory"):
        self.frames = root / "frames"
        self.frames.mkdir(parents=True, exist_ok=True)
        path = root / "seen"
        if path.exists():
            self.shard = EdgeShard.load(str(path))
        else:
            path.mkdir()
            self.shard = EdgeShard.create(str(path), EdgeConfig(vectors={
                "image": EdgeVectorParams(size=IMAGE_DIM, distance=Distance.Cosine),
                "said": EdgeVectorParams(size=TEXT_DIM, distance=Distance.Cosine)}))
            self.shard.update(UpdateOperation.create_field_index("ts", PayloadSchemaType.Float))
        self.last_id = 0

    def add(self, frame: np.ndarray, said: str, said_vec: np.ndarray | None = None,
            ts: float | None = None) -> int:
        """Store one turn: a frame captured at `ts` and what the visitor said while it was in
        view, with `said_vec` when it is a statement worth finding later. Each turn gets its
        own id, even for the same captured frame."""
        ts = ts or time.time()
        pid = self.last_id = max(self.last_id + 1, time.time_ns() // 1000)
        jpg = self.frames / f"{pid}.jpg"
        cv2.imwrite(str(jpg), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        vectors = {} if said_vec is None else {"said": said_vec.tolist()}
        self.shard.update(UpdateOperation.upsert_points([Point(pid, vectors, {
            "ts": ts, "frame": jpg.name, "said": said,
            "thumb": thumb(frame).tobytes().hex()})]))
        self.shard.flush()
        return pid

    def caption(self, pid: int, text: str) -> None:
        self.shard.update(UpdateOperation.set_payload([pid], {"caption": text}))
        self.shard.flush()

    @staticmethod
    def _row(hit) -> dict:
        row = {"id": hit.id, **hit.payload}
        grey = np.frombuffer(bytes.fromhex(row["thumb"]), np.uint8).reshape(THUMB[::-1])
        row["thumb"] = grey.astype(np.float32)
        return row

    def told(self, query: np.ndarray, before: float, n: int = 2) -> list[dict]:
        """Payloads of the visitor's earlier statements closest to `query` (unit bge vector)."""
        hits = self.shard.query(QueryRequest(
            limit=n, query=Query.Nearest(query.tolist(), using="said"), with_payload=True,
            score_threshold=TOLD_MIN,
            filter=Filter(must=[FieldCondition(key="ts", range=RangeFloat(lt=before))])))
        return [self._row(h) for h in hits]

    def recent(self, before: float, n: int = 3) -> list[dict]:
        """Payloads (id, ts, frame, said, caption, thumb) of the newest captioned frames before
        `before`, newest first."""
        hits = self.shard.query(QueryRequest(
            limit=n, query=OrderBy("ts", Direction.Desc), with_payload=True,
            filter=Filter(must=[FieldCondition(key="ts", range=RangeFloat(lt=before)),
                                FieldCondition(key="caption", is_empty=False)])))
        return [self._row(h) for h in hits]


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        seen = Memory(Path(tmp))
        img = np.zeros((36, 64, 3), np.uint8)
        a = seen.add(img, "what is this?", ts=100.0)
        seen.add(img, "and this?", ts=200.0)
        assert seen.recent(before=300.0) == [], "uncaptioned frames are not memories yet"
        seen.caption(a, "a red mug in the center")
        assert [m["caption"] for m in seen.recent(before=300.0)] == ["a red mug in the center"]
        assert seen.recent(before=50.0) == []
        b, c = seen.add(img, "first turn", ts=300.0), seen.add(img, "second turn", ts=300.0)
        v = np.zeros(TEXT_DIM, np.float32)
        v[0] = 1.0
        seen.add(img, "I love espresso.", v, ts=310.0)
        assert [m["said"] for m in seen.told(v, before=400.0)] == ["I love espresso."]
        assert seen.told(v, before=305.0) == [], "only statements made before the question"
        seen.caption(b, "a desk")
        seen.caption(c, "a desk")
        assert b != c and [m["said"] for m in seen.recent(before=400.0, n=2)] in (
            ["first turn", "second turn"], ["second turn", "first turn"]), "one frame, two turns"
        seen.shard.close()
        m = Memory(Path(tmp)).recent(before=300.0)[0]
        assert (Path(tmp) / "frames" / m["frame"]).exists(), "must survive a restart"
    assert about_past("What did I just show you?") and about_past("Do you remember me?")
    assert not about_past("What is on your left?") and not about_past("What color is it?")
    assert about_now("Is this what I showed you before?") and not about_now("What did I show you?")
    assert is_question("is Qdrant written in Rust.") and is_question("Where am I from?")
    assert not is_question("I'm visiting from Berlin.") and not is_question("My name is Dylan.")
    print("selftest ok")
