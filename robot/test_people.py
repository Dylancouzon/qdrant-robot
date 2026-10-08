"""People memory on a real Edge shard with synthetic face vectors, and the identity answers."""
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from robot.config import MODELS, ROOT
from qdrant_edge import Point, UpdateOperation
from robot.people import DIM, NO_FACE, People, consent, done, face, reply, request

LFW = ROOT / "eval/faces/lfw/lfw"  # public photos (gitignored), never team photos


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def test_people() -> None:
    rng = np.random.default_rng(0)
    base = {n: unit(rng.normal(size=DIM)) for n in ("Ana", "Ben", "Cy")}
    near = lambda n: unit(base[n] + 0.05 * rng.normal(size=DIM))  # noqa: E731 another photo
    with tempfile.TemporaryDirectory() as tmp:
        people = People(Path(tmp))
        assert not people.enroll("Ana", {"f1": near("Ana"), "f2": near("Ana")}, None), "consent"
        assert not people.enroll("Ana", {"f1": near("Ana")}, 1.0), "one frame is one shot"
        assert people.enroll("Ana", {f"a{k}": near("Ana") for k in range(7)}, 1.0)
        assert people.enroll("Ben", {"b1": near("Ben"), "b2": near("Ben")}, 2.0)
        assert people.enroll("Cy", {"c1": near("Cy"), "c2": near("Cy")}, 2.0)
        assert people.identify(near("Ana"))[0] == "Ana"
        assert people.identify(near("Ben"))[0] == "Ben"
        assert people.identify(unit(rng.normal(size=DIM))) is None, "a stranger"
        people.link("Ana", ["a1", 17, "t9.jpg"])
        people.link("Ana", [17, 18])
        people.link("Nobody", [99])
        assert people.enroll("Ana", {"a9": near("Ana"), "a8": near("Ana")}, 3.0), "re-enroll"
        assert people.identify(near("Ana"))[0] == "Ana"
        assert people.forget("Ana") == [f"a{k}" for k in range(5)] + [17, "t9.jpg", 18, "a9",
                                                                      "a8"], "every linked id"
        assert people.forget("Nobody") == []
        people.shard.update(UpdateOperation.upsert_points([  # past one scroll page
            Point(k, {"shots": [near("Ben").tolist()] * 2}, {"name": "Ben", "linked": [k]})
            for k in range(150)]))
        assert len(people.forget("Ben")) == 152, "the enrolled point and all 150 extra"
        people.shard.close()
        again = People(Path(tmp))
        assert again.identify(near("Ana")) is None, "forgotten after a reopen"
        assert again.identify(near("Ben")) is None
        assert again.identify(near("Cy"))[0] == "Cy", "others stay"
        again.link("Cy", list(range(2500)))  # more evidence than any cap would keep
        assert len(again.forget("Cy")) == 2502, "every linked id, plus the two shot frames"
        again.shard.close()
        assert People(Path(tmp)).identify(near("Cy")) is None, "gone after a reopen"


def test_answers() -> None:
    sam = ("Sam", 0.7)
    assert request("Hey, do you still remember me?") == ("remembers", None)
    assert request("Could you remember me? My name is Kai Tanaka.") == ("enroll", "Kai Tanaka")
    assert request("Please learn my face, I'm lena") == ("enroll", "Lena")
    assert request("Remember me, I'm back!") == ("enroll", None), "'back' is no name"
    assert request("Who am I?") == ("name", None)
    assert request("Please delete my face.") == ("forget", None)
    assert request("Don't forget me!") is None and request("I'm visiting from Lyon.") is None
    assert reply("Do you recognize me?", sam, True)[0] == "You're Sam. I remember your face."
    assert reply("What's my name?", None, True) is None, "a told name may answer it"
    assert reply("Have we met?", None, True)[0].startswith("I don't think we've met")
    assert reply("Have we met?", None, False) == (NO_FACE, None)
    assert reply("Remember me, I'm Jo.", None, True)[1] == ("ask", "Jo")
    assert reply("Remember me, I'm Jo.", sam, True)[1] is None, "already known"
    assert reply("Forget me please.", sam, True) == (None, ("forget", "Sam")), "speak after"
    assert done("forget", "Sam", True).startswith("Done") and "could not" in done(
        "forget", "Sam", False)
    assert done("enroll", "Jo", False) == NO_FACE
    assert reply("Forget me please.", None, True)[1] is None, "nothing known to forget"
    assert consent("Yeah, sure, why not.") is True
    assert consent("No, I'd rather not.") is False
    assert consent("Hmm, what for?") is None


@pytest.mark.skipif(not (LFW.exists() and (MODELS / "faces/w600k_r50.onnx").exists()),
                    reason="needs LFW and the face models")
def test_face_step() -> None:
    from robot.faces import Faces
    faces = Faces()
    im = [cv2.imread(str(LFW / f"Colin_Powell/Colin_Powell_{k:04d}.jpg")) for k in (1, 2)]
    # LFW centers a 250 px photo on the face: a box twice as tall puts it in the upper half.
    a, b = (face(faces, x, (0, 0, 250, 500)) for x in im)
    assert a @ b > 0.4, "the same person"
    small = cv2.resize(im[0], None, fx=0.25, fy=0.25)
    assert face(faces, small, (0, 0, 63, 126)) is None, "a face under MIN_FACE"
