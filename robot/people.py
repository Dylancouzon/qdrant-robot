"""People the robot knows, in their own Qdrant Edge shard: one point per consenting person with
face shots as a multivector (MaxSim), the face step for a person box, and code answers to
identity questions ("do you remember me?", "remember me, I'm Sam", "forget me")."""
import re
import uuid
from pathlib import Path

import numpy as np
from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    MatchValue,
    MultiVectorComparator,
    MultiVectorConfig,
    Point,
    Query,
    QueryRequest,
    ScrollRequest,
    UpdateOperation,
)

from robot.config import SHARED
from robot.faces import Faces, align
from robot.memory import deletion_target, is_question

DIM = 512  # w600k_r50
SHOTS = 5  # enrolled shots kept per person
# Cosine of the second-best enrolled shot (D45, bench/faces_bakeoff.py CHOICE). Calibrated on
# phone photos shrunk to 40 px: recalibrate on robot-camera frames before runtime use (D45).
THRESHOLD = 0.328
CANDIDATES = 10  # people whose best shot passes THRESHOLD, checked for a second shot
MIN_FACE = 40  # px, face box width: the smallest size the bake-off measured (about 2 m away)
SIMILAR = 0.8  # faces at least this share of the largest one's width: the most central wins


class People:
    def __init__(self, root: Path = SHARED / "memory"):
        path = root / "people"
        if path.exists():
            self.shard = EdgeShard.load(str(path))
        else:
            path.mkdir(parents=True)
            self.shard = EdgeShard.create(str(path), EdgeConfig(vectors={"shots": EdgeVectorParams(
                size=DIM, distance=Distance.Cosine,
                multivector_config=MultiVectorConfig(MultiVectorComparator.MaxSim))}))

    def enroll(self, name: str, shots: list[np.ndarray], consent: float | None,
               visitor: str | None = None) -> bool:
        """Store a person from face vectors of different frames (the first SHOTS; no image is
        kept); `consent` is when they said yes. A different face cannot reuse an enrolled name.
        Refuse without consent or fewer than two frames; preserve the visitor and evidence links."""
        if not consent or len(shots) < 2:
            return False
        existing = self.person(name)
        if existing and any((match := self.identify(shot)) is None or match[0] != name
                            for shot in shots):
            return False
        visitor = existing["visitor"] if existing else visitor or str(uuid.uuid4())
        self.shard.update(UpdateOperation.upsert_points([Point(
            _id(name), {"shots": [s.tolist() for s in shots[:SHOTS]]},
            {"name": name, "visitor": visitor, "consent": consent, "shots": min(len(shots), SHOTS),
             "linked": self._linked(name, [])})]))
        self.shard.flush()
        return True

    def initialize_visitors(self) -> None:
        rows = self.shard.scroll(ScrollRequest(limit=1000, with_payload=True))[0]
        for row in rows:
            if not row.payload.get("visitor"):
                self.shard.update(UpdateOperation.set_payload([row.id],
                    {"visitor": str(uuid.uuid4())}))
        self.shard.flush()

    def person(self, name: str) -> dict | None:
        rows = self.shard.retrieve([_id(name)], True, False)
        return rows[0].payload if rows else None

    def by_visitor(self, visitor: str) -> dict | None:
        rows = self.shard.scroll(ScrollRequest(limit=1, with_payload=True, filter=Filter(
            must=[FieldCondition(key="visitor", match=MatchValue(visitor))])))[0]
        return rows[0].payload if rows else None

    def _linked(self, name: str, ids: list) -> list:
        """The person's linked evidence ids plus `ids`. All are kept: forget() must return every
        one, and memory retention already bounds how much evidence exists."""
        found = self.shard.retrieve([_id(name)], ["linked"], False)
        old = found[0].payload["linked"] if found else []
        return list(dict.fromkeys(old + ids))

    def link(self, name: str, ids: list) -> None:
        """Record evidence ids (turn points and their frames) seen with `name`, so forget()
        returns them; a no-op for an unknown name."""
        if self.shard.retrieve([_id(name)], False, False):
            self.shard.update(UpdateOperation.set_payload(
                [_id(name)], {"linked": self._linked(name, ids)}))
            self.shard.flush()

    def scores(self, face: np.ndarray) -> list[tuple[str, float, float]]:
        """(name, best shot, second-best shot) of the enrolled people nearest `face` (a unit
        vector), highest second-best first: the two-shot rule's value. Edge MaxSim finds the
        candidates by their best shot; the second-best is computed here."""
        hits = self.shard.query(QueryRequest(
            limit=CANDIDATES, query=Query.Nearest([face.tolist()], using="shots"),
            with_payload=["name"], with_vector=True))
        shots = [(h.payload["name"], np.sort(np.array(h.vector["shots"]) @ face)) for h in hits]
        return sorted(((n, float(s[-1]), float(s[-2])) for n, s in shots), key=lambda x: -x[2])

    def identify(self, face: np.ndarray) -> tuple[str, float] | None:
        """(name, score) of the person whose second-best shot is closest to `face`, at
        THRESHOLD or above; None for anyone else."""
        best = self.scores(face)[:1]
        return (best[0][0], best[0][2]) if best and best[0][2] >= THRESHOLD else None

    def forget(self, name: str) -> list:
        """Delete every point called `name`; returns the ids linked to them, for the caller to
        delete that evidence."""
        linked: list = []
        while found := self.shard.scroll(ScrollRequest(
                limit=100, with_payload=["linked"],
                filter=Filter(must=[FieldCondition(key="name", match=MatchValue(name))])))[0]:
            linked += [i for r in found for i in r.payload.get("linked", [])]
            self.shard.update(UpdateOperation.delete_points([r.id for r in found]))
            self.shard.flush()
        return list(dict.fromkeys(linked))


def _id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"person:{name}"))


def located_face(faces: Faces, frame: np.ndarray
                 ) -> tuple[np.ndarray, int, tuple[int, int, int, int]] | None:
    """The face vector of the visitor in `frame` and its width in pixels: the largest face,
    or among faces nearly as large (SIMILAR), the one nearest the center. None when no face
    is MIN_FACE wide."""
    found = faces.detect(frame)
    if not len(found) or found[0, 2] < MIN_FACE:
        return None
    big = found[found[:, 2] >= SIMILAR * found[0, 2]]
    f = big[np.argmin(np.abs(big[:, 0] + big[:, 2] / 2 - frame.shape[1] / 2))]
    box = tuple(int(v) for v in (f[0], f[1], f[0] + f[2], f[1] + f[3]))
    return faces.embed([align(frame, f[4:14].reshape(5, 2))])[0], int(f[2]), box


def face(faces: Faces, frame: np.ndarray) -> tuple[np.ndarray, int] | None:
    found = located_face(faces, frame)
    return found[:2] if found else None


# Identity requests. A name given with "remember me" makes it an enrollment request.
_FORGET = re.compile(r"((everything|all)\s+)?(about\s+)?(me|my face|who i am)\b", re.I)
_REMEMBERS = re.compile(r"\b(do|did|can|could|will|would)\s+you\s+(still\s+)?(remember|"
                        r"recogni[sz]e|know)\s+(me|who i am)\b|\bhave we met\b|"
                        r"^\W*(remember|recogni[sz]e)\s+me\s*\?", re.I)
_NAME_Q = re.compile(r"\b(what'?s|what is|do you know|tell me|say)\s+my name\b|\bwho am i\b", re.I)
_ENROLL = re.compile(r"\b(remember|recogni[sz]e|learn|memori[sz]e)\s+(me|my face)\b", re.I)
# Names: "my name is X", "call me X", "this is X speaking" (any case, up to two words), or
# "I'm X" / "I am X" with X one capitalized word: Parakeet capitalizes proper names, so
# "I'm tired" and "I'm looking for..." are no names.
_CALLED = re.compile(r"\b(?:my name is|my name'?s|call me)\s+([a-z][a-z'-]*)"
                     r"(?:\s+([a-z][a-z'-]*))?|\bthis is ([a-z][a-z'-]*) speaking\b", re.I)
_I_AM = re.compile(r"\b[Ii](?:['\u2019]?m| am)\s+([A-Z][a-z'-]*)\b")
# ponytail: common words that are no name ("I'm Back", "call me back"); the robot also confirms
# the name in its consent question, where "no" stops a wrong one.
_NOT_NAMES = {"a", "actually", "afraid", "again", "all", "also", "an", "and", "at", "back",
              "bored", "busy", "but", "cold", "curious", "doing", "done", "excited", "fine",
              "from", "getting", "glad", "going", "good", "great", "happy", "having", "here",
              "hot", "hungry", "in", "interested", "it", "just", "late", "looking", "lost", "me",
              "new", "not", "ok", "okay", "on", "only", "please", "pretty", "ready", "really",
              "remember", "so", "sorry", "still", "sure", "that", "the", "there", "thinking",
              "this", "tired", "too", "trying", "very", "visiting", "waiting", "well",
              "wondering", "working", "you", "your"}
_NO = (r"no(?!\s+(?:problem|worries))|nope|nah|don'?t|do not|rather not|not really|never|"
       r"not mine|it isn't|it is not|it's not")
_YES = (r"yes|yeah|yep|yup|sure|ok(?:ay)?|of course|go ahead|please do|alright|absolutely|fine|"
        r"you (?:may|can)|correct|it is|that's (?:it|mine|right)|no (?:problem|worries)")
_FILLER = r"^\W*(?:(?:um|uh|oh|well|hmm)\W+)*"
_YES_FIRST = re.compile(rf"{_FILLER}(?:{_YES})\b(?!\s+not\b)", re.I)
_NO_FIRST = re.compile(rf"{_FILLER}(?:{_NO})\b", re.I)
_NO_ANY = re.compile(rf"\b(?:{_NO})\b", re.I)
_YES_ANY = re.compile(rf"\b(?:{_YES})\b(?!\s+not\b)", re.I)

DECLINED = "All right, I won't remember your face."
KEPT = "Okay, I will keep it."
NO_FACE = "Please look at me and say it again, so I can learn your face."
NOT_YOU = "Please look at me and say it again, so I can check it is you."
NOT_MET = "I don't think we've met yet. What's your name?"


def name_in(text: str) -> str | None:
    """The name a visitor gives ("My name is Sam Lee" -> "Sam Lee", "I'm Ana from Berlin" ->
    "Ana"), or None."""
    m = _CALLED.search(text) or _I_AM.search(text)
    words = [w for w in (m.groups() if m else ()) if w]
    if not words or words[0].lower() in _NOT_NAMES:
        return None
    return " ".join(w.capitalize() for w in words if w.lower() not in _NOT_NAMES)


def request(text: str) -> tuple[str, str | None] | None:
    """("forget" | "remembers" | "name" | "enroll", the given name) for an identity request,
    else None."""
    if (rest := deletion_target(text)) is not None and _FORGET.match(rest):
        return "forget", None
    name = name_in(text)
    if name and (_ENROLL.search(text) or _REMEMBERS.search(text)):
        return "enroll", name
    if _REMEMBERS.search(text):
        return "remembers", None
    if _NAME_Q.search(text):
        return "name", None
    return ("enroll", name) if _ENROLL.search(text) else None


def reply(text: str, who: tuple[str, float] | None, seen: bool, told: str | None = None
          ) -> tuple[str | None, tuple[str, str] | None] | None:
    """The spoken answer to an identity request and the caller's next action: ("ask", name)
    means the next turn goes through consent(); ("forget", name) comes with no answer: the
    caller calls People.forget, deletes the evidence, then says done("forget", ...).
    `who` is People.identify on the visitor's face, `seen` whether a face was found, `told`
    the name the visitor told in this conversation (D60: without a face match it answers
    "who am I?"). None when `text` is no identity request."""
    req = request(text)
    if req is None:
        return None
    kind, name = req
    if who:
        return _known(kind, name, who[0])
    if kind == "name" and told:  # a name, never a claim to remember the visitor
        return f"You told me you're {told}.", None
    if kind in ("name", "remembers"):
        return NOT_MET, None
    if kind == "forget":
        return "I don't recognize your face, so I have no face of yours to forget.", None
    if name is None:
        return "Tell me your name too, for example: remember me, I'm Sam.", None
    if not seen:
        return NO_FACE, None
    return f"May I remember your face, {name}? Please say yes or no.", ("ask", name)


def _known(kind: str, name: str | None, known: str) -> tuple[str | None, tuple[str, str] | None]:
    if kind == "forget":
        return None, ("forget", known)
    if kind == "enroll" and name not in (None, known):
        return f"I already remember you as {known}. Say forget me first to start over.", None
    if kind == "enroll":
        return f"I already remember you, {known}.", None
    return f"You're {known}. I remember your face.", None


def consent(text: str) -> bool | None:
    """The answer to a yes or no question: face consent ("May I remember your face?"), near-match
    confirmation ("Is this your mouse?"), and deletion ("Should I forget ...?"). True for a yes
    or False for a no at the start of the line, after a filler such as "um"; None for anything
    else (ask again or go on): a question, or a line with both, or a yes buried in a sentence
    ("I'm not sure"). On a face yes the caller calls People.enroll, then says
    done("enroll", ...)."""
    text = text.replace("\u2019", "'")
    if "?" in text or is_question(text):
        return None
    yes, no = bool(_YES_FIRST.match(text)), bool(_NO_FIRST.match(text))
    if yes and not _NO_ANY.search(text):
        return True
    if no and not _YES_ANY.search(text):
        return False
    return None


def forget_question(name: str | None) -> str:
    """The question before "forget me" deletes anything; the next line is read by consent()
    (a yes runs the deletion, then done("forget", ...))."""
    return f"Should I forget everything about you{f', {name}' if name else ''}? Say yes or no."


def done(kind: str, name: str, ok: bool) -> str:
    """What to say after People.enroll ("enroll") or People.forget and the evidence deletion
    ("forget") returned, `ok` when it succeeded."""
    if kind == "enroll":
        return f"Thank you, {name}. I will remember your face." if ok else NO_FACE
    if ok:
        return f"Done, {name}. I have forgotten your face."
    return "Sorry, something went wrong and I could not forget you. Please ask again."
