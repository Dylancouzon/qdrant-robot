"""Named objects and ignored kinds, in their own Qdrant Edge shard: "this is my phone" stores one
point per name with DINOv2-small crop vectors as a multivector (MaxSim), and "ignore the chair"
stores a rule point with no vector. Both survive a restart; parsing and answers run in code."""
import re
import uuid
from collections.abc import Collection
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    HasIdCondition,
    MultiVectorComparator,
    MultiVectorConfig,
    Point,
    Query,
    QueryRequest,
    ScrollRequest,
    UpdateOperation,
)

from robot.config import MODELS, SHARED
from robot.memory import deletion_target, is_question, kind_of, kinds

MODEL = MODELS / "dinov2-small/model.onnx"
DIM = 768  # DINOv2-small CLS and mean patch token, each unit length, concatenated
SHOTS = 3  # crops of the named track, a third of a second apart
VIEWS = 3  # maximum diverse crops retained across verified explicit reteaching turns
# The highest score of another object, of any kind, on half the bake-off instances; on the
# other half: zero false matches in 625 same-kind and 1,400 other-kind crops, true matches
# 15/22 phones, 15/35 teddy bears (bench/reid.py,
# bench/results/2026-10-08-reid-1791502259.jsonl). Below it, never "yours".
MATCH = 0.822
_MEAN, _STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])


class Crops:
    """Crop vectors: DINOv2-small at 224x224 on the GPU when present, the crop padded square."""

    def __init__(self):
        cuda = "CUDAExecutionProvider" in ort.get_available_providers()
        providers = ([("CUDAExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"})]
                     if cuda else ["CPUExecutionProvider"])
        self.sess = ort.InferenceSession(str(MODEL), providers=providers)

    def __call__(self, crops: list[np.ndarray]) -> np.ndarray:
        x = np.stack([_square(c) for c in crops])
        t = self.sess.run(None, {"pixel_values": x})[0]
        cls, patches = t[:, 0], t[:, 1:].mean(1)
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


def diverse(crops: np.ndarray, current: int, limit: int = VIEWS) -> np.ndarray:
    """Keep distinct original/current anchors, then the farthest remaining cosine views."""
    unique, anchors = [], []
    for i, vector in enumerate(crops):
        at = next((j for j, old in enumerate(unique) if np.array_equal(old, vector)), None)
        if at is None:
            at = len(unique)
            unique.append(vector)
        if i in (0, current) and at not in anchors:
            anchors.append(at)
    vectors = np.asarray(unique, dtype=np.float32)
    unit = _unit(vectors)
    chosen = anchors[:limit]
    while len(chosen) < min(limit, len(vectors)):
        remaining = [i for i in range(len(vectors)) if i not in chosen]
        chosen.append(max(remaining, key=lambda i: float((1 - unit[i] @ unit[chosen].T).min())))
    return vectors[chosen]


class Things:
    def __init__(self, root: Path = SHARED / "memory"):
        path = root / "things"
        if path.exists():
            self.shard = EdgeShard.load(str(path))
        else:
            path.mkdir(parents=True)
            self.shard = EdgeShard.create(str(path), EdgeConfig(vectors={"crops": EdgeVectorParams(
                size=DIM, distance=Distance.Cosine,
                multivector_config=MultiVectorConfig(MultiVectorComparator.MaxSim))}))
        self.items = self.shard.scroll(ScrollRequest(limit=1000, with_payload=True,
            filter=Filter(must=[FieldCondition(key="type", match=MatchValue("item_ignore"))])))[0]

    def name(self, name: str, labels: list[str], crops: np.ndarray) -> str:
        """Keep diverse explicitly taught views when the current crop verifies the exact name.
        Otherwise replace it with the current crop, excluding possibly older physical objects.
        Preserve the first casing, aliases, and deletion links."""
        existing = self.shard.retrieve([_id(name)], True, True)
        current = 0
        if existing:
            old = existing[0]
            name = old.payload["name"]
            labels = sorted({*labels, *old.payload["labels"]})
            hit = self.score(crops[0], name)
            if hit and hit[1] >= MATCH:
                previous = np.asarray(old.vector["crops"], dtype=np.float32)
                current = len(previous)
                crops = np.concatenate([previous, crops[:SHOTS]])
            else:
                crops = crops[:1]
        self.shard.update(UpdateOperation.upsert_points([Point(
            _id(name), {"crops": diverse(crops if current else crops[:SHOTS], current).tolist()},
            {"name": name, "labels": labels, "turns": self._turns(name)})]))
        self.shard.flush()
        return name

    def _turns(self, name: str) -> list:
        found = self.shard.retrieve([_id(name)], ["turns"], False)
        return found[0].payload["turns"] if found else []

    def link(self, name: str, turn: int) -> None:
        """Record the stored turn that named `name`, so forget() deletes it too."""
        if self.shard.retrieve([_id(name)], False, False):
            self.shard.update(UpdateOperation.set_payload(
                [_id(name)], {"turns": self._turns(name) + [turn]}))
            self.shard.flush()

    def named(self, name: str, labels: Collection[str],
              include_ignored: bool = False) -> dict | None:
        """The payload of the object called `name`, else of one named with one of `labels`
        ("my watch" finds the watch the visitor called "my grandmother's")."""
        found = self.shard.retrieve([_id(name)], True, False)
        if not found and labels:
            found = self.shard.scroll(ScrollRequest(limit=1, with_payload=True, filter=Filter(
                must=[FieldCondition(key="name", is_empty=False),
                      FieldCondition(key="labels", match=MatchAny(list(labels)))],
                must_not=[HasIdCondition({_id(n) for n in self.hidden_names()})]
                if self.hidden_names() and not include_ignored else None)))[0]
        if found and not include_ignored and found[0].payload["name"] in self.hidden_names():
            return None
        return found[0].payload if found else None

    def labels(self) -> set[str]:
        """Every label some named object has (none: no new track is embedded)."""
        found = self.shard.scroll(ScrollRequest(limit=1000, with_payload=["labels"], filter=Filter(
            must=[FieldCondition(key="name", is_empty=False)])))[0]
        return {label for r in found for label in r.payload["labels"]}

    def visual_links(self, skip: Collection[str] = ()) -> dict[str, list[int]]:
        """Named evidence, including legacy links, excluding ignored object classes."""
        rows = self.shard.scroll(ScrollRequest(limit=1000, with_payload=True, filter=Filter(
            must=[FieldCondition(key="name", is_empty=False)],
            must_not=[FieldCondition(key="labels", match=MatchAny(list(skip)))]
            if skip else None)))[0]
        return {r.payload["name"]: r.payload.get("turns", []) for r in rows
                if r.payload["name"] not in self.hidden_names()}

    def score(self, crop: np.ndarray, name: str | None = None) -> tuple[str, float] | None:
        """(name, MaxSim score) of the named object nearest `crop` (or of `name`), whatever
        its label: the detector's labels are hints (D61), one object can get several."""
        hits = self.shard.query(QueryRequest(
            limit=1, query=Query.Nearest([crop.tolist()], using="crops"), with_payload=["name"],
            filter=Filter(must=[FieldCondition(key="name", is_empty=False),
                               *([HasIdCondition({_id(name)})] if name else [])],
                          must_not=[HasIdCondition({_id(n) for n in self.hidden_names()})]
                          if self.hidden_names() else None)))
        return (hits[0].payload["name"], hits[0].score) if hits else None

    def forget(self, name: str) -> list:
        """Delete the named object; returns the turns that named it, for the caller to delete."""
        turns = self._turns(name)
        self.shard.update(UpdateOperation.delete_points([_id(name)]))
        self.shard.flush()
        return turns

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

    def hidden_names(self) -> set[str]:
        return {n for r in self.items for n in r.payload.get("excludes", [])}

    def descriptors(self, name: str) -> np.ndarray:
        rows = self.shard.retrieve([_id(name)], False, True)
        return np.asarray(rows[0].vector["crops"], dtype=np.float32)

    def excluded(self, crop: np.ndarray) -> str | None:
        if not self.items:
            return None
        hits = self.shard.query(QueryRequest(limit=1,
            query=Query.Nearest([crop.tolist()], using="crops"), with_payload=False,
            filter=Filter(must=[FieldCondition(key="type", match=MatchValue("item_ignore"))])))
        return str(hits[0].id) if hits and hits[0].score >= MATCH else None

    def ignore_item(self, title: str, crops: np.ndarray) -> str:
        """Persist descriptors only, separately from names, media, and category rules."""
        rows = self.shard.scroll(ScrollRequest(limit=1000, with_payload=["name"],
            with_vector=True, filter=Filter(must=[FieldCondition(key="name", is_empty=False)])))[0]
        excludes = [r.payload["name"] for r in rows
                    if np.max(crops @ np.asarray(r.vector["crops"]).T) >= MATCH]
        ident = str(uuid.uuid4())
        self.shard.update(UpdateOperation.upsert_points([Point(ident,
            {"crops": diverse(crops, 0).tolist()},
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
    ("teach", "", []) for "track this" without a name."""
    text = text.replace("’", "'")
    if _UNNAMED.search(text):
        return "teach", "", []
    if m := next((x for p in _NAMING if (x := p.search(text))), None):
        return None if _identity(m["thing"]) else ("name", *_thing(m["thing"], vocab))
    if (m := _OWNED_NAMING.search(text)) and not _identity(m["thing"]) and \
            kinds(m["thing"], vocab):
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
    if is_question(text) or command(text, vocab) or question(text, vocab) or _DECLINE.search(text):
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
    with tempfile.TemporaryDirectory() as tmp:
        things = Things(Path(tmp))
        rng = np.random.default_rng(0)
        mine, other = _unit(rng.normal(size=(2, DIM)))
        things.name("phone", ["phone"], np.array([mine, mine]))
        things.link("phone", 7)
        things.ignore(["chair"], True)
        assert things.score(mine)[1] > 0.99 and things.score(other)[1] < 0.2
        things.name("cup", ["cup"], np.array([other]))
        assert things.score(other)[0] == "cup" and things.score(other, "phone")[1] < 0.2, \
            "a requested object is scored directly"
        things.forget("cup")
        assert things.named("cup", ["cup"]) is None
        assert things.named("mobile", ["phone"])["name"] == "phone", "found by its label"
        assert things.named("lucky charm", []) is None
        assert things.labels() == {"phone"}, "rule points are not named objects"
        things.shard.close()
        things = Things(Path(tmp))
        assert things.ignored() == {"chair"} and things.named("phone", [])["turns"] == [7], \
            "names and rules survive a restart"
        assert things.forget("phone") == [7] and things.named("phone", ["phone"]) is None
        things.ignore(["chair"], False)
        assert things.ignored() == set() and things.labels() == set()
    if MODEL.exists():
        img = cv2.imread(str(Path(__file__).parent.parent / "eval/dev/images/m2-phones.jpg"))
        v = Crops()([img[200:400, 100:300], img[200:400, 100:300], img[:100, :100]])
        assert v.shape == (3, DIM) and abs(float(v[0] @ v[1]) - 1) < 1e-4
        assert float(v[0] @ v[2]) < MATCH, "a phone crop and a corner of the room differ"
    print("selftest ok")


if __name__ == "__main__":
    _selftest()
