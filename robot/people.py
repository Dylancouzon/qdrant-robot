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

    def enroll(self, name: str, shots: list[np.ndarray], consent: float | None) -> bool:
        """Store a person from face vectors of different frames (the first SHOTS; no image is
        kept); `consent` is when they said yes. One point per name: enrolling a known name
        replaces its shots and keeps its links. Refused (False) without consent or with fewer
        than two frames, since an identity claim needs two shots."""
        if not consent or len(shots) < 2:
            return False
        self.shard.update(UpdateOperation.upsert_points([Point(
            _id(name), {"shots": [s.tolist() for s in shots[:SHOTS]]},
            {"name": name, "consent": consent, "shots": min(len(shots), SHOTS),
             "linked": self._linked(name, [])})]))
        self.shard.flush()
        return True

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


def face(faces: Faces, frame: np.ndarray) -> tuple[np.ndarray, int] | None:
    """The face vector of the visitor in `frame` and its width in pixels: the largest face,
    or among faces nearly as large (SIMILAR), the one nearest the center. None when no face
    is MIN_FACE wide."""
    found = faces.detect(frame)
    if not len(found) or found[0, 2] < MIN_FACE:
        return None
    big = found[found[:, 2] >= SIMILAR * found[0, 2]]
    f = big[np.argmin(np.abs(big[:, 0] + big[:, 2] / 2 - frame.shape[1] / 2))]
    return faces.embed([align(frame, f[4:14].reshape(5, 2))])[0], int(f[2])


# Identity requests. A name given with "remember me" makes it an enrollment request.
_NOT_FORGET = re.compile(r"\b(don'?t|do not|never)\s+forget\b", re.I)
_FORGET = re.compile(r"\b(forget|delete|erase|remove)\s+((everything|all)\s+)?(about\s+)?"
                     r"(me|my face|who i am)\b", re.I)
_REMEMBERS = re.compile(r"\b(do|did|can|could|will|would)\s+you\s+(still\s+)?(remember|"
                        r"recogni[sz]e|know)\s+(me|who i am)\b|\bhave we met\b|"
                        r"^\W*(remember|recogni[sz]e)\s+me\s*\?", re.I)
_NAME_Q = re.compile(r"\b(what'?s|what is|do you know|tell me|say)\s+my name\b|\bwho am i\b", re.I)
_ENROLL = re.compile(r"\b(remember|recogni[sz]e|learn|memori[sz]e)\s+(me|my face)\b", re.I)
_NAME = re.compile(r"\b(?:i'?m|i am|my name is|my name'?s|call me)\s+([a-z][a-z'-]*)"
                   r"(?:\s+([a-z][a-z'-]*))?", re.I)
# ponytail: common words after "I'm" that are no name ("I'm back"); the robot also confirms
# the name in its consent question, where "no" stops a wrong one.
_NOT_NAMES = {"a", "an", "and", "again", "also", "back", "but", "fine", "from", "glad", "going",
              "good", "happy", "here", "it", "just", "me", "new", "not", "okay", "ok", "please",
              "really", "remember", "so", "sorry", "still", "sure", "that", "the", "this", "too",
              "very", "visiting", "you", "your"}
_NO = re.compile(r"\b(no|nope|nah|don'?t|do not|rather not|not really|never)\b", re.I)
_YES = re.compile(r"\b(yes|yeah|yep|yup|sure|ok(ay)?|of course|go ahead|please do|alright|"
                  r"absolutely|fine|you (may|can))\b", re.I)

DECLINED = "All right, I won't remember your face."
NO_FACE = "I can't see your face well enough. Please look at me and ask again."
NO_FACE_SEEN = "I can't see your face right now."
NOT_SURE = "I'm not sure who you are."


def name_in(text: str) -> str | None:
    """The name a visitor gives ("I'm Sam Lee" -> "Sam Lee"), or None."""
    m = _NAME.search(text)
    words = [w for w in (m.groups() if m else ()) if w]
    if not words or words[0].lower() in _NOT_NAMES:
        return None
    return " ".join(w.capitalize() for w in words if w.lower() not in _NOT_NAMES)


def request(text: str) -> tuple[str, str | None] | None:
    """("forget" | "remembers" | "name" | "enroll", the given name) for an identity request,
    else None."""
    if _FORGET.search(text) and not _NOT_FORGET.search(text):
        return "forget", None
    name = name_in(text)
    if name and (_ENROLL.search(text) or _REMEMBERS.search(text)):
        return "enroll", name
    if _REMEMBERS.search(text):
        return "remembers", None
    if _NAME_Q.search(text):
        return "name", None
    return ("enroll", name) if _ENROLL.search(text) else None


def reply(text: str, who: tuple[str, float] | None, seen: bool
          ) -> tuple[str | None, tuple[str, str] | None] | None:
    """The spoken answer to an identity request and the caller's next action: ("ask", name)
    means the next turn goes through consent(); ("forget", name) comes with no answer: the
    caller calls People.forget, deletes the evidence, then says done("forget", ...).
    `who` is People.identify on the visitor's face, `seen` whether a face was found. None
    when `text` is no identity request, or asks for a name the face does not give: the
    conversation memory may hold a name the visitor told."""
    req = request(text)
    if req is None:
        return None
    kind, name = req
    if who:
        return _known(kind, name, who[0])
    if kind == "name":
        return None
    if not seen:
        return NO_FACE, None
    if kind == "forget":
        return "I don't recognize your face, so I have no face of yours to forget.", None
    if kind == "remembers":
        return ("I don't think we've met. To have me remember your face, say: remember me, "
                "and your name.", None)
    if name is None:
        return "Tell me your name too, for example: remember me, I'm Sam.", None
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
    """The answer to "May I remember your face?": True for a clear yes, False for a clear no
    (say DECLINED), None when unclear (ask again). On yes the caller calls People.enroll and
    then says done("enroll", ...)."""
    yes, no = bool(_YES.search(text)), bool(_NO.search(text))
    return None if yes == no else yes


def done(kind: str, name: str, ok: bool) -> str:
    """What to say after People.enroll ("enroll") or People.forget and the evidence deletion
    ("forget") returned, `ok` when it succeeded."""
    if kind == "enroll":
        return f"Thank you, {name}. I will remember your face." if ok else NO_FACE
    if ok:
        return f"Done, {name}. I have forgotten your face."
    return "Sorry, something went wrong and I could not forget you. Please ask again."
