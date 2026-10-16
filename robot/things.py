"""Owner-scoped named objects, view thumbnails, visitors, and Ignore rules in Qdrant Edge.
Object point IDs remain stable when the visitor tells a name or enrolls a face."""
import re
import shutil
import uuid
import time
from collections.abc import Collection
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from qdrant_edge import (
    CountRequest,
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    MatchValue,
    HasIdCondition,
    MultiVectorComparator,
    MultiVectorConfig,
    Point,
    PayloadSchemaType,
    Query,
    QueryRequest,
    ScrollRequest,
    UpdateOperation,
)

from robot.config import MODELS, SHARED
from robot.memory import deletion_target, is_question, kind_of, kinds
from robot.people import request
from robot.settings import settings

MODEL = MODELS / "dinov3-small/model.onnx"
DIM = 768  # DINOv3-small CLS and mean patch token, each unit length, concatenated
PREFIX = 5  # the CLS token and four register tokens come before the patch tokens
SHOTS = 3  # crops of the named track, a third of a second apart
_MEAN, _STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])


class Crops:
    """Crop vectors: DINOv3-small at 224x224 on the GPU when present, the crop padded square."""

    def __init__(self):
        cuda = "CUDAExecutionProvider" in ort.get_available_providers()
        providers = ([("CUDAExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"})]
                     if cuda else ["CPUExecutionProvider"])
        self.sess = ort.InferenceSession(str(MODEL), providers=providers)

    def __call__(self, crops: list[np.ndarray]) -> np.ndarray:
        x = np.stack([_square(c) for c in crops])
        t = self.sess.run(None, {"pixel_values": x})[0]
        cls, patches = t[:, 0], t[:, PREFIX:].mean(1)
        v = np.concatenate([_unit(cls), _unit(patches)], axis=1)
        return v / np.sqrt(2)


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _square(c: np.ndarray) -> np.ndarray:
    h, w = c.shape[:2]
    s = max(h, w)  # pad, so the object keeps its shape
    sq = cv2.copyMakeBorder(c, (s - h) // 2, s - h - (s - h) // 2, (s - w) // 2,
                            s - w - (s - w) // 2, cv2.BORDER_CONSTANT, value=(114,) * 3)
    x = cv2.resize(sq, (224, 224), interpolation=cv2.INTER_LINEAR)[..., ::-1] / 255.0
    return ((x - _MEAN) / _STD).astype(np.float32).transpose(2, 0, 1)


def cut(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = box
    return frame[y1:y2, x1:x2]


def add_vectors(stored: np.ndarray, new: np.ndarray) -> np.ndarray:
    """Append distinct views, retaining the first view and removing the oldest others."""
    views = list(stored)
    for vector in new:
        if views and np.max(_unit(np.asarray(views)) @ _unit(vector[None])[0]) >= \
                settings.duplicate:
            continue
        views.append(vector)
    while len(views) > settings.views_cap:
        views.pop(1)
    return np.asarray(views, dtype=np.float32)


class Things:
    def __init__(self, root: Path = SHARED / "memory", people=None):
        self.people = people
        path = root / "things"
        marker = _id("schema:dinov3")  # names the encoder that made the shard's vectors
        carried = []
        if path.exists():
            self.shard = EdgeShard.load(str(path))
            if not self.shard.retrieve([marker], False, False):
                carried = _carried(self.shard)
                self.shard.close()
                shutil.rmtree(path)  # unusable vectors; a copy would escape "forget me"
        if not path.exists():
            path.mkdir(parents=True)
            self.shard = EdgeShard.create(str(path), EdgeConfig(vectors={"crops": EdgeVectorParams(
                size=DIM, distance=Distance.Cosine,
                multivector_config=MultiVectorConfig(MultiVectorComparator.MaxSim))}))
            self.shard.update(UpdateOperation.upsert_points(
                [Point(marker, {}, {"schema": 2}), *carried]))
        # Every filtered query needs these; unindexed, `type` alone cost 9 ms per score (J).
        # Created on every open, so a shard made before an index was added gets it too.
        for key in ("type", "owner", "key"):
            self.shard.update(UpdateOperation.create_field_index(key, PayloadSchemaType.Keyword))
        self.shard.flush()
        if people is not None:
            people.initialize_visitors()
        self.thumbs = path / "thumbs"
        self.thumbs.mkdir(exist_ok=True)
        self.pending = {}
        self.items = self.shard.scroll(ScrollRequest(limit=1000, with_payload=True,
            filter=Filter(must=[FieldCondition(key="type", match=MatchValue("item_ignore"))])))[0]
        referenced = {v["thumbnail"] for r in self.objects() for v in r.payload["views"]}
        for file in self.thumbs.glob("*.jpg"):
            if file.name not in referenced:
                file.unlink()

    def objects(self, owner: str | None = None):
        rows, offset = [], None
        while True:
            page, offset = self.shard.scroll(ScrollRequest(offset=offset, limit=1000,
                with_payload=True, filter=Filter(must=[
                    FieldCondition(key="type", match=MatchValue("object")),
                    *([FieldCondition(key="owner", match=MatchValue(owner))] if owner else [])])))
            rows.extend(page)
            if offset is None:
                return rows

    def label_map(self) -> dict[str, str]:
        displays = {}
        labels = {}
        for row in self.objects():
            owner = row.payload["owner"]
            if owner not in displays:
                person = self.people.by_visitor(owner) if self.people else None
                displays[owner] = (person or self.visitor(owner))["name" if person else "display"]
            labels[str(row.id)] = f"{displays[owner]}'s {row.payload['name']}"
        return labels

    def map_points(self, linked: Collection[str]) -> tuple[int, list[dict]]:
        """Read at most 64 object nodes, preferring the sampled evidence's linked objects."""
        fields = ["name", "created", "type"]
        query = Filter(must=[FieldCondition(key="type", match=MatchValue("object"))])
        ids = list(dict.fromkeys(linked))[:64]
        rows = {str(row.id): row.payload for row in self.shard.retrieve(ids, fields, False)
                if row.payload.get("type") == "object"} if ids else {}
        page, _ = self.shard.scroll(ScrollRequest(
            limit=64, filter=query, with_payload=fields, with_vector=False))
        for row in page:
            if len(rows) >= 64:
                break
            rows[str(row.id)] = row.payload
        return self.shard.count(CountRequest(filter=query)), [
            {"id": f"things:{ident}", "kind": "object", "label": payload["name"][:120],
             "created": payload.get("created", 0)} for ident, payload in rows.items()]

    def new_visitor(self) -> str:
        ident = str(uuid.uuid4())
        self.pending[ident] = self._guest_number()
        return ident

    def _guest_number(self) -> int:
        counter = _id("visitor-counter")
        rows = self.shard.retrieve([counter], True, False)
        number = rows[0].payload["number"] + 1 if rows else 1
        self.shard.update(UpdateOperation.upsert_points([Point(counter, {}, {"number": number})]))
        self.shard.flush()
        return number

    def visitor(self, owner: str) -> dict | None:
        rows = self.shard.retrieve([owner], True, False)
        return rows[0].payload if rows else None

    def tell(self, owner: str, name: str) -> None:
        if self.visitor(owner):
            self.shard.update(UpdateOperation.set_payload([owner], {"display": name}))
            self.shard.flush()

    def label(self, ident: str) -> str:
        rows = self.shard.retrieve([ident], True, False)
        if not rows:
            return ""
        payload = rows[0].payload
        owner = payload["owner"]
        person = self.people.by_visitor(owner) if self.people else None
        visitor = self.visitor(owner)
        display = person["name"] if person else visitor["display"]
        return f"{display}'s {payload['name']}"

    def name(self, owner: str, name: str, labels: list[str], vectors: np.ndarray,
             crops: list[np.ndarray], display: str | None = None) -> str:
        """Append distinct taught views to the owner's object, preserving its identity."""
        if self.visitor(owner) is None:
            number = self.pending.pop(owner) if owner in self.pending else self._guest_number()
            self.shard.update(UpdateOperation.upsert_points([Point(owner, {},
                {"type": "visitor", "display": display or f"Guest {number}", "number": number})]))
        existing = self.named(owner, name, [], include_ignored=True)
        ident = existing["id"] if existing else str(uuid.uuid4())
        payload = existing or {"type": "object", "owner": owner, "name": name,
                               "created": time.time(),
                               "key": " ".join(name.casefold().split()),
                               "labels": [], "turns": [], "views": []}
        payload = {k: v for k, v in payload.items() if k != "id"}
        payload["labels"] = sorted({*labels, *payload["labels"]})
        rows = self.shard.retrieve([ident], False, True)
        previous = (
            np.asarray(rows[0].vector["crops"], dtype=np.float32) if rows else np.empty((0, DIM))
        )
        self._views(ident, payload, previous, vectors[:SHOTS], crops[:SHOTS], "taught")
        return ident

    def _views(self, ident, payload, previous, vectors, crops, source):
        vectors = np.asarray(vectors, dtype=np.float32)
        previous = np.asarray(previous, dtype=np.float32)
        updated = add_vectors(previous, vectors)
        metadata = list(payload["views"])
        available = [(v, m) for v, m in zip(previous, metadata, strict=True)]
        kept = []
        for vector in updated:
            old = next((m for v, m in available if np.array_equal(v, vector)), None)
            if old is not None:
                kept.append(old)
                continue
            crop = crops[next(i for i, v in enumerate(vectors) if np.array_equal(v, vector))]
            view = str(uuid.uuid4())
            filename = f"{view}.jpg"
            h, w = crop.shape[:2]
            thumbnail = cv2.resize(crop, (max(1, round(w * 160 / max(h, w))),
                                         max(1, round(h * 160 / max(h, w)))))
            if not cv2.imwrite(str(self.thumbs / filename), thumbnail):
                raise OSError("Cannot write object thumbnail")
            kept.append({"id": view, "time": time.time(), "source": source, "thumbnail": filename})
        payload["views"] = kept
        stored = self.shard.retrieve([ident], True, False)
        if np.array_equal(previous, updated) and stored and stored[0].payload == payload:
            return False
        self.shard.update(UpdateOperation.upsert_points([
            Point(ident, {"crops": updated.tolist()}, payload)]))
        self.shard.flush()
        for old in metadata:
            if old not in kept:
                (self.thumbs / old["thumbnail"]).unlink(missing_ok=True)
        return any(not any(np.array_equal(v, old) for old in previous) for v in updated)

    def add_view(self, ident: str, vector: np.ndarray, crop: np.ndarray,
                 source: str = "window") -> bool:
        rows = self.shard.retrieve([ident], True, True)
        if not rows:
            return False
        row = rows[0]
        return self._views(ident, row.payload, np.asarray(row.vector["crops"], dtype=np.float32),
                           vector[None], [crop], source)

    def remove_view(self, ident: str, view: str) -> bool:
        """Remove the matching vector, metadata, and thumbnail, or forget the final view."""
        rows = self.shard.retrieve([ident], True, True)
        if not rows or rows[0].payload.get("type") != "object":
            return False
        row = rows[0]
        metadata = row.payload["views"]
        index = next((i for i, v in enumerate(metadata) if v["id"] == view), None)
        if index is None:
            return False
        if len(metadata) == 1:
            self.forget(ident)
            return True
        removed = metadata[index]
        payload = {**row.payload, "views": metadata[:index] + metadata[index + 1:]}
        vectors = row.vector["crops"]
        self.shard.update(UpdateOperation.upsert_points([
            Point(ident, {"crops": vectors[:index] + vectors[index + 1:]}, payload)]))
        self.shard.flush()
        self.remove_thumbnails([removed["thumbnail"]])
        return True

    def link(self, ident: str, turn: int) -> None:
        rows = self.shard.retrieve([ident], True, False)
        if rows:
            self.shard.update(UpdateOperation.set_payload(
                [ident], {"turns": rows[0].payload["turns"] + [turn]}))
            self.shard.flush()

    def named(self, owner: str, name: str, labels: Collection[str],
              include_ignored: bool = False) -> dict | None:
        key = " ".join(name.casefold().split())
        rows = self.shard.scroll(ScrollRequest(limit=1, with_payload=True, filter=Filter(
            must=[FieldCondition(key="owner", match=MatchValue(owner)),
                  FieldCondition(key="key", match=MatchValue(key))])))[0]
        hidden = set() if include_ignored else self.hidden_ids()
        found = next((r for r in rows if str(r.id) not in hidden), None)
        if found is None and labels:
            found = next((r for r in self.objects(owner) if str(r.id) not in hidden and
                          set(r.payload["labels"]) & set(labels)), None)
        return {**found.payload, "id": str(found.id)} if found else None

    def labels(self) -> set[str]:
        return {label for r in self.objects() for label in r.payload["labels"]}

    def visual_links(self, skip: Collection[str] = ()) -> dict[str, list[int]]:
        return {
            str(r.id): r.payload["turns"]
            for r in self.objects()
            if not set(r.payload["labels"]) & set(skip) and str(r.id) not in self.hidden_ids()
        }

    def score(self, crop: np.ndarray, ident: str | None = None) -> tuple[str, float] | None:
        hits = self.shard.query(QueryRequest(
            limit=1, query=Query.Nearest([crop.tolist()], using="crops"), with_payload=False,
            filter=Filter(must=[FieldCondition(key="type", match=MatchValue("object")),
                               *([HasIdCondition({ident})] if ident else [])],
                          must_not=[HasIdCondition(self.hidden_ids())]
                          if self.hidden_ids() else None)))
        return (str(hits[0].id), hits[0].score) if hits else None

    def _delete(self, rows, extra=()):
        ids = {str(r.id) for r in rows}
        turns = [turn for r in rows for turn in r.payload["turns"]]
        thumbnails = [v["thumbnail"] for r in rows for v in r.payload["views"]]
        rules = [r.id for r in self.items if ids & set(r.payload.get("excludes", []))]
        self.remove_thumbnails(thumbnails)
        self.shard.update(UpdateOperation.delete_points([*ids, *extra, *rules]))
        self.shard.flush()
        self.items = (
            self.shard.retrieve([r.id for r in self.items], True, False) if self.items else []
        )
        return turns, thumbnails

    def remove_thumbnails(self, thumbnails: list[str]) -> None:
        for thumbnail in thumbnails:
            (self.thumbs / thumbnail).unlink(missing_ok=True)

    def forget(self, ident: str) -> list:
        turns, _ = self._delete(self.shard.retrieve([ident], True, False))
        return turns

    def forget_visitor(self, owner: str) -> tuple[list[str], list, list[str]]:
        """Remove objects and the visitor after the caller deletes their linked evidence."""
        rows = self.objects(owner)
        turns, thumbnails = self._delete(rows, [owner])
        self.pending.pop(owner, None)
        return [str(r.id) for r in rows], turns, thumbnails

    def ignore(self, labels: Collection[str], on: bool) -> None:
        """Start (`on`) or stop ignoring tracks with `labels`: one rule point per label."""
        ids = [_id(f"ignore:{label}") for label in labels]
        self.shard.update(UpdateOperation.upsert_points(
            [Point(i, {}, {"ignore": label}) for i, label in zip(ids, labels, strict=True)])
            if on else UpdateOperation.delete_points(ids))
        self.shard.flush()

    def ignored(self) -> set[str]:
        found = self.shard.scroll(ScrollRequest(limit=1000, with_payload=["ignore"], filter=Filter(
            must=[FieldCondition(key="ignore", is_empty=False)])))[0]
        return {r.payload["ignore"] for r in found}

    def preferences(self) -> list[dict]:
        return [{"id": str(r.id), "title": r.payload["title"]} for r in self.items]

    def hidden_ids(self) -> set[str]:
        return {n for r in self.items for n in r.payload.get("excludes", [])}

    def descriptors(self, ident: str) -> np.ndarray:
        rows = self.shard.retrieve([ident], False, True)
        return np.asarray(rows[0].vector["crops"], dtype=np.float32)

    def excluded(self, crop: np.ndarray) -> str | None:
        if not self.items:
            return None
        hits = self.shard.query(QueryRequest(limit=1,
            query=Query.Nearest([crop.tolist()], using="crops"), with_payload=False,
            filter=Filter(must=[FieldCondition(key="type", match=MatchValue("item_ignore"))])))
        return str(hits[0].id) if hits and hits[0].score >= settings.match else None

    def ignore_item(self, title: str, crops: np.ndarray) -> str:
        """Persist descriptors only, separately from names, media, and category rules."""
        rows = self.shard.scroll(ScrollRequest(limit=1000, with_payload=["name"],
            with_vector=True, filter=Filter(must=[FieldCondition(key="name", is_empty=False)])))[0]
        excludes = [str(r.id) for r in rows
                    if np.max(crops @ np.asarray(r.vector["crops"]).T) >= settings.match]
        ident = str(uuid.uuid4())
        self.shard.update(UpdateOperation.upsert_points([Point(ident,
            {"crops": add_vectors(np.empty((0, DIM)), crops).tolist()},
            {"type": "item_ignore", "title": title, "excludes": excludes})]))
        self.shard.flush()
        self.items = self.shard.retrieve([*[r.id for r in self.items], ident], True, False)
        return ident

    def restore_item(self, ident: str) -> bool:
        if ident not in {str(r.id) for r in self.items}:
            return False
        self.shard.update(UpdateOperation.delete_points([ident]))
        self.shard.flush()
        self.items = [r for r in self.items if str(r.id) != ident]
        return True


def _carried(shard: EdgeShard) -> list[Point]:
    """The records of an old shard that hold no crop vectors: visitors, their guest counter, and
    category Ignore rules. Objects and item rules hold the old encoder's vectors and stay behind."""
    rows, offset = [], None
    while True:
        page, offset = shard.scroll(ScrollRequest(offset=offset, limit=1000, with_payload=True))
        rows.extend(page)
        if offset is None:
            break
    counter = _id("visitor-counter")
    return [Point(r.id, {}, r.payload) for r in rows
            if r.payload.get("type") == "visitor" or "ignore" in r.payload or str(r.id) == counter]


def _id(key: str) -> str:
    key = " ".join(key.replace("’", "'").casefold().split())
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"thing:{key}"))


# Display names preserve explicit wording; detector categories remain separate aliases.
_WORD = r"[a-z][a-z'-]*"
_THING = rf"(?P<thing>{_WORD}(?: {_WORD})*)"
_STOP = r"(?:from|now|again|here|is|are|was|were|has|have|do|does|did|please)\b"
_REFERENCE = rf"(?P<thing>{_WORD}(?: (?!{_STOP}){_WORD})*)"
_OWNED = rf"(?P<thing>{_WORD}(?: {_WORD})*'s (?:{_WORD})(?: {_WORD})*)"
_NAMING = [re.compile(p, re.I) for p in (
    rf"^\W*(?:and |so |ok(?:ay)?,? )?(?:this|that|here)(?: one)?(?:'s| is)\s+my\s+{_THING}\W*$",
    rf"^\W*(?:and )?(?:this|that)\s+{_THING}\s+(?:is mine|belongs to me)\W*$",
    rf"\b(?:remember|track)\s+(?:this|that)(?:\s+[a-z-]+)?\s+as\s+my\s+{_THING}\W*$")]
# "Track this" with no name: the robot asks for it, and name_slot reads the next line.
_UNNAMED = re.compile(
    r"^\W*(?:(?:and|so|please|ok(?:ay)?),? )?(?:(?:remember|track)\s+(?:this|that)(?:\s+[a-z-]+)?|"
    r"(?:this|that)(?: one)?(?:'s| is) mine)\W*$", re.I)
_SLOT = re.compile(rf"^\W*(?:(?:as|call it|it's|it is|this is|that's|that is)\s+)?(?:my\s+)?"
                   rf"{_THING}\W*$", re.I)
# "Ignore that" is the whole line: a longer line ("ignore that, what do you see?") is no command.
_IGNORE = re.compile(r"^\W*(?:(?:edgy|please)\W+)*(?:ignore|(?:do not|don't|stop) track(?:ing)?)"
                     r"\s+(?:(?:this|that)(?:\s+(?:thing|object|item|one))?|it)(?:\W+please)?\W*$",
                     re.I)
_DECLINE = re.compile(r"^\W*(?:no|nope|nothing|never ?mind|cancel|stop|skip|forget it)\b", re.I)
_OWNED_NAMING = re.compile(rf"^\W*(?:this|that)(?:'s| is)\s+{_OWNED}\W*$", re.I)
_FORGET = re.compile(rf"(?:about\s+)?my\s+{_REFERENCE}", re.I)  # after the deletion verb
_OWNED_FORGET = re.compile(rf"{_OWNED}\W*$", re.I)
_MY = re.compile(rf"\bmy\s+{_REFERENCE}\b", re.I)
_OWNED_QUERY = re.compile(
    rf"^\W*(?:where (?:is|are)|(?:have|did) you (?:see|seen)|"
    rf"do you (?:still )?(?:remember|know|recall)|(?:is|are) (?:this|that)|"
    rf"and|what about)\s+{_OWNED}\W*$", re.I)
_MINE = re.compile(rf"\b(?:this|that|it)(?:\s+{_THING})?\s+(?:is\s+)?mine\b", re.I)
_THIS = re.compile(r"\b(?:is|are)\s+(?:this|that|it|these|those)\b", re.I)
_WHERE = re.compile(r"\b(?:where|which)\b", re.I)
_SEEN = re.compile(r"\b(?:see|seen|saw|spot\w*|notic\w*)\b", re.I)
_REMEMBER = re.compile(r"\b(?:remember|know|recall)\b|"
                       r"^\W*(?:and|what about)\s+my\s+[a-z-]+(?: [a-z-]+)?\W*$", re.I)


def _thing(text: str, vocab: Collection[str]) -> tuple[str, list[str]]:
    """The spoken display name and its detector-category aliases."""
    return " ".join(text.split()), sorted(kinds(text, vocab))


def _identity(text: str) -> bool:
    return bool(re.search(r"\b(?:face|name)\b", text, re.I))


def command(text: str, vocab: Collection[str]) -> tuple[str, str, list[str]] | None:
    """("name" | "forget", name, labels) for a command about the visitor's things, else None;
    ("teach", "", []) for "track this" without a name; ("ignore", "", []) for "ignore that"."""
    text = text.replace("’", "'")
    if _IGNORE.search(text):
        return "ignore", "", []
    if _UNNAMED.search(text):
        return "teach", "", []
    if m := next((x for p in _NAMING if (x := p.search(text))), None):
        return None if _identity(m["thing"]) else ("name", *_thing(m["thing"], vocab))
    if (m := _OWNED_NAMING.search(text)) and not _identity(m["thing"]):
        return "name", *_thing(m["thing"], vocab)
    if (rest := deletion_target(text)) is not None and (
            m := _FORGET.match(rest) or _OWNED_FORGET.match(rest)):
        if _identity(m["thing"]):
            return None  # "forget my face" is an identity request (robot/people.py)
        return "forget", *_thing(m["thing"], vocab)
    return None


def name_slot(text: str, vocab: Collection[str]) -> tuple[str, list[str]] | None:
    """The name in the line that answers "What should I call it?" ("my collagen", "as my
    collagen", "call it collagen"), or None for a question, a command, or a refusal."""
    text = text.replace("’", "'")
    if is_question(text) or command(text, vocab) or question(text, vocab) or \
            deletion_target(text) is not None or request(text) or _DECLINE.search(text):
        return None
    m = _SLOT.search(text)
    return _thing(m["thing"], vocab) if m and len(m["thing"].split()) <= 4 and \
        not _identity(m["thing"]) else None


def question(text: str, vocab: Collection[str]) -> tuple[str, str, list[str]] | None:
    """("this" | "where" | "seen" | "remember", name, labels) for a question about one of
    the visitor's things, else None."""
    text = text.replace("’", "'")
    if not (is_question(text) or re.match(r"^\W*(?:and|what about)\b", text, re.I)):
        return None
    if (m := _MINE.search(text)) and m["thing"]:
        found = _thing(m["thing"], vocab)
        return ("this", *found) if found[1] else None
    if not (m := _MY.search(text) or _OWNED_QUERY.search(text)) or _identity(m["thing"]):
        return None
    name, labels = _thing(m["thing"], vocab)
    for mode, pattern in (("this", _THIS), ("where", _WHERE), ("seen", _SEEN),
                          ("remember", _REMEMBER)):
        if pattern.search(text):
            return mode, name, labels
    return None


def plural(name: str) -> str:
    return name if name.endswith("s") else f"{name}es" if name.endswith(("ch", "sh")) else \
        f"{name}s"


def _naming(labels: Collection[str]) -> re.Pattern | None:
    """A pattern for the words of ignored kinds ("armchair" too), or None for no kinds."""
    words = {w for label in labels for g in [kind_of(label)] for w in [label, g]}
    return re.compile(r"\w*(?:" + "|".join(map(re.escape, words)) + r")(?:e?s)?\b",
                      re.I) if words else None


def mentions(text: str, labels: Collection[str]) -> bool:
    """Whether `text` (a statement the visitor made) names one of the ignored kinds."""
    return bool((named := _naming(labels)) and named.search(text))


def unmention(caption: str, labels: Collection[str]) -> str:
    """`caption` without the clauses that name an ignored kind: a stored turn caption must not
    bring back what the visitor asked the robot to ignore."""
    if (named := _naming(labels)) is None:
        return caption
    kept = []
    for s in re.split(r"(?<=[.\n])\s*", caption):
        head, colon, body = s.rpartition(":")
        parts = [p.strip(" .") for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", body)]
        if parts := [p for p in parts if p and not named.search(p)]:
            kept.append(f"{head}{colon} " * bool(colon) + ", ".join(parts) + "." * ("." in s))
    return " ".join(kept)


def _selftest() -> None:
    import tempfile
    vocab = {"phone", "cup", "mug", "teddy bear", "plush toy", "toy", "chair", "bottle", "laptop",
             "cat", "keys", "face", "camera"}
    c = lambda t: command(t, vocab)  # noqa: E731
    assert c("This is my phone.") == ("name", "phone", ["phone"])
    assert c("And this is my laptop.") == ("name", "laptop", ["laptop"])
    assert c("Here's my mug!") == ("name", "mug", ["cup", "mug"])
    assert c("This teddy is mine.")[:2] == ("name", "teddy")
    assert c("Please remember this cup as my coffee cup.")[:2] == ("name", "coffee cup")
    assert c("This is my lucky charm.") == ("name", "lucky charm", []), \
        "an unknown thing names any object in view"
    assert c("Please forget my laptop.") == ("forget", "laptop", ["laptop"])
    assert c("Delete my cup from your memory.")[:2] == ("forget", "cup")
    assert c("Forget my face.") is None and c("Forget me.") is None
    assert c("Ignore the chair.") is None and c("Stop ignoring chairs.") is None, \
        "ignore and restore are Mac UI actions"
    assert c("My favorite color is green.") is None and c("I like this cup.") is None
    q = lambda t: question(t, vocab)  # noqa: E731
    assert q("Where is my phone?") == ("where", "phone", ["phone"])
    assert q("Which one is my teddy bear?")[:2] == ("where", "teddy bear")
    assert q("Have you seen my phone?")[:2] == ("seen", "phone")
    assert q("Is this my phone?")[:2] == ("this", "phone")
    assert q("Is this phone mine?")[:2] == ("this", "phone")
    assert q("Do you still remember my teddy bear?")[:2] == ("remember", "teddy bear")
    assert q("And my laptop?")[:2] == ("remember", "laptop")
    assert q("Are you still ignoring chairs?") is None
    assert q("What's my cat's name?") is None and q("Do you remember my cat's name?") is None
    assert q("Do you remember my favorite color?") == ("remember", "favorite color", []), \
        "an unknown thing: the caller answers only if something has that name"
    assert q("When is my talk?") is None and q("Where am I from?") is None
    assert q("Is it mine?") is None, "no kind named"
    assert unmention("Main object: a red mug. Around it: a chair, a lamp, and an armchair.",
                     ["chair"]) == "Main object: a red mug. Around it: a lamp."
    assert unmention("Main object: a wooden chair.\nAround it: a rug.", ["chair"]) == \
        "Around it: a rug."
    assert unmention("A cupboard and a cup.", ["cup"]) == "A cupboard."
    assert mentions("My armchair is comfy.", ["chair"]) and not mentions("I like tea.", ["chair"])
    assert not mentions("A chair.", [])
    OWNER = str(uuid.uuid4())
    test_crops = lambda vectors: [np.full((12, 20, 3), 90, np.uint8) for _ in vectors]  # noqa: E731
    def object_id(things, owner, name):
        row = things.named(owner, name, [], include_ignored=True)
        return row["id"] if row else str(uuid.uuid4())
    with tempfile.TemporaryDirectory() as tmp:
        things = Things(Path(tmp))
        rng = np.random.default_rng(0)
        mine, other = _unit(rng.normal(size=(2, DIM)))
        things.name(
            OWNER, "phone", ["phone"], np.array([mine, mine]), test_crops(np.array([mine, mine]))
        )
        things.link(object_id(things, OWNER, 'phone'), 7)
        things.ignore(["chair"], True)
        assert things.score(mine)[1] > 0.99 and things.score(other)[1] < 0.2
        things.name(OWNER, 'cup', ['cup'], np.array([other]), test_crops(np.array([other])))
        assert (
            things.score(other)[0] == object_id(things, OWNER, "cup")
            and things.score(other, object_id(things, OWNER, "phone"))[1] < 0.2
        ), "a requested object is scored directly"
        things.forget(object_id(things, OWNER, 'cup'))
        assert things.named(OWNER, 'cup', ['cup']) is None
        assert things.named(OWNER, 'mobile', ['phone'])["name"] == "phone", "found by its label"
        assert things.named(OWNER, 'lucky charm', []) is None
        assert things.labels() == {"phone"}, "rule points are not named objects"
        things.shard.close()
        things = Things(Path(tmp))
        assert things.ignored() == {"chair"} and things.named(OWNER, 'phone', [])["turns"] == [7], \
            "names and rules survive a restart"
        assert (
            things.forget(object_id(things, OWNER, "phone")) == [7]
            and things.named(OWNER, "phone", ["phone"]) is None
        )
        things.ignore(["chair"], False)
        assert things.ignored() == set() and things.labels() == set()
    if MODEL.exists():
        img = cv2.imread(str(Path(__file__).parent.parent / "eval/dev/images/m2-phones.jpg"))
        v = Crops()([img[200:400, 100:300], img[200:400, 100:300], img[:100, :100]])
        assert v.shape == (3, DIM) and abs(float(v[0] @ v[1]) - 1) < 1e-4
        assert float(v[0] @ v[2]) < settings.match, "a phone crop and a corner of the room differ"
    print("selftest ok")


if __name__ == "__main__":
    _selftest()
