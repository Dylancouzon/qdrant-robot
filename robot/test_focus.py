"""The focus object's rules on synthetic tracks: take, hold 5 s, margin 1.6, release after 1 s,
freeze, scenery, worn items, the teaching zone, and the name band with hysteresis."""
from robot import focus as F
from robot.focus import Focus, Track

W, H = 1280, 720
PERSON = (300, 0, 1000, 720)
DT = 1 / 15


def run(f: Focus, start: float, seconds: float, tracks, people=(PERSON,), recognized=None):
    """Feed the same tracks at 15 fps; returns the events and the time after the last frame."""
    events, t = [], start
    while t < start + seconds - 1e-9:
        events += f.update(t, tracks, list(people), recognized=recognized)
        t += DT
    return events, t


def phone(box=(500, 200, 600, 360), i=1, label="phone", score=0.6) -> Track:
    return Track(i, box, label, score)


def test_takes_held_object_and_labels_it() -> None:
    f = Focus(W, H)
    events, t = run(f, 0, 0.9, [phone()])
    assert f.focus is None, "watched for a second first"
    events, _ = run(f, t, 0.2, [phone()])
    assert f.focus == 1 and ("focus", 1) in events
    [focus] = [b for b in f.boxes([phone()], [PERSON]) if b[5] == "focus"]
    assert focus[4] == "Phone?"
    assert f.boxes([phone(score=0.2)], [])[0][4] == "???", "a weak kind shows ???"


def test_worn_items_small_boxes_and_loose_objects_never_take_it() -> None:
    f = Focus(W, H)
    shirt = Track(1, (400, 300, 900, 720), "t-shirt", 0.8)
    small = Track(2, (500, 200, 540, 240), "pen", 0.8)  # short side under MIN_SIDE
    chair = Track(3, (950, 200, 1250, 700), "chair", 0.8)  # beside the person, out of the zone
    run(f, 0, 2, [shirt, small, chair])
    assert f.focus is None
    mug = Track(4, (500, 500, 600, 600), "mug", 0.8)  # on the mat in the zone, nobody holds it
    run(f, 2, 1.2, [mug], people=())
    assert f.focus == 4


def test_hold_and_margin() -> None:
    f = Focus(W, H)
    a, b = phone(), phone((600, 200, 900, 520), 2, "book")  # b: 3x the side, near center
    _, t = run(f, 0, 1.2, [a])
    assert f.focus == 1
    _, t = run(f, t, 4.3, [a, b])
    assert f.focus == 1, "no switch before 5 s"
    _, t = run(f, t, 0.8, [a, b])
    assert f.focus == 2, "a 1.6x challenger takes it after 5 s"
    f = Focus(W, H)
    _, t = run(f, 0, 1.2, [a])
    c = phone((480, 180, 620, 380), 3, "camera")  # about 1.4x: under the margin
    run(f, t, 8, [a, c])
    assert f.focus == 1


def test_release_after_one_second() -> None:
    f = Focus(W, H)
    _, t = run(f, 0, 1.2, [phone()])
    _, t = run(f, t, 0.8, [])
    assert f.focus == 1, "a moment out of view keeps it"
    _, t = run(f, t, 0.4, [])
    assert f.focus is None


def test_freeze() -> None:
    f = Focus(W, H)
    a, b = phone(), phone((600, 200, 900, 520), 2, "book")
    _, t = run(f, 0, 6, [a])
    f.freeze(1)
    _, t = run(f, t, 3, [a, b])
    assert f.focus == 1, "frozen while naming"
    _, t = run(f, t, 3, [])
    assert f.focus == 1, "frozen even out of view: the naming turn decides"
    f.thaw()
    run(f, t, 1.2, [b])
    assert f.focus == 2


def test_scenery() -> None:
    f = Focus(W, H)
    mug = Track(1, (500, 500, 600, 600), "mug", 0.8)
    events, t = run(f, 0, 62, [mug], people=())
    assert ("scenery", 1) in events and f.focus is None and 1 in f.scenery
    events, t = run(f, t, 0.2, [])
    back, t = run(f, t, 0.2, [mug], people=())
    assert 1 in f.scenery and events + back == [], "a short miss keeps the mark"
    moved = Track(1, (560, 500, 660, 600), "mug", 0.8)
    run(f, t, 0.2, [moved], people=())
    assert f.scenery == set() and f.focus == 1, "moving makes it a candidate again"


def test_name_band_and_hysteresis() -> None:
    f = Focus(W, H)
    _, t = run(f, 0, 1.2, [phone()])
    assert f.focus == 1
    sure = {1: ("Dylan's phone", 0.85)}
    events, t = run(f, t, DT, [phone()], recognized=sure)
    assert f.names() == {} and f.focus == 1, "one query does not set a name"
    events, t = run(f, t, DT, [phone()], recognized=sure)
    assert ("name", 1, "Dylan's phone") in events and f.names() == {1: ("Dylan's phone", True)}
    assert f.focus is None, "a named object never holds the focus"
    assert f.boxes([phone()], [], sure)[0][4:] == ("Dylan's phone", "known")
    _, t = run(f, t, 2 * DT, [phone()], recognized={1: ("Dylan's phone", 0.79)})
    assert f.names() == {1: ("Dylan's phone", False)}
    assert f.boxes([phone()], [], {1: ("Dylan's phone", 0.79)})[0][4:] == (
        "Dylan's phone?", "guess")
    _, t = run(f, t, 2 * DT, [phone()], recognized={1: (None, 0.0)})
    assert f.names(), "two misses keep it"
    events, t = run(f, t, DT, [phone()], recognized={1: ("Dylan's phone", 0.7)})
    assert ("name", 1, None) in events and f.names() == {}, "the third miss clears it"
    run(f, t, 0.2, [phone()])
    assert f.focus == 1, "unnamed again: it may take the focus"


def test_guess_never_takes_focus_and_one_box_per_name() -> None:
    f = Focus(W, H)
    guess = {1: ("Dylan's phone", 0.79), 2: ("Dylan's phone", 0.80)}
    two = [phone(), phone((700, 200, 800, 360), 2)]
    run(f, 0, 2 * DT, two, recognized=guess)
    run(f, 1, 1, two)
    assert f.focus is None and f.names() == {2: ("Dylan's phone", False)}
    kinds = [b[5] for b in f.boxes(two, [], guess)]
    assert kinds == ["other", "guess"], kinds


def test_target_is_the_held_object_even_when_named() -> None:
    f = Focus(W, H)
    run(f, 0, 2 * DT, [phone()], recognized={1: ("Dylan's phone", 0.9)})
    assert f.focus is None and f.target([phone()]) == 1


def test_steady_gate() -> None:
    f = Focus(W, H)
    t = 0.0
    for k in range(10):  # flung across the frame: over 10% of the width per second
        f.update(t, [phone((100 + 60 * k, 200, 200 + 60 * k, 360))], [(0, 0, W, H)])
        t += DT
    assert F.STEADY * W < 60 * 9 and f.focus is None



def test_target_skips_a_departed_focus() -> None:
    f = Focus(W, H)
    run(f, 0, 1.2, [phone()])
    assert f.focus == 1 and f.target([phone()]) == 1
    assert f.target([]) is None, "the focus left the frame: nothing to bind"


def test_small_target_and_fresh_scores() -> None:
    f = Focus(W, H)
    small = phone((500, 200, 560, 360))
    run(f, 0, 2, [small])
    f.freeze(small.id)
    assert f.target([small]) is None and f.boxes([small], []) == []
    f.bind(small.id, "wallet")
    assert f.boxes([small], [], {small.id: ("wallet", 1)})[0][4:] == ("wallet", "known")
    assert f.boxes([small], [])[0][4:] == ("", "other")
    f.update(3, [small], [], recognized={small.id: (None, 0)})
    assert f.name(small.id) == "wallet" and not f.names()[small.id][1]
    assert all(b[5] != "known" for b in f.boxes([small], [], {small.id: (None, 0)}))
