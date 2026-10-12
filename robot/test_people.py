"""People memory on a real Edge shard with synthetic face vectors, and the identity answers."""
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from robot.config import MODELS, ROOT
from qdrant_edge import Point, UpdateOperation
from robot.people import DIM, NO_FACE, NOT_MET, People, name_in, consent, done, face, reply, request

LFW = ROOT / "eval/faces/lfw/lfw"  # public photos (gitignored), never team photos


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def test_people() -> None:
    rng = np.random.default_rng(0)
    base = {n: unit(rng.normal(size=DIM)) for n in ("Ana", "Ben", "Cy")}
    near = lambda n: unit(base[n] + 0.05 * rng.normal(size=DIM))  # noqa: E731 another photo
    with tempfile.TemporaryDirectory() as tmp:
        people = People(Path(tmp))
        assert not people.enroll("Ana", [near("Ana"), near("Ana")], None), "consent"
        assert not people.enroll("Ana", [near("Ana")], 1.0), "one frame is one shot"
        assert people.enroll("Ana", [near("Ana") for _ in range(7)], 1.0)
        assert people.enroll("Ben", [near("Ben"), near("Ben")], 2.0)
        assert people.enroll("Cy", [near("Cy"), near("Cy")], 2.0)
        assert people.identify(near("Ana"))[0] == "Ana"
        assert people.identify(near("Ben"))[0] == "Ben"
        assert people.identify(unit(rng.normal(size=DIM))) is None, "a stranger"
        people.link("Ana", [16, 17])
        people.link("Ana", [17, 18])
        people.link("Nobody", [99])
        assert people.enroll("Ana", [near("Ana"), near("Ana")], 3.0), "re-enroll"
        assert people.identify(near("Ana"))[0] == "Ana"
        assert people.forget("Ana") == [16, 17, 18], "every linked id, once"
        assert people.forget("Nobody") == []
        people.shard.update(UpdateOperation.upsert_points([  # past one scroll page
            Point(k, {"shots": [near("Ben").tolist()] * 2}, {"name": "Ben", "linked": [k]})
            for k in range(150)]))
        assert len(people.forget("Ben")) == 150, "linked ids of all 150 extra points"
        people.shard.close()
        again = People(Path(tmp))
        assert again.identify(near("Ana")) is None, "forgotten after a reopen"
        assert again.identify(near("Ben")) is None
        assert again.identify(near("Cy"))[0] == "Cy", "others stay"
        again.link("Cy", list(range(2500)))  # more evidence than any cap would keep
        assert len(again.forget("Cy")) == 2500, "every linked id"
        again.shard.close()
        assert People(Path(tmp)).identify(near("Cy")) is None, "gone after a reopen"


def test_answers() -> None:
    sam = ("Sam", 0.7)
    assert request("Hey, do you still remember me?") == ("remembers", None)
    assert request("Could you remember me? My name is Kai Tanaka.") == ("enroll", "Kai Tanaka")
    assert request("Please learn my face, my name is lena") == ("enroll", "Lena")
    for said, name in [("I'm Ana from Berlin.", "Ana"), ("Hi, I am Priya.", "Priya"),
                       ("Call me Jo.", "Jo"), ("This is Omar speaking.", "Omar"),
                       ("My name's Kai and I build drones.", "Kai")]:
        assert name_in(said) == name, said
    for said in ["I'm tired.", "I'm fine, thanks.", "I'm here!", "I'm looking for the bathroom.",
                 "I am just visiting.", "I'm Sorry.", "I'm lena", "I'm good, and you?"]:
        assert name_in(said) is None, said
    assert request("Remember me, I'm back!") == ("enroll", None), "'back' is no name"
    assert request("Who am I?") == ("name", None)
    assert request("Please delete my face.") == ("forget", None)
    assert request("Don't forget me!") is None and request("I'm visiting from Lyon.") is None
    for said in [
                 "Don't delete my face.",
                 "Do not erase me",
                 "Can you not forget me",
                 "Please do not ever forget me",
                 "I do not want you to forget me",
                 "Can you tell me why you forget me",
                 "Should I forget me?",
                 "Why did you forget me?",
                 "Did you forget me?",
                 "I said forget me",
                 "You forget me every time",
                 "Tell me how to delete my face",
                 "When will you forget me?",
                 "How do I make you forget me",
                 "Never forget me",
                 "Please don't forget my face",
                 "He wants you to forget me",
                 "Do you forget me?",
    ]:
        assert request(said) != ("forget", None), said
    for said in [
                 "Forget me",
                 "forget me.",
                 "Please forget me",
                 "Okay, delete my face",
                 "Ok so erase everything about me",
                 "Can you forget me?",
                 "could you please remove my face",
                 "Would you forget who I am",
                 "I want you to forget me",
                 "I'd like you to please delete my face",
                 "um please forget me",
                 "Forget me, please",
                 "Now erase all about me",
    ]:
        assert request(said) == ("forget", None), said
    assert reply("Do you recognize me?", sam, True)[0] == "You're Sam. I remember your face."
    assert reply("What's my name?", None, True) == (NOT_MET, None)
    assert reply("What's my name?", None, False, "Ana")[0] == "You told me you're Ana."
    assert reply("What's my name?", sam, True, "Ana")[0].startswith("You're Sam"), "face wins"
    assert reply("Have we met?", None, False) == (NOT_MET, None), "no face: still no claim"
    assert reply("Do you remember me?", None, True, "Jo") == (NOT_MET, None), "told, not known"
    assert reply("Remember me, I'm Jo.", None, False) == (NO_FACE, None), "enrolling needs one"
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
    for text, answer in [("I'm not sure", None), ("Okay, what do you see?", None),
                         ("Sure, go ahead", True), ("Yes please", True), ("Um, yes", True),
                         ("No, keep it", False), ("Nope", False), ("Of course", True),
                         ("Of course not", None), ("No, it is not mine", False),
                         ("No problem", True), ("That's right", True), ("That\u2019s mine", True),
                         ("Not mine", False), ("Yes and no", None)]:
        assert consent(text) is answer, text


@pytest.mark.skipif(not (LFW.exists() and (MODELS / "faces/w600k_r50.onnx").exists()),
                    reason="needs LFW and the face models")
def test_face_step() -> None:
    from robot.faces import Faces
    faces = Faces()
    im = [cv2.imread(str(LFW / f"Colin_Powell/Colin_Powell_{k:04d}.jpg")) for k in (1, 2)]
    # LFW centers a 250 px photo on the face: a box twice as tall puts it in the upper half.
    (a, _), (b, _) = (face(faces, x) for x in im)
    assert a @ b > 0.4, "the same person"
    small = cv2.resize(im[0], None, fx=0.25, fy=0.25)
    assert face(faces, small) is None, "a face under MIN_FACE"


def offer(name: str) -> str:
    return f"Nice to meet you, {name}! Want me to remember your face so I recognize you next time?"


def test_robot_identity(monkeypatch) -> None:
    """The robot's identity turns through Robot._turn on real Edge shards, with a fake face
    step (a person's face vector is the pixel value of their frame; 99: the face is hidden)
    and stub brain, voice, and embedder. Identity comes from the face in the frame at speech
    start, never a track or the cached look: a visitor who replaces another in the same place
    (the look stays valid), or whose new track merges into another's lost track, inherits no
    name, consent, or evidence; after "forget me" nothing of that face is stored."""
    import queue
    import time
    from types import SimpleNamespace as Stub

    from robot import main, memory
    from robot.detect import CONFIRM, LOST, MAX_MISSED, Detection
    from robot.main import FIRST_PERSON, Robot, Turn
    from robot.people import DECLINED, KEPT, _id
    from robot.text_embed import DIM as TEXT_DIM
    from robot.test_things import open_robot

    steps = []

    def fake_face(faces, frame):
        steps.append(1)
        k = int(frame[0, 0, 0])
        return None if k == 99 else (np.eye(DIM, dtype=np.float32)[k], 120)

    monkeypatch.setattr(main, "face", fake_face)
    here, near = (400, 100, 800, 700), (450, 100, 850, 700)
    clock = iter(range(int(time.time()), int(time.time()) + 10_000))  # wall clock, as turns

    def make(root: Path) -> Robot:
        robot = open_robot(root)  # current model-free owner, tracking, UI, and real Edge shards
        robot.asking, robot.stream, robot.wake_word = None, None, False
        robot.turns = queue.Queue()
        robot.vocab = set()
        robot.ready, robot.last_frame, robot.exchanges, robot.detections = None, None, 0, 0
        robot.out = root / "out"
        robot.out.mkdir(exist_ok=True)
        robot.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[[0] * len(texts)]
        robot.knowledge, robot.route = Stub(search=lambda q: []), lambda q: "social"
        robot.brain = Stub(prefill=lambda m: None, answer=lambda m, **k: (t for t in ["Okay."]))
        robot.voice = Stub(say=lambda text: np.zeros(160, np.float32))
        robot.speaker = Stub(play=lambda pcm: None)
        return robot

    with tempfile.TemporaryDirectory() as tmp:
        root, turns = Path(tmp), []
        robot = make(root)

        def frames(k: int | None, n: int, box: tuple = here) -> np.ndarray:
            frame = np.full((720, 1280, 3), k or 0, np.uint8)
            for _ in range(n):  # the robot's detection loop, without the detector
                dets = [Detection("person", 0.9, box)] if k else []
                if found := robot.tracker.update(dets, 1280, float(next(clock))):
                    robot._sight(found)
            return frame

        def ask(text: str, frame: np.ndarray) -> str | None:
            """The code answer to `text` said in front of `frame`, or None (the brain's)."""
            t = float(next(clock))
            turns.append(turn := Turn(question=text, speech_start=t, line=t, speech_end=t))
            robot._turn(turn, (frame, t))
            return turn.answer if turn.verbatim else None

        def linked(name: str) -> list[int]:
            found = robot.people.shard.retrieve([_id(name)], ["linked"], False)
            return found[0].payload["linked"] if found else []

        def said() -> list[str]:
            return [r.payload.get("said", "") for r in robot.memory.shard.scroll(
                memory.ScrollRequest(limit=999, with_payload=True))[0]]

        ana = frames(1, 60)
        assert steps == [], "no face step without a turn"
        robot.wake_word = True  # D65
        assert ask("What's my name?", ana) is None and turns[-1].kind == "background"
        assert ask("Hey Edgy, what's my name?", ana) == NOT_MET
        assert turns[-1].question == "what's my name?", "the wake phrase is stripped"
        assert ask("What's my name?", ana) == NOT_MET, "a follow-up within CONVERSATION_S"
        robot.wake_word = False
        assert ask("Nice to meet you, I'm Ana.", ana) == offer("Ana"), "a name: one offer (D69)"
        assert ask("What's my name?", ana) == "You told me you're Ana.", "no reply keeps the name"
        assert ask("I'm Ana, as I said.", ana) is None, "the offer is never repeated"
        assert ask("What's my name?", frames(99, 1)) == "You told me you're Ana.", \
            "her face is missed on her own person track: the conversation goes on"
        assert ask("I'm Ana.", frames(99, 1)) is None, "told with no face: no offer"
        assert ask("What's my name?", frames(99, 1)) == "You told me you're Ana.", "a follow-up"
        assert ask("What's my name?", frames(99, MAX_MISSED + CONFIRM, (0, 100, 300, 700))) \
            == NOT_MET, "no face, another person track: a new conversation"
        for _ in range(main.CONVERSATION_S + 1):
            next(clock)  # a pause: whoever speaks now may be someone else
        assert ask("What's my name?", frames(99, 1)) == NOT_MET, "no face after a gap: dropped"
        assert ask("I'm Ana.", frames(99, 1)) is None
        assert ask("Yes.", frames(4, 1)) is None and robot.people.identify(np.eye(DIM)[4]) is None \
            and robot.people.identify(np.eye(DIM)[1]) is None, "another visitor's yes: nobody"
        assert ask("I'm Ana.", ana) == offer("Ana"), "her face: a new linked visitor, one offer"
        assert ask("No thanks.", ana) == DECLINED, "no"
        assert robot.people.identify(np.eye(DIM)[1]) is None, "a no enrolls nothing"
        assert ask("What's my name?", ana) == "You told me you're Ana.", "the name stays"
        assert ask("Remember me, I'm Ana.", ana).startswith("May I remember your face, Ana?")
        assert ask("Hmm, what?", ana).startswith("Sorry, may I"), "unclear: asked once more"
        assert ask("What's the weather?", ana) is None, "then the conversation goes on"
        assert ask("Yes.", ana) is None and robot.people.identify(np.eye(DIM)[1]) is None
        assert ask("Remember me, I'm Ana.", ana).startswith("May I")
        assert ask("No thanks.", ana) == DECLINED and robot.people.identify(np.eye(DIM)[1]) is None
        assert ask("Remember me, I'm Ana.", ana).startswith("May I")
        assert ask("Yes, sure.", ana) == done("enroll", "Ana", True)
        assert ask("Do you remember me?", ana) == "You're Ana. I remember your face."
        assert turns[-1].identity["claimed"] == "Ana" and turns[-1].identity["face_px"] == 120
        assert turns[-1].identity["scores"][0][::2] == ["Ana", 1.0], "the two-shot value logged"
        track, ana_links = robot._visitor(), linked("Ana")
        robot._look((ana, float(next(clock))))  # idle time prefills Ana's frame (_watch)
        ben = frames(2, 3)  # Ben steps into Ana's place: the track goes on
        assert robot._visitor() == track and not robot._stale(ben), \
            "and the prefilled look of Ana stays valid for his turn"
        assert ask("Do you remember me?", ben).startswith("I don't think we've met")
        assert linked("Ana") == ana_links, "his turn is not linked to her"
        assert ask("Who am I?", ben) == NOT_MET and linked("Ana") == ana_links, \
            "Ben inherits neither Ana's told name nor her evidence"
        assert ask("Remember me, I'm Ben.", ben).startswith("May I")
        assert ask("Yes.", frames(1, 1)) == done("enroll", "Ben", False), "not the face that asked"
        assert ask("Remember me, I'm Ben.", ben).startswith("May I")
        assert ask("Yes.", ben) == done("enroll", "Ben", True)
        assert ask("Great, thanks, robot.", ben) is None
        hidden = frames(99, 1)
        assert ask("What's my name?", hidden) == "You told me you're Ben.", \
            "face missed on his own track: the told name stays"
        assert ask("Do you remember me?", hidden).startswith("I don't think we've met"), \
            "but recognition still needs a face in the frame"
        frames(2, 3)
        frames(None, MAX_MISSED + 2)  # Ben leaves; Ana steps in nearby before his track ends
        ana = frames(1, CONFIRM + 1, near)
        assert robot._visitor() == track, "her new track continued his lost one"
        assert ask("What's my name?", ana) == "You're Ana. I remember your face."
        assert ask("Thanks!", ana) is None
        assert ask("Missed face line.", frames(99, 1, near)) is None
        assert "Missed face line." in said(), "stored for her though her face was missed"
        assert "Remember me, I'm Ben." in said() and "Nice to meet you, I'm Ana." in said()
        assert not list((root / "frames").iterdir()), "ordinary identity turns store text only"
        crop = robot.memory.add(ana[:80, :80], "Ana's selected source crop", ts=time.time())
        robot.people.link("Ana", [crop])
        [source] = robot.memory.points([crop])
        assert (root / "frames" / source["frame"]).exists(), "deletion covers a real saved image"
        hers = robot.memory.points(linked("Ana"))
        held = {r.payload["frame"] for r in robot.memory.shard.scroll(memory.ScrollRequest(
            limit=999, with_payload=["frame"]))[0] if "frame" in r.payload}
        assert hers and {f.name for f in (root / "frames").iterdir()} == held, \
            "only the explicit linked source crop saves an image"
        assert ask("Please forget me.", ana) == "Should I forget everything about you, Ana? " \
            "Say yes or no."
        assert ask("No, keep me.", ana) == KEPT and robot.people.identify(np.eye(DIM)[1])
        assert ask("Please forget me.", ana).startswith("Should I forget")
        assert ask("What's my name?", ana) == "You're Ana. I remember your face.", \
            "any other line drops the question and is answered"
        assert ask("Yes.", ana) is None and robot.people.identify(np.eye(DIM)[1]), \
            "a yes with no question pending deletes nothing"
        assert ask("Please forget me.", ana).startswith("Should I forget")
        assert ask("Yes.", frames(2, 1)) is None and robot.people.identify(np.eye(DIM)[1]), \
            "another visitor's yes deletes nothing"
        assert ask("Please forget me.", ana).startswith("Should I forget")
        assert robot.deleting and turns[-1].keep is False, "the question is no evidence"
        assert ask("Yes, please.", ana) == done("forget", "Ana", True)
        assert robot.people.identify(np.eye(DIM)[1]) is None
        assert robot.people.identify(np.eye(DIM)[2])[0] == "Ben", "only the face that asked"
        assert not robot.memory.points([p["id"] for p in hers])
        assert not any((root / "frames" / p["frame"]).exists()
                       for p in hers if "frame" in p), "and frames"
        assert "Missed face line." not in said(), "a missed-face turn of hers goes too"
        assert "Thanks!" not in said() and "Great, thanks, robot." in said(), \
            "her linked turns go, Ben's stay"
        frames(None, LOST + 2)  # the detector loses her: no person track at all
        assert ask("Hello again, I'm still here.", ana) is None
        assert ask("Can you hear me?", frames(99, 1)) is None
        assert not any(t in said() for t in ("Please forget me.", "Hello again, I'm still here.",
                                             "Can you hear me?")), "nothing of her is stored"
        assert ask("Hi, I'm next in line.", frames(2, 1)) is None
        assert "Hi, I'm next in line." in said(), "another face ends the hiding"
        monkeypatch.setattr(memory, "MAX_POINTS", 1)
        robot._retain(float(next(clock)))
        assert robot.memory.shard.count(memory.CountRequest()) <= 1 and linked("Ben"), \
            "linked turns expire like other evidence: the cap holds"
        monkeypatch.setattr(memory, "MAX_POINTS", 20_000)
        ben = frames(2, CONFIRM + 1)
        track = robot._visitor()
        assert ask("Forget me too.", ben).startswith("Should I forget")
        assert ask("Yes.", ben) == done("forget", "Ben", True) and turns[-1].keep is False
        assert ask("Still me.", ben) is None and "Still me." not in said()
        cy = frames(3, 3)  # Cy steps into Ben's place: the same track id
        assert robot._visitor() == track
        assert ask("Hello, I'm new here.", cy) is None and "Hello, I'm new here." in said(), \
            "a new face on a forgotten track is stored"
        robot.memory.shard.close()
        robot.people.shard.close()
        robot.things.shard.close()
        robot = make(root)  # a restart: nothing of Ana is left to recognize or hide
        assert robot.people.identify(np.eye(DIM)[1]) is None and robot.people.identify(
            np.eye(DIM)[2]) is None, "after a reopen of both shards"
        assert ask("Do you remember me?", frames(1, CONFIRM + 1)).startswith(
            "I don't think we've met"), "only a new consent could enroll her again"
        cy = frames(3, 1)
        assert ask("Hi, I'm Cy.", cy) == offer("Cy") and robot.people.identify(np.eye(DIM)[3]) \
            is None, "a name alone is never consent"
        assert ask("Yes, please.", cy) == done("enroll", "Cy", True)
        assert robot.people.identify(np.eye(DIM)[3])[0] == "Cy", "a yes to the offer enrolls"
        robot.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[
            [1 if "from" in t else 0 for t in texts]]  # only lines about origin match each other
        assert ask("I'm from Lisbon.", cy) is None
        assert ask("Where am I from?", cy) is None and turns[-1].told == ["I'm from Lisbon."]
        assert "Lisbon" in str(turns[-1].prompt), "Cy's own exchanges stay in the prompt"
        assert ask("So which town do I live in?", frames(5, 1)) is None, "a paraphrase"
        assert not any(FIRST_PERSON.search(x) for x in turns[-1].told) and "Lisbon" not in str(
            turns[-1].prompt), "a visitor replacing Cy within the window gets none of Cy's " \
            "statements or exchanges (D70)"
        assert ask("Where am I from?", frames(5, 1)) is None and turns[-1].told == []
        assert ask("Where am I from?", cy) is None and turns[-1].told == [], \
            "nor does Cy after that new conversation"


def test_face_position_matches_selected_detection(monkeypatch):
    from types import SimpleNamespace
    from robot import people

    rows = np.zeros((2, 15), np.float32)
    rows[0, :4], rows[1, :4] = (0, 100, 160, 160), (565, 120, 150, 155)
    vector = np.eye(DIM, dtype=np.float32)[0]
    faces = SimpleNamespace(detect=lambda frame: rows, embed=lambda crops: [vector])
    monkeypatch.setattr(people, "align", lambda frame, landmarks: frame[:112, :112])
    frame = np.zeros((720, 1280, 3), np.uint8)
    found, width, box = people.located_face(faces, frame)
    assert found is vector and width == 150 and box == (565, 120, 715, 275)
    assert face(faces, frame)[0] is vector


def test_second_face_cannot_reuse_enrolled_name(tmp_path):
    people = People(tmp_path)
    faces = np.eye(DIM, dtype=np.float32)[:2]
    try:
        assert people.enroll("Ana", [faces[0], faces[0]], 1.0, "first")
        assert not people.enroll("Ana", [faces[1], faces[1]], 2.0, "second")
        assert people.person("Ana")["visitor"] == "first"
        assert people.identify(faces[1]) is None
    finally:
        people.shard.close()
