"""The focus object for teaching and the labels of named objects on screen (research/booth-ux.md,
D63): a pure state machine fed once per detected frame. No I/O, no models; tests in test_focus.py.
"""
import math
from collections import deque
from dataclasses import dataclass, field

Box = tuple[int, int, int, int]  # x1, y1, x2, y2 in frame pixels

# Worn or part of a person: never the focus (the hoodie strings read "lanyard" in the live clip).
BODY = frozenset({"person", "face", "t-shirt", "lanyard", "badge", "hat", "glasses"})
MIN_SIDE = 64  # shortest side at a 1280 px source width, scaled with the frame
STEADY = 0.10  # of the frame width: how far a candidate's center may move in STEADY_S
STEADY_S = 1.0
MOVED = 0.03  # of the frame width: a center shift that counts as moved (static box jitter ~1%)
RECENT_S = 3.0  # appeared or moved this recently: an interaction cue
SCENERY_S = 60.0  # still this long: scenery, until it moves or leaves and returns
GONE_S = 1.0  # out of view, or unfit for the focus, this long: released and forgotten
HOLD_S = 5.0  # a challenger may take the focus only after the focus held it this long
MARGIN = 1.6  # ... and only with this many times the focus's salience
CUE = 1.5  # salience factor per cue: held up, appeared or moved recently
HELD = 0.8  # fraction of a box inside a person or hand box: held up, to take the focus
KEEP = 0.5  # ... to keep it (a phone held at arm's length sits 0.7 inside the person box)
# The teaching zone, a calibration knob for the booth mat (fractions of the frame): an object
# whose whole box is inside it may take the focus without being held.
ZONE = (0.25, 0.5, 0.75, 1.0)
SURE, GUESS = 0.822, 0.772  # things.MATCH, and the bottom of the guess band ("Dylan's phone?")
SET_N, CLEAR_N = 2, 3  # agreeing queries that set a name; queries under GUESS that clear it
DISPLAY_S = 2.0  # display only; fresh recognition still controls visual writes
KIND_SCORE = 0.4  # majority label score from which the focus shows the kind ("Phone?")


@dataclass
class Track:
    """A confirmed track in view on this frame."""
    id: int
    box: Box
    label: str  # the majority label
    score: float  # the majority label's detector score


@dataclass
class _Seen:
    first: float  # first seen since it was last gone for GONE_S
    moved: float  # last moved by MOVED
    anchor: tuple[float, float]  # its center when it last moved
    path: deque  # (time, center) over the last STEADY_S
    last: float = 0.0  # last in view
    continuous: float = 0.0  # source time after the last detection gap


@dataclass
class _Name:
    """A track's name with hysteresis: set after SET_N agreeing queries at GUESS or more,
    cleared after CLEAR_N queries under GUESS in a row."""
    name: str | None = None
    score: float = 0.0
    run: tuple[str | None, int] = (None, 0)  # the last queried name and how many agree
    misses: int = 0
    refreshed: float = 0.0

    def heard(self, name: str | None, score: float, taken: float) -> bool:
        """Count one recognition result; True when the shown name changed."""
        old = self.name
        self.score = score  # Hysteresis keeps a name, never the confidence of an older frame.
        if name is None or score < GUESS:
            self.run, self.misses = (None, 0), self.misses + 1
            if self.misses >= CLEAR_N:
                self.name = None
            return self.name != old
        self.misses = 0
        self.run = (name, self.run[1] + 1 if self.run[0] == name else 1)
        if name != self.name:
            self.name = None  # A conflicting result cannot color the old name green.
        if name == old or self.run[1] >= SET_N:
            self.name = name
        self.refreshed = taken
        return self.name != old


def _center(b: Box) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def inside(a: Box, b: Box) -> float:
    """The fraction of box a inside box b."""
    w = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return w * h / max(1, (a[2] - a[0]) * (a[3] - a[1]))


@dataclass
class Focus:
    """Feed `update` once per detected frame. `focus` is the track to teach (or None),
    `names` the tracks with a shown name, `scenery` the still tracks. `ignored` holds the
    kinds the visitor asked to ignore (things.ignored())."""
    width: int
    height: int
    ignored: set[str] = field(default_factory=set)
    focus: int | None = None
    frozen: bool = False
    scenery: set[int] = field(default_factory=set)
    since: float = 0.0  # when the focus took it
    fit: float = 0.0  # when the focus was last fit to hold it
    now: float = 0.0
    seen: dict[int, _Seen] = field(default_factory=dict)
    named: dict[int, _Name] = field(default_factory=dict)
    visible: set[int] = field(default_factory=set)
    held: list[Box] = field(default_factory=list)  # this frame's person and hand boxes

    def update(self, now: float, tracks: list[Track], people: list[Box], hands: list[Box] = (),
               recognized: dict[int, tuple[str | None, float]] | None = None,
               recognized_at: float | None = None) -> list[tuple]:
        """One frame: its tracks (no person tracks needed), person and hand boxes, and the
        recognition results queried on this frame (track -> things.score(), or (None, 0)).
        Returns events: ("focus", id or None), ("name", id, name or None), ("scenery", id)."""
        self.now, self.held = now, [*people, *hands]
        live = {t.id: t for t in tracks}
        self.named = {i: n for i, n in self.named.items()
                      if i in live and live[i].label not in self.ignored}
        for t in tracks:
            self._see(t)
        self.visible = set(live)
        for i in [i for i, s in self.seen.items() if now - s.last >= GONE_S]:
            del self.seen[i]
            self.named.pop(i, None)
        events = []
        for i, (name, score) in (recognized or {}).items():
            taken = now if recognized_at is None else recognized_at
            if i in live and live[i].label not in self.ignored and self.accepts(i, taken) and \
                    self.named.setdefault(i, _Name()).heard(name, score, taken):
                events.append(("name", i, self.named[i].name))
        still = {i for i, s in self.seen.items() if now - s.moved >= SCENERY_S}
        events += [("scenery", i) for i in sorted(still - self.scenery)]
        self.scenery = still
        old = self.focus
        self._refocus(live)
        return events + [("focus", self.focus)] * (self.focus != old)

    def _see(self, t: Track) -> None:
        c = _center(t.box)
        s = self.seen.setdefault(t.id, _Seen(self.now, self.now, c, deque()))
        if t.id not in self.visible:
            s.continuous = self.now
        s.last = self.now
        s.path.append((self.now, c))
        while s.path[0][0] < self.now - STEADY_S:
            s.path.popleft()
        if math.dist(c, s.anchor) >= MOVED * self.width:
            s.moved, s.anchor = self.now, c

    def _fit(self, t: Track, held: float = HELD) -> bool:
        """May hold the focus: an unnamed object, not worn, ignored, or scenery, large enough,
        and held up or in the teaching zone."""
        x1, y1, x2, y2 = ZONE
        zone = (x1 * self.width, y1 * self.height, x2 * self.width, y2 * self.height)
        return (t.label not in BODY and t.label not in self.ignored and not self.name(t.id)
                and t.id not in self.scenery and self.sized(t)
                and (self._held(t, held) or inside(t.box, zone) == 1))

    def sized(self, t: Track) -> bool:
        return min(t.box[2] - t.box[0], t.box[3] - t.box[1]) >= MIN_SIDE * self.width / 1280

    def accepts(self, track: int, taken: float) -> bool:
        return track in self.visible and taken >= self.seen[track].continuous

    def bind(self, track: int, name: str, taken: float | None = None) -> None:
        taken = self.now if taken is None else taken
        if self.accepts(track, taken):
            self.named[track] = _Name(name=name, score=1.0, run=(name, SET_N), refreshed=taken)

    def forget(self, name: str) -> None:
        self.named = {i: n for i, n in self.named.items() if name not in (n.name, n.run[0])}

    def _held(self, t: Track, held: float = HELD) -> bool:
        return any(inside(t.box, b) >= held for b in self.held)

    def _steady(self, t: Track) -> bool:
        """Watched for STEADY_S and moved less than STEADY in that time."""
        s, c = self.seen[t.id], _center(t.box)
        return self.now - s.first >= STEADY_S and all(
            math.dist(c, p) < STEADY * self.width for _, p in s.path)

    def salience(self, t: Track) -> float:
        """sqrt(area) x closeness to the frame center, times CUE when held up and again when
        it appeared or moved in the last RECENT_S."""
        (cx, cy), s = _center(t.box), self.seen[t.id]
        off = math.hypot(cx / self.width - 0.5, cy / self.height - 0.5) / math.hypot(0.5, 0.5)
        recent = self.now - max(s.first, s.moved) < RECENT_S
        return (math.sqrt((t.box[2] - t.box[0]) * (t.box[3] - t.box[1])) * (1 - off)
                * CUE ** self._held(t) * CUE ** recent)

    def _refocus(self, live: dict[int, Track]) -> None:
        if self.frozen:
            return
        cur = live.get(self.focus)
        if cur is not None and self._fit(cur, KEEP):
            self.fit = self.now
        elif self.focus is not None and not self.name(self.focus) and self.now - self.fit < GONE_S:
            return  # a moment out of view or out of the zone keeps it; a name drops it at once
        else:
            cur = None
        best = max((t for t in live.values() if self._fit(t) and self._steady(t)),
                   key=self.salience, default=None)
        if cur is not None and (best is None or best.id == cur.id or self.now - self.since < HOLD_S
                                or self.salience(best) < MARGIN * self.salience(cur)):
            return
        self.focus = best and best.id
        self.since = self.fit = self.now

    def name(self, track: int) -> str | None:
        """Accepted name for fresh re-verification; display age is separate."""
        n = self.named.get(track)
        return n and n.name

    def names(self, now: float | None = None) -> dict[int, tuple[str, bool]]:
        """Track -> (name, sure) for the shown names: per name only the best-scoring track;
        sure is at least SURE, else a guess."""
        best: dict[str, tuple[int, float]] = {}
        now = self.now if now is None else now
        for i, n in self.named.items():
            if i in self.visible and now - n.refreshed <= DISPLAY_S and n.name and \
                    n.score > best.get(n.name, (0, -1.0))[1]:
                best[n.name] = (i, n.score)
        return {i: (name, s >= SURE) for name, (i, s) in best.items()}

    def freeze(self, track: int | None) -> None:
        """Hold the focus on `track` from the speech start of a naming turn until thaw()."""
        self.focus, self.frozen, self.since, self.fit = track, True, self.now, self.now

    def thaw(self) -> None:
        self.frozen = False

    def target(self, tracks: list[Track]) -> int | None:
        """The object a naming turn binds to: the focus, else the most salient object held up,
        named or not (a visitor can always teach what they hold)."""
        tracks = [t for t in tracks if self.sized(t) and t.label not in self.ignored]
        live = {t.id for t in tracks}
        if self.focus in live:  # a focus that just left the frame is not bound
            return self.focus
        held = [t for t in tracks if t.label not in BODY and self._held(t) and t.id in self.seen]
        best = max(held, key=self.salience, default=None)
        return best and best.id

    def boxes(self, tracks: list[Track], people: list[Box],
              now: float | None = None) -> list[tuple]:
        """Current boxes with bounded object associations; people stay anonymous."""
        names = self.names(now)
        out = [(*b, "", "person") for b in people]
        for t in tracks:
            if t.id in names:
                name, sure = names[t.id]
                out.append((*t.box, name if sure else name + "?", "known" if sure else "guess"))
            elif t.id == self.focus and self.sized(t):
                out.append((*t.box, t.label.capitalize() + "?" if t.score >= KIND_SCORE
                            else "???", "focus"))
            elif t.label not in BODY and (self.sized(t) or t.id in names):
                out.append((*t.box, "", "other"))
        return out
