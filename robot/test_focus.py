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
    _, t = run(f, t, DT, [phone()], recognized=sure)  # fresh evidence resets weak-query count
    _, t = run(f, t, 2 * DT, [phone()], recognized={1: (None, 0.0)})
    assert f.names() == {1: ("Dylan's phone", True)}, "two weak queries retain the display"
    events, t = run(f, t, DT, [phone()], recognized={1: ("Dylan's phone", 0.7)})
    assert ("name", 1, None) in events and f.names() == {}, "the third miss clears it"
    run(f, t, 4, [phone()])
    assert f.focus == 1, "unnamed again after the selection interval"


def test_repeated_guess_queries_bound_green_but_keep_verification_preference():
    f = Focus(W, H)
    for now in (10, 10.1):
        f.update(now, [phone()], [], recognized={1: ("Chosen", .9)})
    for now in (10.2, 10.3):
        f.update(now, [phone()], [], recognized={1: ("Chosen", .797)})
        assert f.names() == {1: ("Chosen", True)}
    for i in range(100):
        f.update(10.4 + i / 10, [phone()], [], recognized={1: ("Chosen", .797)})
        assert f.names() == {1: ("Chosen", False)} and f.name(1) == "Chosen"
        assert all(b[5] != "known" for b in f.boxes([phone()], []))
    f.update(21, [phone()], [], recognized={1: ("Chosen", .9)})
    assert f.names() == {1: ("Chosen", True)}
    for i in range(100):
        f.update(21.1 + i / 10, [phone()], [])
    assert f.names() == {1: ("Chosen", True)}, "skipped queries do not consume hysteresis"
    f.update(32, [phone()], [], recognized={1: ("Different", .9)})
    assert not f.names() and f.name(1) is None, "a competing strong claim abstains immediately"


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
def test_size_only_dip_keeps_grey_geometry_but_retains_accepted_name(monkeypatch, box):
    monkeypatch.setattr(F, "MIN_SIDE", 120)
    f = Focus(W, H)
    large = Track(1, (500, 200, 800, 500), "book", .9)
    small = Track(1, box, "book", .9)
    f.update(100, [large], [])
    f.bind(1, "Visitor's item")
    before = f.named[1], f.epoch(1)
    f.update(100.05, [small], [])
    assert f.name(1) == "Visitor's item"
    assert not f.names() and f.boxes([small], [])[0][4:] == ("", "other")
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


@pytest.mark.parametrize("named, selected", [(True, False), (False, True), (False, False)])
def test_continuous_raw_motion_never_snaps_from_drawing_lag(named, selected):
    f = Focus(W, H)
    previous = None
    for k in range(20):
        raw = phone((100 + 40 * k, 200, 280 + 40 * k, 380))
        f.update(10 + k * DT, [raw], [])
        if k == 0 and named:
            f.bind(raw.id, "My phone")
        if selected:
            f.focus = raw.id
        [box] = f.boxes([raw], [])
        assert box[5] == ("known" if named else "focus" if selected else "other")
        if previous:
            step = (box[0] + box[2] - previous[0] - previous[2]) / 2
            assert 0 < step <= 40, "steady raw motion cannot cause a larger drawing jump"
        assert raw.box == (100 + 40 * k, 200, 280 + 40 * k, 380)
        previous = box
    assert raw.box[0] - previous[0] <= 40 * (1 - F.SMOOTH) / F.SMOOTH + 1
    abrupt = phone((20, 200, 200, 380))
    f.update(12, [abrupt], [])
    assert f.geometry([abrupt])[1] == abrupt.box, "real discontinuities still snap"


@pytest.mark.parametrize("dip", [phone((510, 210, 570, 270)), phone(score=0.12)])
def test_eligibility_dip_keeps_grey_drawing_history(dip):
    f = Focus(W, H)
    original = phone()
    f.update(10, [original], [])
    f.focus = original.id
    f.update(10 + DT, [dip], [])
    assert f.seen[1].shown is not None
    assert f.boxes([dip], [])[0][5] == "other" and not f.eligible(dip)
    assert f.target([dip]) is None, "retained geometry cannot authorize naming"
    hidden = f.geometry([dip])[1]
    recovered = phone((520, 200, 620, 360))
    f.update(10 + 2 * DT, [recovered], [])
    shown = f.boxes([recovered], [])[0][:4]
    assert shown != recovered.box, "recovery continues the existing filter"
    assert all(abs(b - a) <= F.SMOOTH * abs(c - a) + 1
               for a, b, c in zip(hidden, shown, recovered.box, strict=True))
    assert recovered.box == (520, 200, 620, 360)
    f.update(10.5, [], [])
    assert f.seen[1].shown is None, "a real absence clears retained geometry"


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
    assert all(b[4] != "Chosen name" for b in f.boxes([unknown], [], 14.55)), \
        "a departed track cannot draw on another source"
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


@pytest.mark.parametrize(('detector', 'descriptor', 'displayed'), [
    (.143188, .7754759788513184, False),  # Recorded face crop: both current signals weak.
    (.143188, F.GUESS, False),
    (.143188, F.SURE - .0001, False),
    (.143188, F.SURE, True),
    (.143188, 1, True),
    (F.DISPLAY_CONFIDENCE, .7754759788513184, True),
    (.9, .2544, True),
])
def test_display_requires_one_current_positive_signal(detector, descriptor, displayed):
    f = Focus(W, H)
    t = phone((518, 142, 697, 386), score=.9)
    f.update(10, [t], [])
    f.bind(t.id, 'Chosen')
    t = phone(t.box, score=detector)
    f.update(10.1, [t], [], recognized={t.id: ('Chosen', descriptor)})
    assert bool(f.names()) is displayed
    assert f.boxes([t], [])[0][4:] == (("Chosen", "known") if displayed else ("", "other"))
    assert f.name(t.id) == 'Chosen', 'display rejection retains the preference for re-query'
    assert f.named[t.id].score == descriptor, 'retained display confidence never replaces evidence'
    assert f.named[t.id].confidence == 1
    assert f.eligible(t, pending=True), 'the crop remains eligible for fresh re-verification'
    f.update(10.2, [t], [])
    assert bool(f.names()) is displayed, 'skipped queries do not change either signal'
    assert f.named[t.id].misses == int(descriptor < F.SURE)


def test_two_weak_signals_hide_until_detector_or_descriptor_recovers():
    f = Focus(W, H)
    t = phone((518, 142, 697, 386), score=.143188)
    f.update(10, [t], [])
    f.bind(t.id, 'Chosen')
    f.update(10.1, [t], [], recognized={t.id: ('Chosen', .7754759788513184)})
    assert not f.names() and not f.eligible(t)
    refreshed = f.named[t.id].refreshed
    strong_detector = phone(t.box, score=.9)
    f.update(10.2, [strong_detector], [])
    assert f.names() == {t.id: ('Chosen', True)}
    assert f.named[t.id].refreshed == refreshed, 'detector recovery invents no crop authority'
    assert f.named[t.id].score < F.SURE
    f.update(10.3, [t], [])
    assert not f.names(), 'the retained association cannot override two weak signals'
    f.update(10.4, [t], [], recognized={t.id: ('Chosen', F.SURE)})
    assert f.names() == {t.id: ('Chosen', True)} and f.eligible(t)
    assert f.named[t.id].score == F.SURE and f.named[t.id].refreshed == 10.4


def test_item_exclusion_requires_match_and_counts_only_actual_misses():
    f = Focus(W, H)
    t = phone()
    f.update(10, [t], [])
    f.exclude(t.id, None)
    assert not f.excluded and f.seen[t.id].exclude_misses == 0
    f.exclude(t.id, 'preference')
    for miss in (1, 2):
        f.exclude(t.id, None)
        assert f.excluded == {t.id: 'preference'}
        assert not f.boxes([t], []) and f.seen[t.id].exclude_misses == miss
        f.update(10 + miss * .1, [t], [])
        assert f.seen[t.id].exclude_misses == miss, 'skipped queries cannot consume continuity'
    f.exclude(t.id, None)
    assert not f.excluded and f.seen[t.id].exclude_misses == 0
    assert not f.excluded, 'third actual miss releases a different object on the same track'
    f.update(10.3, [t], [])
    assert f.boxes([t], []), 'the next matched source admits its own outline'


def test_item_match_and_explicit_replacement_reset_exclusion_misses():
    f = Focus(W, H)
    t = phone()
    f.update(10, [t], [])
    f.exclude(t.id, 'first')
    for preference in ('first', 'new explicit item'):
        f.exclude(t.id, None)
        f.exclude(t.id, None)
        f.exclude(t.id, preference)
        assert f.excluded == {t.id: preference} and f.seen[t.id].exclude_misses == 0
    f.exclude(t.id, None)
    assert f.excluded == {t.id: 'new explicit item'} and f.seen[t.id].exclude_misses == 1


def test_item_gap_clears_exclusion_and_counter_before_new_match():
    f = Focus(W, H)
    t = phone()
    f.update(10, [t], [])
    f.exclude(t.id, 'old')
    f.exclude(t.id, None)
    f.exclude(t.id, None)
    f.update(10.3, [], [])
    assert not f.excluded and f.seen[t.id].exclude_misses == 0
    f.update(10.4, [t], [])
    f.exclude(t.id, None)
    assert not f.excluded, 'return has no inherited preference authority'
    f.exclude(t.id, 'new')
    f.exclude(t.id, None)
    assert f.excluded == {t.id: 'new'} and f.seen[t.id].exclude_misses == 1


def test_low_drawing_needs_raw_admission_and_never_grants_focus_or_actions():
    f = Focus(W, H)
    low = phone(score=F.DETECT_LOW)
    f.update(10, [low], [])
    assert f.seen[1].shown and not f.boxes([low], []), 'filter history is not admission'
    high = phone(score=F.DISPLAY_CONFIDENCE)
    f.update(10.1, [high], [])
    assert f.boxes([high], [])
    f.focus = low.id
    for step in range(1, 31):
        f.update(10.1 + step / 15, [low], [])
        expected = ('???', 'focus') if f.focus == low.id else ('', 'other')
        assert f.boxes([low], [])[0][4:] == expected
        assert not f.eligible(low) and f.target([low]) is None and not f._fit(low)
        assert f.seen[1].admitted == f.now, 'full-size LOW continuity renews size grace only'
    below = phone(score=F.DETECT_LOW - .0001)
    f.update(12.2, [below], [])
    assert not f.boxes([below], [])
    f.update(12.3, [], [])
    assert not f.boxes([low], []) and f.seen[1].admitted is None
    f.update(12.4, [low], [])
    assert not f.boxes([low], []), 'a returning weak track needs a new raw admission'


def test_selected_unknown_style_survives_alternating_high_low_source_confidence():
    f = Focus(W, H)
    high = phone(score=F.DISPLAY_CONFIDENCE)
    _, taken = run(f, 10, 1.2, [high], people=())
    assert f.focus == high.id
    changed = f.changed
    for step in range(60):
        low = step % 2 == 0
        current = phone(score=F.DETECT_LOW if low else F.DISPLAY_CONFIDENCE)
        f.update(taken + step * DT, [current], [])
        source = f.geometry([current])
        assert f.boxes([current], [], geometry=source)[0][4:] == ('???', 'focus')
        assert f.focus == current.id and f.changed == changed
        assert f.eligible(current) is not low
        assert f.target([current]) == (None if low else current.id)
        assert f._fit(current) is not low
    f.checking.add(current.id)
    assert not f.boxes([current], [], geometry=source)
    f.checking.clear()
    f.exclude(current.id, 'preference')
    assert not f.boxes([current], [], geometry=source)
    f.restore('preference')
    f.ignored.add(current.label)
    assert not f.boxes([current], [], geometry=source)
    f.ignored.clear()
    f.update(f.now + DT, [], [])
    assert not f.boxes([current], [], geometry=source), 'departed source stays hidden'


def test_size_grace_expires_without_weak_observation_renewal(monkeypatch):
    monkeypatch.setattr(F, 'MIN_SIDE', 120)
    f = Focus(W, H)
    high = phone((500, 200, 700, 500))
    small = phone((500, 200, 619, 500), score=.21)
    f.update(10, [high], [])
    for offset in (.05, .15, .199):
        f.update(10 + offset, [small], [])
        assert f.boxes([small], [])[0][4:] == ('', 'other')
        assert not f.eligible(small) and f.target([small]) is None
        assert f.seen[1].admitted == 10
    f.update(10.201, [small], [])
    assert not f.boxes([small], [])
    f.update(10.25, [high], [])
    assert f.boxes([high], []) and f.seen[1].admitted == 10.25
    f.exclude(1, 'ignored-item')
    assert not f.boxes([high], []) and f.seen[1].admitted is None
    f.restore('ignored-item')
    assert not f.boxes([high], []), 'Restore alone invents no source admission'
    f.update(10.3, [high], [])
    assert f.boxes([high], [])


def test_size_grace_follows_admitted_low_full_size_sources(monkeypatch):
    monkeypatch.setattr(F, 'MIN_SIDE', 120)
    f = Focus(W, H)
    high = phone((500, 200, 700, 500))
    low = phone(high.box, score=F.DETECT_LOW)
    small = phone((500, 200, 619, 500), score=F.DETECT_LOW)
    f.update(10, [high], [])
    run(f, 10.1, 1.2, [low], people=())
    admitted = f.seen[1].admitted
    assert admitted > 11 and not f.eligible(low)
    f.update(admitted + .067, [small], [])
    assert f.boxes([small], [])[0][4:] == ('', 'other')
    f.update(admitted + .199, [small], [])
    assert f.boxes([small], []) and f.seen[1].admitted == admitted
    f.update(admitted + .201, [small], [])
    assert not f.boxes([small], [])


def test_source_geometry_admission_is_frozen_but_current_safety_can_remove_it(monkeypatch):
    monkeypatch.setattr(F, 'MIN_SIDE', 120)
    f = Focus(W, H)
    high = phone((500, 200, 700, 500))
    f.update(10, [high], [])
    source = f.geometry([high])
    small = phone((500, 200, 619, 500), score=.21)
    f.update(10.25, [small], [])
    assert not f.boxes([small], []), 'the newer source has exhausted size grace'
    assert f.boxes([small], [], geometry=source) == [(*high.box, '', 'other')]
    f.ignored.add('phone')
    assert not f.boxes([small], [], geometry=source)
    f.ignored.clear()
    f.update(10.3, [], [])
    assert not f.boxes([high], [], geometry=source), 'departed pixels cannot be drawn'
