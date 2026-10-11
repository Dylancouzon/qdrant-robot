"""The robot's memory, one Qdrant Edge shard: one point per turn, holding the frame it saw (JPEG
on disk as evidence, capture time, a caption the VLM wrote from that frame in idle time) and
what the visitor said, and one point per detector track (a sighting: label, region of the frame,
first and last seen times; no frame). Statements carry a bge vector, so later
questions find them by vector search ("What drink do I like?" finds "I really love espresso")."""
import re
import time
from collections.abc import Callable, Collection
from pathlib import Path

import cv2
import numpy as np
from qdrant_edge import (
    CountRequest,
    Direction,
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    HasIdCondition,
    MatchAny,
    MatchValue,
    OrderBy,
    PayloadSchemaType,
    Point,
    Query,
    QueryRequest,
    RangeFloat,
    ScrollRequest,
    UpdateOperation,
)

from robot.config import SHARED
from robot.text_embed import DIM as TEXT_DIM

IMAGE_DIM = 768  # the SigLIP 2 vector slot M2 fills
THUMB = (64, 36)  # width, height
# Retention (reviews/20261008-151809-4769-design.md): ordinary evidence (sightings, turn frames,
# captions, statements) lasts the booth day. The caps are a safety net: a 30-minute soak stored
# 185 sightings, so a booth day is about 4,500 points; 20,000 is four times that. A frame is
# about 130 KB (J), so 20,000 frames take about 2.6 GB; 4 GB of the 109 GB free disk holds them.
RETAIN_S = 12 * 3600
MAX_POINTS = 20_000
MAX_FRAME_BYTES = 4 << 30
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
_COMPARING = "same|different|like|similar|compare"
_WHEN_WHERE = "yesterday|today|morning|hours?|minutes?|week|left|right|center|middle"
_COMPARE = re.compile(rf"\b({_COMPARING})\b", re.I)
_WHEN = re.compile(rf"\b({_WHEN_WHERE})\b", re.I)  # "a moment ago" is not here: RAM answers it
_NARROWED = re.compile(rf"\b({_COMPARING}|{_WHEN_WHERE}|ago)\b", re.I)
_ORDINAL = re.compile(r"\b(first|second(?!\s+ago)|third|fourth|last|latest)\b", re.I)
_NTH = {"first": 0, "second": 1, "third": 2, "fourth": 3}  # any other ordinal: the newest
_MAIN = re.compile(r"Main object:\s*([^.\n]+)")


def main_object(caption: str) -> str | None:
    """The main object a stored frame's caption names ("a gold keypad phone"), or None."""
    return x.group(1).strip() if (x := _MAIN.search(caption)) else None


def shown(question: str, memories: list[dict], age: Callable[[dict], str]) -> str | None:
    """The answer to "what did I show you" from memories (newest first), or None when the
    question is another kind or no memory names a main object."""
    if not (about_past(question) and _SHOWN.search(question)) or _NARROWED.search(question):
        return None
    named = [(m, x) for m in memories if (x := main_object(m["caption"]))]
    if not named:
        return None
    m, thing = named[-1] if _FIRST.search(question) else named[0]
    return f"You showed me {thing}, {age(m)}."


def earlier_view(question: str, looks: list, now, differs: Callable) -> object | None:
    """The one retained look (oldest first) that a past question about something shown means,
    for a visitor who shows things and then changes the view. None: another kind of question
    (a present one, a comparison, a time or place the window cannot hold: stored memories answer
    those), or no look to pick, so nothing changes. When no look `differs` from `now`, the newest
    look shows the present view, and the caller sends the present image. Otherwise the
    candidates are the looks that differ, runs of the same view counted once and represented by
    their newest; "first", "second", and "third" count from the oldest, anything else is the
    newest."""
    if not (about_past(question) and _SHOWN.search(question)) or about_now(question) \
            or _COMPARE.search(question) or _WHEN.search(question) or not looks:
        return None
    apart: list = []
    for look in looks:
        if differs(look, now):
            if apart and not differs(apart[-1], look):
                apart[-1] = look
            else:
                apart.append(look)
    if not apart:
        return looks[-1]
    n = _NTH.get(m.group(1).lower(), -1) if (m := _ORDINAL.search(question)) else -1
    return apart[n] if n < len(apart) else None


# Sighting questions ("what was on your left?", "is the cup still there?", "what is gone?"),
# answered in code from the detector's sightings and what it tracks now: the 2B brain ignored
# sighting lines in its prompt (D43). Each group is one kind of thing for a visitor: detector
# labels that flicker on one object, and the words people use for them.
KINDS = ["cup|mug", "teddy bear|plush toy|toy|teddy|plush|stuffed animal",
         "bag|backpack|handbag|purse|rucksack|suitcase", "phone|mobile|cellphone|smartphone",
         "laptop|computer", "monitor|screen|display|tv|television",
         "computer mouse|mouse", "remote control|remote", "potted plant|plant|flower",
         "glasses|sunglasses|spectacles", "headphones|headset|earphones", "t-shirt|shirt",
         "bicycle|bike", "motorcycle|motorbike", "keys|key", "dog|puppy", "cat|kitten",
         "person|man|woman|someone|somebody|people|visitor", "photo|picture|photograph"]
SAID = 3  # sightings named in one answer at most
_SIDE = re.compile(r"\b(?:your|my|the)\s+(left|right)\b|\b(left|right)[\s-](?:side|hand|corner)\b|"
                   r"\b(center|centre|middle)\b", re.I)
_GONE = re.compile(r"\b(gone|missing|disappear\w*|vanish\w*|took|taken|take away|removed?|"
                   r"chang\w*|no longer|not (?:there|here)|isn't (?:there|here))\b", re.I)
_STILL = re.compile(r"\b(still|anymore|any more|no longer)\b", re.I)
_SEES = re.compile(r"\b(see|sees|seen|saw|spot\w*|notic\w*|make out|find|found|there|here|around|"
                   r"anywhere|in view|in front)\b", re.I)
_PERFECT = re.compile(r"\b(have|has|ever)\b", re.I)  # "have you seen", "has anyone left"
_NOW_TOO = re.compile(r"\b(now|have|has|ever)\b", re.I)  # a past question that reaches now
_WHERE = re.compile(r"\bwhere\b", re.I)
_IT = re.compile(r"\b(it|them|they|that one)\b", re.I)
_WHAT = re.compile(r"\b(what|which|anything|something)\b", re.I)


def _groups(vocab: Collection[str]) -> list[list[str]]:
    return [g.split("|") for g in KINDS] + [[label] for label in vocab]


def kinds(text: str, vocab: Collection[str]) -> set[str]:
    """The detector labels a text names, with their kind's other labels ("mugs" names cup and
    mug). Plurals count; words of no label in `vocab` do not."""
    groups = _groups(vocab)
    known = {w for g in groups for w in g}
    words = [w if w in known else w[:-2] if w.endswith("es") and w[:-2] in known
             else w[:-1] if w.endswith("s") and w[:-1] in known else w
             for w in re.findall(r"[a-z]+(?:-[a-z]+)?", text.lower())]
    text = f" {' '.join(words)} "
    return {w for g in groups if any(f" {x} " in text for x in g) for w in g if w in vocab}


def sighting_query(question: str, context: list[str], vocab: Collection[str]
                   ) -> tuple[str, dict[str, set[str]], bool] | None:
    """What a sighting question asks, or None for any other question: ("kind", {"label": ...})
    for where a named thing is or was; ("gone", match) for what left the view; ("seen", match)
    for what was seen, optionally {"region": ...}; and whether it asks about now too. "it" is
    the one object the newest text of `context` (the last exchange, newest first) names."""
    labels, regions = kinds(question, vocab), {
        "center" if g in ("centre", "middle") else g.lower()
        for m in _SIDE.finditer(question) for g in m.groups() if g}
    where, still, gone = (bool(x.search(question)) for x in (_WHERE, _STILL, _GONE))
    if not labels and _IT.search(question) and (where or still):
        labels = next((k for k in (kinds(c, vocab) for c in context) if k), set())
        labels = labels if len(set(map(kind_of, labels))) == 1 else set()
    now = not about_past(question) or still or bool(_NOW_TOO.search(question))
    past = about_past(question) or bool(_PERFECT.search(question))
    if labels and (where or gone or (past or still) and (regions or _SEES.search(question))):
        return "kind", {"label": labels}, now
    match = {"region": regions} if regions else {}
    if labels or not _WHAT.search(question):
        return None
    if gone:
        return "gone", match, False
    return ("seen", match, now) if past and (regions or _SEES.search(question)) else None


def article(label: str) -> str:
    return label if label.endswith("s") else f"{'an' if label[0] in 'aeiou' else 'a'} {label}"


def kind_of(label: str) -> str:
    return next((g.split("|")[0] for g in KINDS if label in g.split("|")), label)


def sighting_answer(mode: str, match: dict[str, set[str]], now_too: bool, past: list[dict],
                    now: list[dict], ago: Callable[[float], str]) -> tuple[str, list[int]] | None:
    """The spoken answer to a sighting_query and the ids of the sightings it names, or None
    when no sighting matches: captions then answer, as they cover objects the detector cannot
    name. `past`: sightings out of view, newest first (already matched); `now`: every sighting
    in view. Each sighting is one track; tracks of one kind in one region are named together,
    because the detector cannot tell whether they are the same object."""
    visible: dict[str, list[str]] = {}  # kind -> regions in view, over the whole frame
    for s in now:
        visible.setdefault(kind_of(s["label"]), []).append(s["region"])
    now = [s for s in now if all(s[k] in v for k, v in match.items())]
    groups: dict[tuple[str, str], list[dict]] = {}
    for s in (now if now_too and mode != "gone" else []) + past:
        groups.setdefault(_key(s), []).append(s)
    named = list(groups.values())[:SAID]
    if not named:
        return None
    ids = {s["id"] for s in now}
    return (" ".join(_described(g, ids, visible.get(kind_of(g[0]["label"]), []), ago)
                     for g in named), [s["id"] for g in named for s in g])


def _key(s: dict) -> tuple[str, str]:
    return kind_of(s["label"]), s["region"]


def _side(region: str) -> str:
    # Spoken to the visitor: the robot's own left and right (image left is the robot's left).
    return "in the center" if region == "center" else f"on my {region}"


def _described(group: list[dict], now: set[int], visible: list[str],
               ago: Callable[[float], str]) -> str:
    """One kind in one region: in view now (the first track), or last seen, then where the
    same kind is in view now, anywhere in the frame (a moved object is a new track)."""
    s, unsure = group[0], "; I cannot tell if it is the same one."
    thing, where = article(s["label"]), _side(s["region"])
    if s["id"] in now:
        earlier = [x for x in group if x["id"] not in now]
        return f"I see {thing} {where} now." + (
            f" I also saw {thing} there {ago(earlier[0]['last_seen'])}{unsure}" if earlier else "")
    saw = f"I saw {thing} {where}, {ago(s['last_seen'])}"
    if visible:
        there = "there" if s["region"] in visible else " and ".join(map(_side, sorted(visible)))
        return f"{saw}. I see {thing} {there} now{unsure}"
    return f"{saw}; I do not see {'them' if s['label'].endswith('s') else 'it'} now."


def about_past(question: str) -> bool:
    return bool(_PAST.search(question))


def about_now(question: str) -> bool:
    return bool(_NOW.search(question))


def is_question(text: str) -> bool:
    return text.rstrip().endswith("?") or bool(_ASKS.match(text.strip()))


# A deletion is authorized only by an imperative: the line starts with the verb, after optional
# filler, a polite frame ("can you please"), or "I want you to". Everything else is no command.
_DELETE = re.compile(r"^\W*(?:(?:ok|okay|so|um|uh|well|now|and|then|please)\W+)*"
                     r"(?:(?:(?:can|could|would|will)\s+you|i(?:'d| would)? (?:want|like)\s+you"
                     r"\s+to)\s+(?:please\s+)?)?(?:forget|delete|erase|remove)\b\W*", re.I)


def deletion_target(text: str) -> str | None:
    """What an imperative deletion ("Please forget my phone") names, else None."""
    text = text.replace("\u2019", "'")
    return text[m.end():] if (m := _DELETE.match(text)) else None


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
        self.shard.update(UpdateOperation.create_field_index("frame", PayloadSchemaType.Keyword))
        self.last_id = 0
        self.frame_bytes = self._sweep()  # the bytes MAX_FRAME_BYTES limits

    def _held(self, jpg: str) -> bool:
        return bool(self.shard.count(CountRequest(filter=Filter(must=[
            FieldCondition(key="frame", match=MatchValue(jpg))]))))

    def _sweep(self) -> int:
        """Delete every frame file that no point holds (crash leftovers: with the shard just
        opened, no write is pending); returns the bytes of the rest, the bytes MAX_FRAME_BYTES
        limits."""
        held, offset = set(), None
        while True:  # one pass over the frame names, not a query per file
            page, offset = self.shard.scroll(ScrollRequest(
                offset=offset, limit=1000, with_payload=["frame"]))
            held |= {r.payload["frame"] for r in page if "frame" in r.payload}
            if offset is None:
                break
        for f in [f for f in self.frames.glob("*.jpg") if f.name not in held]:
            f.unlink()
        return sum(f.stat().st_size for f in self.frames.glob("*.jpg"))

    def _id(self) -> int:
        """A new point or frame id, unique across restarts (microseconds since the epoch)."""
        self.last_id = max(self.last_id + 1, time.time_ns() // 1000)
        return self.last_id

    def save(self, frame: np.ndarray) -> str:
        """Store a frame as evidence; returns its file name."""
        jpg = f"{self._id()}.jpg"
        cv2.imwrite(str(self.frames / jpg), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        self.frame_bytes += (self.frames / jpg).stat().st_size
        return jpg

    def add(self, frame: np.ndarray | None, said: str, said_vec: np.ndarray | None = None,
            ts: float | None = None, **fields) -> int:
        """Store text and an optional source crop, with a statement vector when supplied."""
        ts = ts or time.time()
        visual = {} if frame is None else {"frame": self.save(frame),
                                          "thumb": thumb(frame).tobytes().hex()}
        pid = self._id()
        vectors = {} if said_vec is None else {"said": said_vec.tolist()}
        self.shard.update(UpdateOperation.upsert_points([Point(pid, vectors, {
            "ts": ts, "said": said, **visual, **fields})]))
        self.shard.flush()
        return pid

    def sighting(self, label: str, region: str, seen: float, named: str | None = None) -> int:
        """Store a new track: `label` in the `region` third of the frame, and the name of the
        visitor's object it matched (robot/things.py)."""
        pid = self._id()
        self.shard.update(UpdateOperation.upsert_points([Point(pid, {}, {
            "label": label, "region": region, "first_seen": seen, "last_seen": seen,
            **({"named": named} if named else {})})]))
        self.shard.flush()
        return pid

    def set(self, pid: int, **fields) -> bool:
        """Update payload fields of a point: a caption, or a sighting's label, region, and
        times. False, and nothing written, when the point is gone (evicted or forgotten before
        a pending write)."""
        if not self.points([pid]):
            return False
        self.shard.update(UpdateOperation.set_payload([pid], fields))
        self.shard.flush()
        return True

    def forget(self, ids: Collection[int]) -> None:
        """Delete the points still kept of `ids`, and their frames unless another point holds
        the same frame."""
        found = self.points(ids)
        self.shard.update(UpdateOperation.delete_points([p["id"] for p in found]))
        self.shard.flush()
        for jpg in {p["frame"] for p in found if "frame" in p}:
            if not self._held(jpg) and (path := self.frames / jpg).exists():
                self.frame_bytes -= path.stat().st_size
                path.unlink()

    def _oldest(self, n: int, before: float, keep: Collection[int]) -> list[int]:
        """Up to `n` ids of the oldest points last seen before `before` (turns by capture time,
        sightings by last seen), oldest first, except the point ids in `keep`."""
        hide, found = [HasIdCondition(keep)] if keep else None, []
        for field in ("ts", "last_seen"):
            found += [(h.payload[field], h.id) for h in self.shard.query(QueryRequest(
                limit=n, query=OrderBy(field, Direction.Asc), with_payload=[field],
                filter=Filter(must=[FieldCondition(key=field, range=RangeFloat(lt=before))],
                              must_not=hide)))]
        return [i for _, i in sorted(found)[:n]]

    def retain(self, now: float, active: Collection[int]) -> list[int]:
        """Evict the evidence older than RETAIN_S, then the oldest points until the shard and
        its frame files are under the caps, never the `active` points (tracks still in view).
        Returns the evicted point ids."""
        keep, evicted = set(active), []
        while old := self._oldest(256, now - RETAIN_S, keep):
            self.forget(old)
            evicted += old
        while (over := self.shard.count(CountRequest()) - MAX_POINTS) > 0 or (
                self.frame_bytes > MAX_FRAME_BYTES):
            if not (old := self._oldest(over if over > 0 else 1, float("inf"), keep)):
                break  # everything left is in view
            self.forget(old)
            evicted += old
        return evicted

    @staticmethod
    def _row(hit) -> dict:
        row = {"id": hit.id, **hit.payload}
        if "thumb" in row:
            grey = np.frombuffer(bytes.fromhex(row["thumb"]), np.uint8).reshape(THUMB[::-1])
            row["thumb"] = grey.astype(np.float32)
        return row

    def told(self, query: np.ndarray, before: float, n: int = 2) -> list[dict]:
        """Payloads of the visitor's earlier statements closest to `query` (unit bge vector)."""
        hits = self.shard.query(QueryRequest(
            limit=n, query=Query.Nearest(query.tolist(), using="said"), with_payload=True,
            score_threshold=TOLD_MIN,
            filter=Filter(must=[FieldCondition(key="ts", range=RangeFloat(lt=before))])))
        return [{**self._row(h), "score": h.score} for h in hits]

    def recent(self, before: float, n: int = 3,
               selected: dict[str, list[int]] | None = None, skip: Collection[str] = ()
               ) -> list[dict]:
        """Payloads (id, ts, frame, said, caption, thumb) of the newest captioned frames before
        `before`, newest first."""
        must = [FieldCondition(key="ts", range=RangeFloat(lt=before)),
                FieldCondition(key="frame", is_empty=False),
                FieldCondition(key="caption", is_empty=False)]
        if selected is not None:
            if not selected:
                return []
            ids = {i for linked in selected.values() for i in linked}
            must.append(Filter(should=[FieldCondition(key="named", match=MatchAny(list(selected))),
                                       *([HasIdCondition(ids)] if ids else [])]))
        hits = self.shard.query(QueryRequest(
            limit=n, query=OrderBy("ts", Direction.Desc), with_payload=True,
            filter=Filter(must=must, must_not=[
                FieldCondition(key="label", match=MatchAny(list(skip)))] if skip else None)))
        return [self._row(h) for h in hits]

    def sightings(self, before: float, n: int = 4, hide: Collection[int] = (),
                  skip: Collection[str] = (), **match: Collection[str]) -> list[dict]:
        """Payloads (id, label, region, first_seen, last_seen) of the sightings last
        seen before `before`, newest first, except the points in `hide` and the labels in
        `skip` (ignored kinds); `match` keeps those whose field has one of the given values
        (label=["cup", "mug"])."""
        if any(not values for values in match.values()):
            return []
        hits = self.shard.query(QueryRequest(
            limit=n, query=OrderBy("last_seen", Direction.Desc), with_payload=True,
            filter=Filter(must=[FieldCondition(key="last_seen", range=RangeFloat(lt=before)),
                                *(FieldCondition(key=k, match=MatchAny(list(v)))
                                  for k, v in match.items())],
                          must_not=[HasIdCondition(set(hide))] * bool(hide) + [
                              FieldCondition(key="label", match=MatchAny(list(skip)))
                          ] * bool(skip) or None)))
        return [{"id": h.id, **h.payload} for h in hits]

    def forget_named(self, name: str) -> None:
        """Delete selected crops and sightings, including records outside current track links."""
        while rows := self.shard.scroll(ScrollRequest(limit=100, with_payload=False, filter=Filter(
                must=[FieldCondition(key="named", match=MatchValue(name))])))[0]:
            self.forget([r.id for r in rows])

    def points(self, ids: Collection[int]) -> list[dict]:
        """Payloads of the points `ids` (the sightings in view now)."""
        return [{"id": r.id, **r.payload}
                for r in self.shard.retrieve(list(ids), True, False)] if ids else []

def _earlier_selftest() -> None:
    """Views are numbers: a view differs from another by more than 1."""
    differs = lambda a, b: abs(a - b) > 1  # noqa: E731
    pick = lambda q, looks, now=0: earlier_view(q, looks, now, differs)  # noqa: E731
    looks = [10, 10.5, 20, 0.5]  # clock twice, laptop, then the present view again
    assert pick("What did I just show you?", looks) == 20, "the newest differing view"
    assert pick("What was the first thing I showed you?", looks) == 10.5, "a run counts once"
    assert pick("And the second thing I showed you?", looks) == 20
    assert pick("What was the third thing I showed you?", looks) is None, "no third"
    assert pick("What did I show you a second ago?", looks) == 20, "a time, not an ordinal"
    assert pick("What did I show you after that?", looks) == 20
    assert pick("Which thing did I hold up a moment ago?", looks) == 20
    assert pick("Remind me what I brought earlier.", looks) == 20
    assert pick("What did I just show you?", [0.2, 0.9]) == 0.9, "unchanged: the same view"
    for when in ("yesterday", "this morning", "two hours ago", "on the left"):
        assert pick(f"What did I show you {when}?", looks) is None, when
    assert pick("What did I just show you?", []) is None, "no earlier exchange"
    assert pick("What am I holding now?", looks) is None, "a present question"
    assert pick("What is this?", looks) is None
    assert pick("Is this the same thing I showed you?", looks) is None, "combined: not here"
    assert pick("Was it the same as what I showed you before?", looks) is None
    assert pick("What did we talk about before?", looks) is None, "not about something shown"


def _sighting_selftest() -> None:
    vocab = {"cup", "mug", "bag", "backpack", "keys", "umbrella", "potted plant", "lamp", "clock"}
    q = lambda text, *context: sighting_query(text, list(context), vocab)  # noqa: E731
    assert kinds("Did you spot any mugs or backpacks?", vocab) == {"cup", "mug", "bag", "backpack"}
    assert kinds("the flowers", vocab) == {"potted plant"} and kinds("a giraffe", vocab) == set()
    assert q("Where did my umbrella end up?") == ("kind", {"label": {"umbrella"}}, False)
    assert q("Can you still make out the plant?") == ("kind", {"label": {"potted plant"}}, True)
    assert q("Has anyone left their keys around here?") == ("kind", {"label": {"keys"}}, True)
    assert q("Was the clock in the middle or on the right side?")[::2] == ("kind", False)
    assert q("Could you tell if it is still there?", "I see a lamp on my right now.") == (
        "kind", {"label": {"lamp"}}, True), "'it' is the one thing the last exchange named"
    assert q("Is it still there?", "A lamp and a clock.", "the lamp?") is None, "ambiguous 'it'"
    assert q("Hmm, which thing vanished from the middle?") == ("gone", {"region": {"center"}},
                                                               False)
    assert q("Anything changed since then?") == ("gone", {}, False)
    assert q("Tell me what sat to the left-hand side a minute ago, what was it?") == (
        "seen", {"region": {"left"}}, False)
    assert q("So what did you notice during my break?") == ("seen", {}, False)
    for other in ("What's on your right?", "Is this the same bag as before?", "What color "
                  "was the umbrella?", "Do you still remember my mug?", "What do you see "
                  "right now?", "What did we chat about earlier?", "Is it heavy?"):
        assert q(other) is None, other
    ago = lambda ts: f"{100 - ts:.0f} seconds ago"  # noqa: E731
    lamp = {"id": 1, "label": "lamp", "region": "right", "last_seen": 10.0}
    mug = {"id": 2, "label": "mug", "region": "left", "last_seen": 80.0}
    cup = {"id": 3, "label": "cup", "region": "left", "last_seen": 60.0}  # maybe the same mug
    clock = {"id": 4, "label": "clock", "region": "right", "last_seen": 50.0}
    new_mug = {"id": 5, "label": "mug", "region": "left", "last_seen": 90.0}
    assert sighting_answer("gone", {}, False, [mug, cup, clock], [lamp], ago) == (
        "I saw a mug on my left, 20 seconds ago; I do not see it now. I saw a clock on my "
        "right, 50 seconds ago; I do not see it now.", [2, 3, 4]), "one kind and side, together"
    assert sighting_answer("gone", {}, False, [mug], [new_mug], ago)[0] == (
        "I saw a mug on my left, 20 seconds ago. I see a mug there now; I cannot tell if it is "
        "the same one."), "a new mug on the same side does not hide the earlier one"
    assert sighting_answer("seen", {"region": {"right"}}, False, [clock], [lamp], ago) == (
        "I saw a clock on my right, 50 seconds ago; I do not see it now.", [4]), \
        "a past question leaves out what is in view now"
    assert sighting_answer("kind", {"label": {"mug", "cup"}}, True, [mug], [new_mug], ago)[0] \
        == ("I see a mug on my left now. I also saw a mug there 20 seconds ago; I cannot tell "
            "if it is the same one.")
    many = [{**cup, "id": 10 + k, "last_seen": 70.0 - k} for k in range(9)]
    assert sighting_answer("seen", {}, False, many + [clock], [], ago)[1][-1] == 4, \
        "repeated sightings of one kind leave room for others"
    moved = {"id": 6, "label": "clock", "region": "left", "last_seen": 95.0}  # a new track
    assert sighting_answer("seen", {"region": {"right"}}, False, [clock], [moved, lamp], ago)[
        0] == ("I saw a clock on my right, 50 seconds ago. I see a clock on my left now; I "
               "cannot tell if it is the same one."), "no 'not seen' claim when it moved sides"
    assert sighting_answer("kind", {"label": {"keys"}}, True, [], [lamp], ago) is None
    assert sighting_answer("seen", {"region": {"center"}}, True, [], [lamp], ago) is None

def _retain_selftest(seen: Memory, frames: Path, img: np.ndarray) -> None:
    global MAX_POINTS, MAX_FRAME_BYTES
    hour, day = 3600.0, 1000.0 + RETAIN_S  # the selftest's clock: the shard's oldest is ts 100
    old_turns = [m["frame"] for m in seen.recent(before=1e9, n=99)]
    cups = [seen.sighting("cup", "left", day - hour + k) for k in range(4)]
    assert seen.retain(day, ()) and len(seen.sightings(1e9, 99, label=["cup"])) == 4, \
        "an hour-old cup outlives three newer cup tracks"
    assert seen.recent(before=1e9, n=99) == [] and seen.told(np.eye(TEXT_DIM)[0], 1e9) == [], \
        "turns, captions, and statements past the window are evicted"
    assert old_turns and not any((frames / f).exists() for f in old_turns), "and their frames"
    assert seen.sightings(1e9, 99, label=["bag"]) == [], "a sighting past the window too"
    MAX_POINTS, MAX_FRAME_BYTES = 3, 1 << 40
    named = seen.add(img, "this is my phone", ts=day - 1)  # a linked turn: it expires too
    kept = seen.points([named])[0]["frame"]
    for k in range(10):  # turnover: one cup stays in view, others come and go
        seen.sighting("cup", "right", day + k)
        seen.retain(day + k, {cups[0]})
        assert seen.shard.count(CountRequest()) == MAX_POINTS, "the cap holds exactly"
    assert seen.points([cups[0]]) and not seen.points([named]), "the oldest out of view go"
    assert not (frames / kept).exists(), "with its frame"
    assert not seen.set(named, caption="x"), "a pending write to an evicted point is dropped"
    seen.forget([named, cups[0]])
    assert not seen.points([cups[0]]), "forget skips the ids already gone"
    MAX_POINTS = 20_000
    for k in range(3):
        seen.add(img, f"turn {k}", ts=day + 20 + k)
    MAX_FRAME_BYTES = seen.frame_bytes - 1
    seen.retain(day + 30, {cups[0]})
    assert seen.frame_bytes <= MAX_FRAME_BYTES, "the disk cap evicts the oldest out of view"
    MAX_FRAME_BYTES = 4 << 30


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
        cup = seen.sighting("cup", "left", 320.0)
        seen.set(cup, region="center", last_seen=330.0)
        seen.sighting("bag", "right", 340.0)
        assert [s["label"] for s in seen.sightings(before=400.0)] == ["bag", "cup"]
        assert seen.sightings(before=335.0)[0]["region"] == "center", "the update moved it"
        mine = seen.sighting("cup", "right", 336.0, named="cup")
        assert [s["id"] for s in seen.sightings(400.0, named=["cup"])] == [mine]
        assert [s["label"] for s in seen.sightings(400.0, skip=["cup"])] == ["bag"]
        seen.forget_named("cup")
        assert seen.sightings(400.0, named=["cup"]) == [] and not seen.points([mine])
        seen.forget([mine])
        assert [s["label"] for s in seen.sightings(before=400.0, n=1, hide={
            seen.sightings(before=400.0)[0]["id"]})] == ["cup"], "hidden points leave room"
        assert len(seen.recent(before=400.0, n=9)) == 3 and seen.told(v, before=400.0)[0][
            "said"] == "I love espresso.", "sightings are neither captioned frames nor statements"
        seen.shard.close()
        frames = Path(tmp) / "frames"
        orphans = ("1.jpg", "2.jpg", f"{seen.last_id + 10**9}.jpg")  # crash leftovers
        for orphan in orphans:
            (frames / orphan).write_bytes(b"x" * 10)
        again = Memory(Path(tmp))
        assert not any((frames / f).exists() for f in orphans), "orphans are deleted at open"
        assert again.frame_bytes == sum(f.stat().st_size for f in frames.iterdir()), \
            "the disk cap counts the frames left: the held ones"
        m = again.recent(before=300.0)[0]
        assert (Path(tmp) / "frames" / m["frame"]).exists(), "must survive a restart"
        s = again.sightings(before=400.0)[1]
        assert (s["label"], s["first_seen"], s["last_seen"]) == ("cup", 320.0, 330.0)
        assert "frame" not in s, "a sighting stores no frame"
        _retain_selftest(again, Path(tmp) / "frames", img)
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
    _earlier_selftest()
    assert not is_question("I'm visiting from Berlin.") and not is_question("My name is Dylan.")
    _sighting_selftest()
    print("selftest ok")

