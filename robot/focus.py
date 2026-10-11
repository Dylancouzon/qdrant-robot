"""The focus object for teaching and the labels of named objects on screen (research/booth-ux.md,
D63): a pure state machine fed once per detected frame. No I/O, no models; tests in test_focus.py.
"""
import math
from collections import deque
from dataclasses import dataclass, field

from robot.config import DETECT_LOW, DISPLAY_CONFIDENCE, OBJECT_MIN_SIDE
from robot.settings import settings

Box = tuple[int, int, int, int]  # x1, y1, x2, y2 in frame pixels

# Worn or part of a person: never the focus (the hoodie strings read "lanyard" in the live clip).
BODY = frozenset({"person", "face", "t-shirt", "lanyard", "badge", "hat", "glasses"})
MIN_SIDE = OBJECT_MIN_SIDE
STEADY = 0.10  # of the frame width: how far a candidate's center may move in STEADY_S
STEADY_S = 1.0
MOVED = 0.03  # of the frame width: a center shift that counts as moved (static box jitter ~1%)
RECENT_S = 3.0  # appeared or moved this recently: an interaction cue
SCENERY_S = 60.0  # still this long: scenery, until it moves or leaves and returns
GONE_S = 1.0  # out of view, or unfit for the focus, this long: released and forgotten
SWITCH_S = 3.0  # minimum interval between unknown-focus transitions, including releases
HOLD_S = 5.0  # a challenger may take the focus only after the focus held it this long
CHALLENGE_S = 1.0  # the same challenger must exceed the margin continuously
SMOOTH = 0.35  # drawing coordinates only, one update per source frame
SNAP = 0.08  # frame-width center change: follow large movement, smooth size changes
MARGIN = 1.6  # ... and only with this many times the focus's salience
CUE = 1.5  # salience factor per cue: held up, appeared or moved recently
HELD = 0.8  # fraction of a box inside a person or hand box: held up, to take the focus
# The teaching zone, a calibration knob for the booth mat (fractions of the frame): an object
# whose whole box is inside it may take the focus without being held.
ZONE = (0.25, 0.5, 0.75, 1.0)
SET_N, CLEAR_N = 2, 3  # agreeing queries that set a name; weak queries that clear it
OCCLUSION_S = 0.2  # drawing only; a gap invalidates every older recognition result


@dataclass
class Track:
    """A confirmed track in view on this frame."""
    id: int
    box: Box
    label: str  # the majority label
    score: float  # current detection confidence, separate from the majority category


@dataclass
class _Seen:
    first: float  # first seen since it was last gone for GONE_S
    moved: float  # last moved by MOVED
    anchor: tuple[float, float]  # its center when it last moved
    path: deque  # (time, center) over the last STEADY_S
    last: float = 0.0  # last in view
    continuous: float = 0.0  # source time after the last detection gap
    shown: tuple | None = None  # smoothed drawing box; never used for crops or selection
    track: Track | None = None
    epoch: int = 0
    exclude_misses: int = 0  # consecutive queried misses of a continuous item preference
    admitted: float | None = None  # last full-size source after raw UI admission


@dataclass
class _Name:
    """Set a name after agreeing queries within the near-match band.
    Weak queries fade confidence, and queries below the band clear the name."""
    name: str | None = None
    score: float = 0.0  # latest query, never retained to authorize a write
    confidence: float = 0.0  # accepted display confidence through bounded weak queries
    run: tuple[str | None, int] = (None, 0)  # the last queried name and how many agree
    misses: int = 0
    refreshed: float = 0.0

    def heard(self, name: str | None, score: float, taken: float) -> bool:
        """Count one recognition result; True when the shown name changed."""
        old = self.name
        self.score = score
        self.misses = self.misses + 1 if name is None or score < settings.match else 0
        if name is None or score < (settings.match - settings.guess_band):
            self.run = None, 0
            if self.misses >= CLEAR_N:
                self.name, self.confidence = None, 0.0
            return self.name != old
        self.run = (name, self.run[1] + 1 if self.run[0] == name else 1)
        if name != self.name:
            self.name, self.confidence = None, 0.0  # Conflicting positives abstain immediately.
        if name == old or self.run[1] >= SET_N:
            self.name = name
            self.confidence = score if self.misses >= CLEAR_N else max(self.confidence, score)
        self.refreshed = taken
        return self.name != old


def _center(b: Box) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def drawing_box(shown: tuple, previous: Box, current: Box, width: int) -> tuple:
    """Smooth stationary jitter, and follow measured motion without predicting positions."""
    motion = math.dist(_center(previous), _center(current))
    if motion > SNAP * width:
        return current
    blend = max(SMOOTH, min(1.0, motion / (MOVED * width)))
    return tuple(a + blend * (b - a) for a, b in zip(shown, current, strict=True))


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
    scenery: set[int] = field(default_factory=set)
    changed: float = -math.inf  # last selection change, retained across loss and recognition
    since: float = 0.0  # when the focus took it
    fit: float = 0.0  # when the focus was last fit to hold it
    now: float = 0.0
    seen: dict[int, _Seen] = field(default_factory=dict)
    named: dict[int, _Name] = field(default_factory=dict)
    visible: set[int] = field(default_factory=set)
    challenger: tuple[int | None, float] = (None, 0.0)
    held: list[Box] = field(default_factory=list)  # this frame's person and hand boxes
    excluded: dict[int, str] = field(default_factory=dict)  # matched item preference ids
    checking: set[int] = field(default_factory=set)  # returning items await preference verification

    def update(self, now: float, tracks: list[Track], people: list[Box], hands: list[Box] = (),
               recognized: dict[int, tuple[str | None, float]] | None = None,
               recognized_at: float | None = None) -> list[tuple]:
        """One frame: its tracks (no person tracks needed), person and hand boxes, and the
        recognition results queried on this frame (track -> things.score(), or (None, 0)).
        Returns events: ("focus", id or None), ("name", id, name or None), ("scenery", id)."""
        self.now, self.held = now, [*people, *hands]
        live = {t.id: t for t in tracks}
        for i, s in self.seen.items():
            if i not in live and now > s.last:
                s.epoch += 1
                s.continuous = now
                if now - s.last > OCCLUSION_S:
                    s.admitted = None
                    self.named.pop(i, None)
                    self.excluded.pop(i, None)
                    s.exclude_misses = 0
                    s.shown = None
        # Raw size gates names, actions, and queries without erasing a continuous preference.
        self.named = {i: n for i, n in self.named.items()
                      if i not in live or (self.confident(live[i], pending=True) and
                      live[i].label not in self.ignored and i not in self.excluded and
                      (n.name or self.sized(live[i])))}
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
        gap = t.id not in self.visible
        if gap:
            s.continuous = self.now
            s.admitted = None
            s.shown = None
            if self.now - s.last > OCCLUSION_S:
                self.named.pop(t.id, None)
                self.excluded.pop(t.id, None)
                s.exclude_misses = 0
        if t.label in self.ignored or t.id in self.excluded:
            s.shown = None
            s.admitted = None
        elif s.shown is None or (s.track and
                math.dist(_center(s.track.box), c) > SNAP * self.width):
            s.shown = t.box
            s.admitted = None
        elif self.now > s.last:
            s.shown = drawing_box(s.shown, s.track.box, t.box, self.width)
        if self.eligible(t) or (s.admitted is not None and self.sized(t) and
                t.score >= DETECT_LOW and t.id not in self.checking):
            s.admitted = self.now
        s.last, s.track = self.now, t
        s.path.append((self.now, c))
        while s.path[0][0] < self.now - STEADY_S:
            s.path.popleft()
        if math.dist(c, s.anchor) >= MOVED * self.width:
            s.moved, s.anchor = self.now, c

    def _fit(self, t: Track) -> bool:
        """An eligible unknown object. Held and teaching-zone cues raise priority."""
        return (t.label not in BODY and t.score >= DISPLAY_CONFIDENCE and self.eligible(t) and
                not self.names().get(t.id, (None, False))[1]
                and t.id not in self.scenery)

    def sized(self, t: Track) -> bool:
        return min(t.box[2] - t.box[0], t.box[3] - t.box[1]) >= MIN_SIDE * self.width / 1280

    def confident(self, t: Track, *, pending: bool = False) -> bool:
        """A sure name can continue at LOW; pending associations can only be reverified."""
        name = self.named.get(t.id)
        known = name and name.name and (pending or name.score >= settings.match)
        return t.score >= (DETECT_LOW if known else DISPLAY_CONFIDENCE)

    def eligible(self, t: Track, *, pending: bool = False) -> bool:
        """Pending preference checks preserve drawing history, never action authority."""
        return (self.sized(t) and self.confident(t, pending=pending) and
                t.label not in self.ignored and t.id not in self.excluded and
                (pending or t.id not in self.checking))

    def drawable(self, t: Track) -> bool:
        """Previously admitted, currently matched LOW tracks retain drawing, not action rights."""
        seen = self.seen.get(t.id)
        return bool(t.id in self.visible and seen and seen.admitted is not None and
                    t.score >= DETECT_LOW and t.label not in self.ignored and
                    t.id not in self.excluded and t.id not in self.checking and
                    (self.sized(t) or 0 <= self.now - seen.admitted <= OCCLUSION_S))

    def epoch(self, track: int) -> int:
        return self.seen[track].epoch

    def accepts(self, track: int, taken: float) -> bool:
        return track in self.visible and taken >= self.seen[track].continuous

    def bind(self, track: int, name: str, taken: float | None = None) -> None:
        taken = self.now if taken is None else taken
        if self.accepts(track, taken):
            self.named[track] = _Name(name=name, score=1.0, confidence=1.0,
                                      run=(name, SET_N), refreshed=taken)

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
        x1, y1, x2, y2 = ZONE
        zone = (x1 * self.width, y1 * self.height, x2 * self.width, y2 * self.height)
        return (math.sqrt((t.box[2] - t.box[0]) * (t.box[3] - t.box[1])) * (1 - off)
                * CUE ** self._held(t) * CUE ** recent * CUE ** (inside(t.box, zone) == 1))

    def _refocus(self, live: dict[int, Track]) -> None:
        cur = live.get(self.focus)
        if cur is not None and self._fit(cur):
            self.fit = self.now
        elif self.focus is not None and not self.name(self.focus) and self.now - self.fit < GONE_S:
            self.challenger = None, 0.0
            return  # a brief loss keeps the selection; a confirmed name releases it
        else:
            cur = None
        best = max((t for t in live.values() if self._fit(t) and self._steady(t)),
                   key=self.salience, default=None)
        if cur is not None and (best is None or best.id == cur.id or self.now - self.since < HOLD_S
                                or self.salience(best) < MARGIN * self.salience(cur)):
            self.challenger = None, 0.0
            return
        if cur is not None:
            if best.id != self.challenger[0]:
                self.challenger = best.id, self.now
            if self.now - self.challenger[1] < CHALLENGE_S:
                return
        self.challenger = None, 0.0
        next_focus = best and best.id
        if next_focus is not None and self.now - self.changed < SWITCH_S:
            next_focus = self.focus if cur is not None else None
        if next_focus != self.focus:
            self.changed = self.now
            self.focus = next_focus
            self.since = self.fit = self.now

    def exclude(self, track: int, preference: str | None) -> None:
        """Apply one fresh preference result; retain a matched item through two actual misses."""
        seen = self.seen.get(track)
        if seen is None:
            return
        if preference:
            self.excluded[track] = preference
            seen.exclude_misses = 0
            seen.admitted = None
        elif track in self.excluded:
            seen.exclude_misses += 1
            if seen.exclude_misses >= CLEAR_N:
                self.excluded.pop(track)
                seen.exclude_misses = 0

    def restore(self, preference: str) -> None:
        """Clear display continuity for a restored item preference."""
        for i in [i for i, p in self.excluded.items() if p == preference]:
            self.excluded.pop(i)
            if i in self.seen:
                self.seen[i].exclude_misses = 0

    def name(self, track: int) -> str | None:
        """Accepted name for fresh re-verification; display age is separate."""
        n = self.named.get(track)
        return n and n.name

    def names(self, now: float | None = None) -> dict[int, tuple[str, bool]]:
        """Continuous eligible associations. Competing claims abstain together."""
        grouped: dict[str, list[tuple[int, float]]] = {}
        now = self.now if now is None else now
        for i, n in self.named.items():
            seen = self.seen.get(i)
            if seen and seen.track and self.confident(seen.track) and \
                    self.eligible(seen.track, pending=True) and \
                    (i in self.visible or now - seen.last <= OCCLUSION_S) and \
                    n.name and n.confidence >= (settings.match - settings.guess_band):
                grouped.setdefault(n.name, []).append((i, n.confidence))
        return {hits[0][0]: (name, hits[0][1] >= settings.match)
                for name, hits in grouped.items() if len(hits) == 1}

    def target(self, tracks: list[Track]) -> int | None:
        """The object a naming turn binds to: the focus, else the most salient object held up,
        named or not (a visitor can always teach what they hold)."""
        tracks = [t for t in tracks if self.eligible(t)]
        live = {t.id for t in tracks}
        if self.focus in live:  # a focus that just left the frame is not bound
            return self.focus
        held = [t for t in tracks if t.label not in BODY and self._held(t) and t.id in self.seen]
        best = max(held, key=self.salience, default=None)
        return best and best.id

    def boxes(self, tracks: list[Track], people: list[Box],
              now: float | None = None, *, geometry: dict[int, Box] | None = None) -> list[tuple]:
        """Current object labels on current or explicitly supplied source geometry."""
        names = self.names(now)
        drawn = self.geometry(tracks) if geometry is None else geometry
        out = []
        for t in tracks:
            if t.label in BODY or t.id not in drawn or t.id not in self.visible or \
                    t.label in self.ignored or t.id in self.excluded or t.id in self.checking:
                continue
            box = drawn[t.id]
            if t.id in names and names[t.id][1]:
                name, sure = names[t.id]
                out.append((*box, name, "known"))
            elif t.id == self.focus:
                out.append((*box, "???", "focus"))
            else:
                out.append((*box, "", "other"))
        return out

    def carried(self, tracks: list[Track], taken: float, now: float) -> dict[int, tuple]:
        """Bridge a short object gap for drawing only, bounded by capture and wall time."""
        names, out = self.names(now), {}
        for i, seen in self.seen.items():
            t = seen.track
            if i in self.visible or not t or t.label in BODY or seen.admitted is None or \
                    seen.shown is None or not 0 <= taken - seen.last <= OCCLUSION_S or \
                    not 0 <= now - seen.last <= OCCLUSION_S or t.label in self.ignored or \
                    i in self.excluded or i in self.checking or t.score < DETECT_LOW or \
                    (not self.sized(t) and seen.last - seen.admitted > OCCLUSION_S):
                continue
            # Even an unconfirmed replacement removes the old outline at this position.
            if any(other.label not in BODY and max(inside(t.box, other.box),
                    inside(other.box, t.box)) >= 0.5 for other in tracks):
                continue
            name, sure = names.get(i, ("", False))
            label, kind = (name, "known") if sure else (
                ("???", "focus") if i == self.focus else ("", "other"))
            out[i] = (*tuple(round(v) for v in seen.shown), label, kind)
        return out

    def geometry(self, tracks: list[Track]) -> dict[int, Box]:
        """Snapshot source drawing admission and geometry; names and selection stay current."""
        return {t.id: tuple(round(v) for v in self.seen[t.id].shown)
                if t.id in self.seen and self.seen[t.id].shown is not None else t.box
                for t in tracks if t.label in BODY or self.drawable(t)}
