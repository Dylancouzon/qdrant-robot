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
    MultiVectorComparator,
    MultiVectorConfig,
    Point,
    Query,
    QueryRequest,
    ScrollRequest,
    UpdateOperation,
)

from robot.config import MODELS, SHARED
from robot.memory import is_question, kind_of, kinds

MODEL = MODELS / "dinov2-small/model.onnx"
DIM = 768  # DINOv2-small CLS and mean patch token, each unit length, concatenated
SHOTS = 3  # crops of the named track, a third of a second apart
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

    def name(self, name: str, labels: list[str], crops: np.ndarray) -> None:
        """Store `name` (one point per name: naming it again replaces the crops) for an object
        with detector `labels`, from its crop vectors; the turns that named it are kept."""
        self.shard.update(UpdateOperation.upsert_points([Point(
            _id(name), {"crops": crops[:SHOTS].tolist()},
            {"name": name, "labels": labels, "turns": self._turns(name)})]))
        self.shard.flush()

    def _turns(self, name: str) -> list:
        found = self.shard.retrieve([_id(name)], ["turns"], False)
        return found[0].payload["turns"] if found else []

    def link(self, name: str, turn: int) -> None:
        """Record the stored turn that named `name`, so forget() deletes it too."""
        if self.shard.retrieve([_id(name)], False, False):
            self.shard.update(UpdateOperation.set_payload(
                [_id(name)], {"turns": self._turns(name) + [turn]}))
            self.shard.flush()

    def named(self, name: str, labels: Collection[str]) -> dict | None:
        """The payload of the object called `name`, else of one named with one of `labels`
        ("my watch" finds the watch the visitor called "my grandmother's")."""
        found = self.shard.retrieve([_id(name)], True, False)
        if not found and labels:
            found = self.shard.scroll(ScrollRequest(limit=1, with_payload=True, filter=Filter(
                must=[FieldCondition(key="labels", match=MatchAny(list(labels)))])))[0]
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
        return {r.payload["name"]: r.payload.get("turns", []) for r in rows}

    def score(self, crop: np.ndarray, name: str | None = None) -> tuple[str, float] | None:
        """(name, MaxSim score) of the named object nearest `crop` (or of `name`), whatever
        its label: the detector's labels are hints (D61), one object can get several."""
        hits = self.shard.query(QueryRequest(
            limit=1, query=Query.Nearest([crop.tolist()], using="crops"), with_payload=["name"],
            filter=Filter(must=[FieldCondition(key="name", match=MatchValue(name))])
            if name else None))
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


def _id(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"thing:{key}"))


# Commands and questions about the visitor's things. A thing is one or two words after "my"
# (or before "is mine"); a detector kind ("mug" names cup and mug) or any other word.
_THING = r"(?P<thing>[a-z][a-z-]*(?: [a-z][a-z-]*)?)"
_NAMING = [re.compile(p, re.I) for p in (
    rf"^\W*(?:and |so |ok(?:ay)?,? )?(?:this|that|here)(?: one)?(?:'s| is)\s+my\s+{_THING}\W*$",
    rf"^\W*(?:and )?(?:this|that)\s+{_THING}\s+(?:is mine|belongs to me)\W*$",
    rf"\b(?:remember|track)\s+(?:this|that)(?:\s+[a-z-]+)?\s+as\s+my\s+{_THING}\W*$")]
_FORGET = re.compile(rf"\b(?:forget|delete|erase|remove)\b(?:\s+about)?\s+my\s+{_THING}", re.I)
_UNIGNORE = re.compile(r"\b(?:stop|quit|no longer|don'?t|do not)\s+ignor\w*|\bunignore\b|"
                       r"\bnotice\b.*\bagain\b", re.I)
_IGNORE = re.compile(r"\b(?:ignore|stop (?:remembering|noticing|tracking|storing)|"
                     r"(?:don'?t|do not) (?:remember|notice|track|store))\b", re.I)
_IGNORING = re.compile(r"\bignoring\b", re.I)
_MY = re.compile(rf"\bmy\s+{_THING}\b(?!')", re.I)  # not "my dog's name"
_MINE = re.compile(rf"\b(?:this|that|it)(?:\s+{_THING})?\s+(?:is\s+)?mine\b", re.I)
_THIS = re.compile(r"\b(?:is|are)\s+(?:this|that|it|these|those)\b", re.I)
_WHERE = re.compile(r"\b(?:where|which)\b", re.I)
_SEEN = re.compile(r"\b(?:see|seen|saw|spot\w*|notic\w*)\b", re.I)
_REMEMBER = re.compile(r"\b(?:remember|know|recall)\b|"
                       r"^\W*(?:and|what about)\s+my\s+[a-z-]+(?: [a-z-]+)?\W*$", re.I)


def _thing(text: str, vocab: Collection[str]) -> tuple[str, list[str]]:
    """(name, detector labels) of a thing's words: a detector kind is named by its first word
    ("mug" -> "cup"); other words are their own name, with no labels."""
    labels = kinds(text, vocab)
    if labels:
        return kind_of(sorted(labels)[0]), sorted(labels)
    return text.lower(), []


def command(text: str, vocab: Collection[str]) -> tuple[str, str, list[str]] | None:
    """("name" | "forget" | "ignore" | "unignore", name, labels) for a command about the
    visitor's things, else None."""
    text = text.replace("’", "'")
    if m := next((x for p in _NAMING if (x := p.search(text))), None):
        return "name", *_thing(m["thing"], vocab)
    if m := _FORGET.search(text):
        if m["thing"].split()[0].lower() in ("face", "name"):
            return None  # "forget my face" is an identity request (robot/people.py)
        return "forget", *_thing(m["thing"], vocab)
    if is_question(text) or re.search(r"\bmy\b", text, re.I):
        return None
    for kind, pattern in (("unignore", _UNIGNORE), ("ignore", _IGNORE)):
        if pattern.search(text) and (labels := sorted(kinds(text, vocab))):
            return kind, kind_of(labels[0]), labels
    return None


def question(text: str, vocab: Collection[str]) -> tuple[str, str, list[str]] | None:
    """("this" | "where" | "seen" | "remember" | "ignoring", name, labels) for a question
    about one of the visitor's things or an ignore rule, else None."""
    text = text.replace("’", "'")
    if not (is_question(text) or re.match(r"^\W*(?:and|what about)\b", text, re.I)):
        return None
    if _IGNORING.search(text) and (labels := sorted(kinds(text, vocab))):
        return "ignoring", kind_of(labels[0]), labels
    if (m := _MINE.search(text)) and m["thing"]:
        found = _thing(m["thing"], vocab)
        return ("this", *found) if found[1] else None
    if not (m := _MY.search(text)):
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
    assert c("Here's my mug!") == ("name", "cup", ["cup", "mug"])
    assert c("This teddy is mine.")[:2] == ("name", "teddy bear")
    assert c("Please remember this cup as my coffee cup.")[:2] == ("name", "cup")
    assert c("This is my lucky charm.") == ("name", "lucky charm", []), \
        "an unknown thing names any object in view"
    assert c("Please forget my laptop.") == ("forget", "laptop", ["laptop"])
    assert c("Delete my cup from your memory.")[:2] == ("forget", "cup")
    assert c("Forget my face.") is None and c("Forget me.") is None
    assert c("Ignore the chair.") == ("ignore", "chair", ["chair"])
    assert c("Please don't remember bottles.") == ("ignore", "bottle", ["bottle"])
    assert c("You can stop ignoring chairs now.") == ("unignore", "chair", ["chair"])
    assert c("Ignore my phone.") is None and c("Ignore that.") is None
    assert c("My favorite color is green.") is None and c("I like this cup.") is None
    q = lambda t: question(t, vocab)  # noqa: E731
    assert q("Where is my phone?") == ("where", "phone", ["phone"])
    assert q("Which one is my teddy bear?")[:2] == ("where", "teddy bear")
    assert q("Have you seen my phone?")[:2] == ("seen", "phone")
    assert q("Is this my phone?")[:2] == ("this", "phone")
    assert q("Is this phone mine?")[:2] == ("this", "phone")
    assert q("Do you still remember my teddy bear?")[:2] == ("remember", "teddy bear")
    assert q("And my laptop?")[:2] == ("remember", "laptop")
    assert q("Are you still ignoring chairs?")[:2] == ("ignoring", "chair")
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
