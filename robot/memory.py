"""The robot's memory, one Qdrant Edge shard: one point per turn, holding the frame it saw (JPEG
on disk as evidence, capture time, a caption the VLM wrote from that frame in idle time) and
what the visitor said, and one point per detector track (a sighting: label, region of the frame,
first and last seen times, and its source frame). Statements carry a bge vector, so later
questions find them by vector search ("What drink do I like?" finds "I really love espresso")."""
import re
import time
from collections.abc import Callable, Collection
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
    HasIdCondition,
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


# "What did I show you?" and its variants: the demo's key memory question, answered in code
# from the newest memory's main object, because the 2B brain often ignored a present memory.
_SHOWN = re.compile(r"\b(show|showed|shown|hold|holding|held|in my hands?|bring|brought)\b",
                    re.I)
_FIRST = re.compile(r"\bfirst\b", re.I)
# Anything that narrows which memory is meant (a time, a place, a comparison) goes to the
# brain with the memories instead: the code path only knows "newest" and "first".
_NARROWED = re.compile(r"\b(same|different|like|similar|compare|yesterday|today|morning|"
                       r"hour|hours|minutes?|ago|week|left|right|center|middle)\b", re.I)
_MAIN = re.compile(r"Main object:\s*([^.\n]+)")


def shown(question: str, memories: list[dict], age: Callable[[dict], str]) -> str | None:
    """The answer to "what did I show you" from memories (newest first), or None when the
    question is another kind or no memory names a main object."""
    if not (about_past(question) and _SHOWN.search(question)) or _NARROWED.search(question):
        return None
    named = [(m, x.group(1).strip()) for m in memories if (x := _MAIN.search(m["caption"]))]
    if not named:
        return None
    m, thing = named[-1] if _FIRST.search(question) else named[0]
    return f"You showed me {thing}, {age(m)}."


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
        for field in ("ts", "last_seen"):  # a no-op when the index exists
            self.shard.update(UpdateOperation.create_field_index(field, PayloadSchemaType.Float))
        self.last_id = 0

    def _id(self) -> int:
        """A new point or frame id, unique across restarts (microseconds since the epoch)."""
        self.last_id = max(self.last_id + 1, time.time_ns() // 1000)
        return self.last_id

    def save(self, frame: np.ndarray) -> str:
        """Store a frame as evidence; returns its file name."""
        jpg = f"{self._id()}.jpg"
        cv2.imwrite(str(self.frames / jpg), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return jpg

    def add(self, frame: np.ndarray, said: str, said_vec: np.ndarray | None = None,
            ts: float | None = None) -> int:
        """Store one turn: a frame captured at `ts` and what the visitor said while it was in
        view, with `said_vec` when it is a statement worth finding later. Each turn gets its
        own id, even for the same captured frame."""
        ts = ts or time.time()
        jpg, pid = self.save(frame), self._id()
        vectors = {} if said_vec is None else {"said": said_vec.tolist()}
        self.shard.update(UpdateOperation.upsert_points([Point(pid, vectors, {
            "ts": ts, "frame": jpg, "said": said, "thumb": thumb(frame).tobytes().hex()})]))
        self.shard.flush()
        return pid

    def sighting(self, label: str, region: str, seen: float, frame: str) -> int:
        """Store a new track: `label` in the `region` third of `frame` (a saved frame)."""
        pid = self._id()
        self.shard.update(UpdateOperation.upsert_points([Point(pid, {}, {
            "label": label, "region": region, "first_seen": seen, "last_seen": seen,
            "frame": frame})]))
        self.shard.flush()
        return pid

    def set(self, pid: int, **fields) -> None:
        """Update payload fields of a point: a caption, or a sighting's region and times."""
        self.shard.update(UpdateOperation.set_payload([pid], fields))
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

    def sightings(self, before: float, n: int = 4, hide: Collection[int] = ()) -> list[dict]:
        """Payloads (id, label, region, first_seen, last_seen, frame) of the sightings last
        seen before `before`, newest first, except the points in `hide`."""
        hits = self.shard.query(QueryRequest(
            limit=n, query=OrderBy("last_seen", Direction.Desc), with_payload=True,
            filter=Filter(must=[FieldCondition(key="last_seen", range=RangeFloat(lt=before))],
                          must_not=[HasIdCondition(set(hide))] if hide else None)))
        return [{"id": h.id, **h.payload} for h in hits]


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        seen = Memory(Path(tmp))
        img = np.zeros((36, 64, 3), np.uint8)
        a = seen.add(img, "what is this?", ts=100.0)
        seen.add(img, "and this?", ts=200.0)
        assert seen.recent(before=300.0) == [], "uncaptioned frames are not memories yet"
        seen.set(a, caption="a red mug in the center")
        assert [m["caption"] for m in seen.recent(before=300.0)] == ["a red mug in the center"]
        assert seen.recent(before=50.0) == []
        b, c = seen.add(img, "first turn", ts=300.0), seen.add(img, "second turn", ts=300.0)
        v = np.zeros(TEXT_DIM, np.float32)
        v[0] = 1.0
        seen.add(img, "I love espresso.", v, ts=310.0)
        assert [m["said"] for m in seen.told(v, before=400.0)] == ["I love espresso."]
        assert seen.told(v, before=305.0) == [], "only statements made before the question"
        seen.set(b, caption="a desk")
        seen.set(c, caption="a desk")
        assert b != c and [m["said"] for m in seen.recent(before=400.0, n=2)] in (
            ["first turn", "second turn"], ["second turn", "first turn"]), "one frame, two turns"
        cup = seen.sighting("cup", "left", 320.0, seen.save(img))
        seen.set(cup, region="center", last_seen=330.0)
        seen.sighting("bag", "right", 340.0, seen.save(img))
        assert [s["label"] for s in seen.sightings(before=400.0)] == ["bag", "cup"]
        assert seen.sightings(before=335.0)[0]["region"] == "center", "the update moved it"
        assert [s["label"] for s in seen.sightings(before=400.0, n=1, hide={
            seen.sightings(before=400.0)[0]["id"]})] == ["cup"], "hidden points leave room"
        assert len(seen.recent(before=400.0, n=9)) == 3 and seen.told(v, before=400.0)[0][
            "said"] == "I love espresso.", "sightings are neither captioned frames nor statements"
        seen.shard.close()
        again = Memory(Path(tmp))
        m = again.recent(before=300.0)[0]
        assert (Path(tmp) / "frames" / m["frame"]).exists(), "must survive a restart"
        s = again.sightings(before=400.0)[1]
        assert (s["label"], s["first_seen"], s["last_seen"]) == ("cup", 320.0, 330.0)
        assert (Path(tmp) / "frames" / s["frame"]).exists()
    assert about_past("What did I just show you?") and about_past("Do you remember me?")
    assert not about_past("What is on your left?") and not about_past("What color is it?")
    assert about_now("Is this what I showed you before?") and not about_now("What did I show you?")
    assert is_question("is Qdrant written in Rust.") and is_question("Where am I from?")
    mems = [{"caption": "Main object: a bus. Around it: a street."},
            {"caption": "Main object: green apples\nAround it: a bowl."}]
    ago = lambda m: "just now"  # noqa: E731
    assert shown("What did I just show you?", mems, ago) == "You showed me a bus, just now."
    assert shown("What was the first thing I showed you?", mems, ago).startswith(
        "You showed me green apples")
    assert shown("Is this the same thing I showed you?", mems, ago) is None
    assert shown("What did we talk about?", mems, ago) is None
    assert shown("What did I show you yesterday?", mems, ago) is None
    assert shown("What did I show you on the left?", mems, ago) is None
    assert not is_question("I'm visiting from Berlin.") and not is_question("My name is Dylan.")
    print("selftest ok")
