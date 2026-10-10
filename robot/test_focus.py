"""Focus selection intervals, drawing continuity, and named-track hysteresis on real Focus."""
import pytest

from robot import focus as F
from robot.focus import Focus, Track



@pytest.fixture(autouse=True)
def calibrated_unit_fixture(monkeypatch):
    # Existing selection fixtures use a 64px minimum; the config binding has its own check.
    monkeypatch.setattr(F, "MIN_SIDE", 64)

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
    assert focus[4] == "???"
    assert f.boxes([phone(score=0.3)], [])[0][4] == "???", "detector confidence never names it"


def test_worn_small_objects_hidden_and_outside_zone_fallback() -> None:
    f = Focus(W, H)
    shirt = Track(1, (400, 300, 900, 720), "t-shirt", 0.8)
    small = Track(2, (500, 200, 540, 240), "pen", 0.8)  # short side under MIN_SIDE
    chair = Track(3, (950, 200, 1250, 700), "chair", 0.8)  # beside the person, out of the zone
    run(f, 0, 2, [shirt, small, chair])
    assert f.focus == 3, "the eligible outside-zone object is the fallback"
    mug = Track(4, (500, 500, 600, 600), "mug", 0.8)  # on the mat in the zone, nobody holds it
    run(f, 2, 1.2, [mug], people=())
    assert f.focus is None, "loss retains the selection-change interval"
    run(f, 3.2, 3.0, [mug], people=())
    assert f.focus == 4


def test_hold_and_margin() -> None:
    f = Focus(W, H)
    a, b = phone(), phone((600, 200, 900, 520), 2, "book")  # b: 3x the side, near center
    _, t = run(f, 0, 1.2, [a])
    assert f.focus == 1
    _, t = run(f, t, 4.3, [a, b])
    assert f.focus == 1, "no switch before 5 s"
    _, t = run(f, t, 1.8, [a, b])
    assert f.focus == 2, "a sustained 1.6x challenger takes it after the hold"
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
    assert f.scenery == set() and f.focus is None
    run(f, t + .2, 2, [moved], people=())
    assert f.focus == 1, "moving makes it a candidate again"


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
    assert f.boxes([phone()], [])[0][4:] == ("Dylan's phone", "known")
    _, t = run(f, t, 2 * DT, [phone()], recognized={1: ("Dylan's phone", 0.79)})
    assert f.names() == {1: ("Dylan's phone", True)}
    assert f.boxes([phone()], [])[0][5] == "known", "an accepted label survives a weaker view"
    _, t = run(f, t, 2 * DT, [phone()], recognized={1: (None, 0.0)})
    assert f.names() == {1: ("Dylan's phone", True)}, "two weak queries retain the display"
    events, t = run(f, t, DT, [phone()], recognized={1: ("Dylan's phone", 0.7)})
    assert ("name", 1, None) in events and f.names() == {}, "the third miss clears it"
    run(f, t, 4, [phone()])
    assert f.focus == 1, "unnamed again after the selection interval"


def test_guess_never_takes_focus_and_one_box_per_name() -> None:
    f = Focus(W, H)
    guess = {1: ("Dylan's phone", 0.79), 2: ("Dylan's phone", 0.80)}
    two = [phone(), phone((700, 200, 800, 360), 2)]
    run(f, 0, 2 * DT, two, recognized=guess)
    run(f, 1, 1, two)
    assert f.focus in (1, 2) and f.names() == {}, "competing claims abstain; one unknown may focus"
    assert sorted(b[5] for b in f.boxes(two, [])) == ["focus", "other"]


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
    f.focus = small.id
    assert f.target([small]) is None and f.boxes([small], []) == []
    f.bind(small.id, "wallet")
    assert f.boxes([small], []) == [], "known items follow the same minimum"
    large = phone()
    f.update(2.1, [large], [])
    f.bind(large.id, "wallet")
    f.update(2.2, [large], [], recognized={large.id: (None, 0)})
    assert f.names() == {large.id: ("wallet", True)}
    assert f.named[large.id].score == 0, "display confidence is separate from the fresh query"


@pytest.mark.parametrize("box", [(500, 200, 619, 500), (500, 200, 800, 319)])
def test_size_only_dip_hides_but_retains_accepted_name(monkeypatch, box):
    monkeypatch.setattr(F, "MIN_SIDE", 120)
    f = Focus(W, H)
    large = Track(1, (500, 200, 800, 500), "book", .9)
    small = Track(1, box, "book", .9)
    f.update(100, [large], [])
    f.bind(1, "Visitor's item")
    before = f.named[1], f.epoch(1)
    f.update(100.05, [small], [])
    assert f.name(1) == "Visitor's item"
    assert not f.names() and not f.boxes([small], [])
    assert not f.eligible(small) and f.target([small]) is None
    f.update(100.1, [large], [])
    assert (f.named[1], f.epoch(1)) == before
    assert f.names() == {1: ("Visitor's item", True)}
    assert f.boxes([large], [])[0][4:] == ("Visitor's item", "known")
    assert f.named[1].refreshed == 100, "retention creates no new recognition authority"


@pytest.mark.parametrize("reason", [
    "confidence", "ignore", "exclude", "conflict", "gap", "forget", "miss"])
def test_size_dip_does_not_override_name_invalidation(monkeypatch, reason):
    monkeypatch.setattr(F, "MIN_SIDE", 120)
    f = Focus(W, H)
    large = Track(1, (500, 200, 800, 500), "book", .9)
    small = Track(1, (500, 200, 619, 500), "book", .9)
    f.update(100, [large], [])
    f.bind(1, "Chosen")
    f.update(100.05, [small], [])
    if reason == "confidence":
        f.update(100.1, [Track(1, small.box, "book", F.DETECT_LOW / 2)], [])
    elif reason == "ignore":
        f.ignored.add("book")
        f.update(100.1, [small], [])
    elif reason == "exclude":
        f.excluded[1] = "preference"
        f.update(100.1, [small], [])
    elif reason == "conflict":
        f.update(100.1, [large], [], recognized={1: ("Other", .99)})
    elif reason == "gap":
        f.update(100.3, [], [])
    elif reason == "forget":
        f.forget("Chosen")
    else:
        for now in (100.1, 100.15, 100.2):
            f.update(now, [large], [], recognized={1: (None, 0)})
            assert bool(f.names()) == (now < 100.2), "the third weak query clears the display"
    f.update(100.4, [large], [])
    assert f.name(1) is None and not f.names()


def test_display_age_conflicts_gaps_and_delayed_results():
    f = Focus(W, H)
    a = phone()
    f.update(10, [a], [])
    f.bind(1, "Wallet", 10)
    f.update(11, [a], [])  # skipped query keeps confidence and source age
    assert f.boxes([a], [])[0][4:] == ("Wallet", "known")
    assert f.named[1].refreshed == 10
    assert f.names(12.01), "continuous association has no query-age timeout"
    f.update(11.1, [a], [], recognized={1: ("Phone", 0.99)})
    assert not f.names(), "a conflicting positive cannot color the old name"
    f.update(11.2, [a], [], recognized={1: ("Phone", 0.99)})
    assert f.names() == {1: ("Phone", True)}
    f.update(11.3, [a], [], recognized={1: (None, 0)})
    assert f.names() == {1: ("Phone", True)}, "one weak query retains bounded display continuity"
    f.update(11.4, [], [])
    assert f.name(1) == "Phone", "a short gap retains display-only preference"
    f.update(11.5, [a], [], recognized={1: ("Phone", 0.99)}, recognized_at=11.2)
    assert f.names() == {1: ("Phone", True)}, "a delayed result cannot change the retained display"
    assert f.named[1].score == 0 and f.named[1].refreshed == 11.2
    f.bind(1, "Phone", 11.2)
    assert f.named[1].score == 0, "binding source age also respects the gap"
    f.bind(1, "Phone", 11.5)
    f.ignored = {"phone"}
    f.update(11.6, [a], [])
    assert not f.names(), "ignore clears live associations"
    f.ignored.clear()
    f.update(11.7, [a], [], recognized={1: ("Pending", 0.99)})
    f.forget("Pending")
    assert not f.named, "forget also clears a pending name"


def test_epoch_two_query_acquisition():
    f = Focus(W, H)
    for t in (1791570000.0, 1791570000.5):
        f.update(t, [phone()], [], recognized={1: ("Wallet", 0.9)})
    assert f.names() == {1: ("Wallet", True)}
    assert f.named[1].refreshed == 1791570000.5


def test_drawing_smoothing_raw_authority_motion_and_gap():
    f = Focus(W, H)
    original = phone()
    jitter = phone((510, 190, 590, 370))
    f.update(10, [original], [])
    f.update(10.1, [jitter], [])
    f.focus = 1
    shown = f.boxes([jitter], [])[0][:4]
    assert shown == (504, 196, 596, 364)
    assert jitter.box == (510, 190, 590, 370), "drawing never changes the raw crop box"
    f.update(10.1, [jitter], [])
    assert f.boxes([jitter], [])[0][:4] == shown, "preview repeats cannot smooth twice"
    moved = phone((700, 200, 800, 360))
    f.update(10.2, [moved], [])
    assert f.boxes([moved], [])[0][:4] == moved.box, "large motion snaps immediately"
    f.update(10.3, [], [])
    f.update(10.4, [original], [])
    assert f.boxes([original], [])[0][:4] == original.box, "a gap clears drawing history"
    r = Focus(W, H)
    r.update(10, [original], [])
    r.focus = 1
    assert r.boxes([original], [])[0][:4] == original.box, "new session has no drawing history"


def test_challenger_requires_continuous_priority():
    f = Focus(W, H)
    a = phone()
    b = phone((700, 220, 800, 320), 2, "book")
    c = phone((580, 240, 680, 340), 3, "cup")
    big_b = phone((600, 110, 900, 430), 2, "book")
    big_c = phone((470, 130, 790, 450), 3, "cup")
    _, t = run(f, 0, 7, [a])
    _, t = run(f, t, 1.2, [a, b, c])
    for _ in range(3):
        _, t = run(f, t, 0.5, [a, big_b, c])
        _, t = run(f, t, 0.5, [a, b, big_c])
        assert f.focus == 1, "alternating priorities never build a continuous challenge"
    _, t = run(f, t, 0.5, [a, big_b, c])
    _, t = run(f, t, 0.1, [a, b, c])
    assert f.challenger[0] is None, "losing the margin clears pending priority"
    _, t = run(f, t, 0.7, [a, big_b, c])
    assert f.focus == 1
    f.update(t, [a], [PERSON])
    assert f.challenger[0] is None, "a gap clears pending priority"
    _, t = run(f, t + DT, 0.8, [a, big_b, c])
    assert f.focus == 1
    _, t = run(f, t, 0.4, [a, big_b, c])
    assert f.focus == 2
    f.update(t, [a, big_b, c], [PERSON])
    assert f.challenger[0] is None and f.focus == 2


def test_stationary_size_outlier_and_ignore_clear_drawing():
    f = Focus(W, H)
    a = phone()
    enlarged = phone((400, 100, 700, 460))  # same center, three times the width
    f.update(10, [a], [])
    f.focus = 1
    f.update(10.1, [enlarged], [])
    assert f.boxes([enlarged], [])[0][:4] == (465, 165, 635, 395)
    f.ignored = {"phone"}
    f.update(10.2, [enlarged], [])
    assert f.seen[1].shown is None
    f.ignored.clear()
    f.update(10.3, [a], [])
    assert f.boxes([a], [])[0][:4] == a.box


def test_mixed_known_unknown_short_occlusion_and_config(monkeypatch):
    from robot.config import OBJECT_MIN_SIDE
    monkeypatch.setattr(F, "MIN_SIDE", OBJECT_MIN_SIDE)
    f = Focus(W, H)
    known = phone((400, 200, 600, 400))
    unknown = phone((700, 400, 900, 650), 2)
    run(f, 10, 1.2, [known, unknown])
    f.bind(1, "Chosen name")
    f.update(14.4, [known, unknown], [PERSON])
    assert sorted(b[5] for b in f.boxes([known, unknown], [])) == ["focus", "known"]
    epoch = f.epoch(1)
    f.update(14.5, [unknown], [PERSON])
    assert f.epoch(1) > epoch and f.name(1) == "Chosen name"
    assert any(b[4] == "Chosen name" for b in f.boxes([unknown], [], 14.55))
    f.update(14.6, [known, unknown], [PERSON], recognized={1: ("Wrong", .99)},
             recognized_at=14.4)
    assert f.name(1) == "Chosen name", "a short-gap cached display grants no source authority"
    f.update(14.9, [unknown], [PERSON])
    assert f.name(1) is None
    tiny = phone((0, 0, 119, 250), 3)
    f.update(15, [tiny, unknown], [])
    f.bind(3, "Tiny")
    assert all(b[4] != "Tiny" for b in f.boxes([tiny, unknown], []))


def test_teaching_zone_is_priority_cue_with_general_fallback():
    f = Focus(W, H)
    outside = phone((1050, 200, 1250, 400))
    zone = phone((540, 400, 740, 600), 2)
    run(f, 0, 1.2, [outside], people=())
    assert f.focus == 1, "a sole eligible stable object can be taught anywhere"
    run(f, 1.2, 6.5, [outside, zone], people=())
    assert f.focus == 2, "teaching-zone cue wins after the ordinary sustained challenger"


def test_known_unknown_and_neutral_outlines_keep_source_geometry_and_filtering(monkeypatch):
    from robot.config import OBJECT_MIN_SIDE
    monkeypatch.setattr(F, "MIN_SIDE", OBJECT_MIN_SIDE)
    f = Focus(W, H, ignored={"bottle"})
    known = phone((100, 300, 300, 600))
    unknown = phone((540, 300, 740, 600), 2)
    other = phone((1000, 300, 1200, 600), 3)
    body = phone(PERSON, 4, "person")
    tiny = phone((0, 0, 119, 250), 5)
    ignored = phone((100, 50, 300, 250), 6, "bottle")
    tracks = [known, unknown, other, body, tiny, ignored]
    _, t = run(f, 10, 1.2, tracks)
    f.bind(known.id, "Visitor's chosen name")
    source = f.geometry(tracks)
    for k, (label, score) in enumerate((("wallet", .9), ("bag", .3), ("phone", .7)) * 2):
        varied = phone((540 + k, 300, 740 + k, 600), 2, label, score)
        latest = [known, varied, other, body, tiny, ignored]
        f.update(t + k * DT, latest, [PERSON])
        assert f.focus == unknown.id
        boxes = f.boxes(latest, [PERSON], geometry=source)
        assert boxes == [(*known.box, "Visitor's chosen name", "known"),
                         (*unknown.box, "???", "focus"), (*other.box, "", "other")]
    assert varied.box != source[varied.id] and f.geometry(latest)[varied.id] != source[varied.id]


@pytest.mark.parametrize("reason", ["loss", "recognized", "size"])
def test_global_selection_interval_survives_release(reason):
    f = Focus(W, H)
    a, b = phone(), phone((900, 300, 1050, 500), 2)
    run(f, 0, 1.2, [a, b])
    assert f.focus == 1
    changed = f.changed
    if reason == "recognized":
        f.bind(1, "Chosen")
    transitions = []
    old = f.focus
    for k in range(110):
        now = 1.2 + k * DT
        tracks = [b] if reason == "loss" else [a, b]
        if reason == "size":
            tracks = [phone((500, 200, 550, 360)), b]
        f.update(now, tracks, [PERSON])
        if f.focus != old:
            transitions.append((now, f.focus))
            old = f.focus
        if now - changed < F.SWITCH_S:
            assert f.focus != 2
            assert not any(box[:4] == b.box and box[4] == "???"
                           for box in f.boxes(tracks, []))
    assert transitions[-1][1] == 2
    assert transitions[-1][0] - changed >= F.SWITCH_S
    assert all(b[0] - a[0] >= F.SWITCH_S
               for a, b in zip(transitions, transitions[1:], strict=False))


def test_duplicate_name_abstains_even_when_one_match_becomes_weak():
    f = Focus(W, H)
    a, b = phone(), phone((700, 200, 800, 360), 2)
    f.update(10, [a, b], [])
    f.bind(1, "Chosen")
    f.bind(2, "Chosen")
    f.update(10.1, [a, b], [], recognized={1: (None, 0)})
    assert not f.names(), "a weak view must not release the competing accepted claim"
    assert all(box[5] != "known" for box in f.boxes([a, b], []))
