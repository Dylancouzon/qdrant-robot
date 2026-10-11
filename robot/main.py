"""The robot: hears a line, looks, recalls, answers aloud, and remembers named objects
and conversation. One process; the LLM runs in a supervised llama-server child.
Every turn logs its stage times and saves its answer audio.

    python -m robot.main                       camera, USB microphone, USB speaker
"""
import argparse
import contextlib
import json
import os
import queue
import secrets
import subprocess
import re
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

from robot import audio, brain
from robot.asr import Ears, Scribe, woken
from robot.config import SHARED
from robot.settings import settings
from robot.detect import CONFIRM, Detector, Sighting, Tracker, iou, region
from robot.recognition import Recognition
from robot.focus import BODY, OCCLUSION_S, SMOOTH, SNAP, Focus, Track, inside
from robot.knowledge import VERBATIM, Knowledge
from robot.memory import (
    UNAVAILABLE,
    Memory,
    about_past,
    compares,
    earlier_view,
    article,
    is_question,
    kind_of,
    main_object,
    shown,
    showed,
    sighting_answer,
    sighting_query,
    thumb,
)
from robot.people import (
    DECLINED,
    THRESHOLD,
    People,
    consent,
    done,
    face,
    located_face,
    name_in,
    reply,
    request,
)
from robot.route import Router
from robot.text_embed import TextEmbedder
from robot.things import (
    SHOTS,
    Things,
    command,
    cut,
    plural,
    mentions,
    name_slot,
    question,
    unmention,
)
from robot.tts import RATE, Speaker, phrases
from robot.view import valid_id, Screen, View

HISTORY_TURNS = 4  # the conversation window, in exchanges
WATCH_S = 0.3      # how often idle time checks whether the prefilled frame is stale
SCENE_CHANGE = 8.0  # mean absolute difference (0-255) of 64x36 grey thumbnails
# Camera rate: unthrottled detection halved LLM decode (research/detector.md).
DETECT_FPS = 15
DETECT_RESTARTS = 3  # detector failures it recovers from by reloading; the next one stops it
SIGHTINGS = 64  # the newest out-of-view sightings a sighting answer groups
LINES = 4  # sighting lines for the brain at most: the newest of each kind
# A statement about the speaker (D70): recalled only in the conversation it was told in.
FIRST_PERSON = re.compile(r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine|myself)\b", re.I)
# Identity is the face in the current frame, never a track (design
# reviews/20261008-161702-78890-design.md): a visitor replacing another keeps the track id.
# Conversation identity uses the fresh speech-start frame.
# Background display verifies its own frame.
# Without an enrolled face match, a name told in this conversation answers (D60).
# A line this soon after the last answer finishes playing continues the conversation (D65);
# a visitor can walk to the keyboard and back inside it.
CONVERSATION_S = 60
CLEAR_S = 30  # after "forget me", turns are not stored until another face, or no face this long
VIEW_S = 0.33  # spacing of the recent views a named object's crops come from
PREVIEW_TTL = 0.75  # source expiry for recognition writes
# A UI item stays offered, and Ignore stays valid, this long after its track leaves the view,
# so a person has time to open the dropdown and choose it. The offer keeps its own crop.
OFFER_HOLD_S = 30.0
OFFER_REFRESH_S = 1.0  # a visible item gets a new crop this often; an Ignore in flight can finish
NOTHING_HELD = "I don't see an object held up. Hold it up and say it again."
SETTLE_S = 0.5  # how long a "my phone" turn waits for tracks confirmed after its speech start


def _central(boxes: dict[int, tuple], width: int) -> int | None:
    """The track whose box center is nearest the frame's vertical center line."""
    return min(boxes, key=lambda t: abs(sum(boxes[t][::2]) / 2 - width / 2), default=None)


def scene_change(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(thumb(a).astype(np.float32) - thumb(b)).mean())


def differs(a: "Look", b: "Look") -> bool:
    return scene_change(a.frame, b.frame) > SCENE_CHANGE


@dataclass
class Look:
    """A frame whose prompt prefix, after `exchanges` exchanges, is in the brain's KV cache."""
    frame: np.ndarray
    taken: float                  # capture time: the evidence time of what the brain saw
    image: dict
    exchanges: int
    changed: bool                 # the view differs from the previous turn's
    history: list[dict]           # the conversation as prefilled with this frame
    caption: str | None = None    # what the brain made of this frame alone (brain.caption)


@dataclass
class Visitor:
    """What a person track carries for its life only (D49)."""
    forgotten: bool = False   # "forget me": nothing more of this track is written


@dataclass
class Offer:
    """An item the UI can Ignore: the crop it had when last in view, and when that was."""
    title: str
    chosen: str | None   # the saved object's name, when a name was accepted for the track
    label: str
    epoch: int
    shot: np.ndarray     # a copy of the crop only, never a view of the whole camera frame
    seen: float          # capture time of the source it was cut from


@dataclass
class Turn:
    """One exchange, with wall-clock stage times (time.time())."""
    question: str = ""
    answer: str = ""
    facts: list[str] = field(default_factory=list)
    memories: list[int] = field(default_factory=list)  # evidence: ids of the frames recalled
    ui_evidence: list[dict] = field(default_factory=list)  # readable sources, never logged
    kind: str = ""                # sight, recall, social, or knowledge (robot/route.py)
    verbatim: bool = False        # answered from Edge in code (a fact, a shown object), no LLM
    told: list[str] = field(default_factory=list)  # earlier visitor statements recalled
    prompt: list = field(default_factory=list)  # the brain's messages without images or system
    frame_id: int = 0             # this turn's text memory point
    looked: float = 0.0           # capture time of the frame this turn looked at
    selected: float = 0.0         # capture time of the retained look a past question about
    #                               something shown is answered from (0: none)
    caption: str = ""             # that look's caption: ready, demand (made in this turn), or
    #                               failed (none, interrupted, or no main object); "" no look
    caption_s: float = 0.0        # seconds the on-demand caption took
    delivered: bool = False       # the caption supplied the code answer, or was in the request
    #                               the brain answered
    speech_start: float = 0.0     # the VAD heard speech start
    target: int | None = None     # the object track the focus gave at speech start (Focus.target)
    speech_end: float = 0.0       # end of the visitor's speech (from the ASR stream clock)
    line: float = 0.0             # the VAD ended the line
    transcribed: float = 0.0      # Parakeet's final transcript ready
    retrieved: float = 0.0
    first_token: float = 0.0
    first_phrase: float = 0.0     # first phrase of text complete, handed to TTS
    first_audio: float = 0.0      # first phrase synthesized and handed to the speaker
    done: float = 0.0
    wav: str = ""
    audio_s: float = 0.0          # length of the spoken answer
    detect_fps: float = 0.0       # detection and tracking rate while this turn ran
    identity: dict = field(default_factory=dict)  # face width, two-shot scores, name claimed
    visitor: str = ""             # resolved once before object actions
    named: str = ""               # the visitor's object this turn named: linked to its frame
    keep: bool = True             # False: not stored ("forget my phone")
    resumed: bool = False         # decode paused at the first phrase and resumed (D66)


class Robot:
    def __init__(self, camera, out: Path, memory: Path = SHARED / "memory",
                 play: Callable[[np.ndarray], None] | None = None, model: str = brain.MODEL,
                 wake_word: bool = True):
        """`wake_word` False: every line is answered (scripted sessions never say it)."""
        self.camera, self.out, self.wake_word = camera, out, wake_word
        self.camera_source = "Live camera"
        out.mkdir(parents=True, exist_ok=True)
        self.knowledge, self.embed = Knowledge(), TextEmbedder()
        self.people = People(memory)
        self.memory = Memory(memory)
        self.things = Things(memory, self.people)
        self.conversation_visitor = self.things.new_visitor()
        self.conversation_started = False
        self.named, self.ignored = self.things.labels(), self.things.ignored()
        self.scribe = Scribe()
        self.route = Router(self.embed)
        self.voice = Speaker()
        self.speaker = audio.Mouth(play)
        self.muted, self.volume = False, audio.saved_volume()  # the page's controls
        self.volume_lock = threading.Lock()  # mixer, saved level, and page value change together
        self.brain = brain.Brain(model)
        self.detect, self.tracker = Detector(), Tracker()
        self.vocab = set(self.detect.names.values())  # the labels the detector can give
        self.points: dict[int, int] = {}  # track id -> its sighting point, while it is tracked
        self.away: set[int] = set()  # tracked ids reported gone: their points may be evicted
        self.visitors: dict[int, Visitor] = {}  # person track id -> what is known of them
        # (frame, Tracker.view()) of the last detected frame, and of up to SHOTS frames VIEW_S
        # apart: a box and the frame it was found in stay together for a crop.
        self.view: tuple[np.ndarray | None, dict] = (None, {})
        self.view_at = self.view_taken = 0.0  # detection time, source capture time
        self.offers: dict[int, Offer] = {}  # track id -> its Ignore choice (see _offers)
        self.verified = None  # completed positive/negative face result on exact source pixels
        self.shown_taken = 0.0
        self.shown_frame, self.shown_record = 0, 0
        self.shown_known = False
        self.window = None
        self.session_id = secrets.token_hex(16)
        self.control_message = ""
        self.crop_due = {}
        self.item_checked = {}
        self.matches_pending = False
        self.crop_times: deque[float] = deque()  # at most three background crop queries per second
        self.focus: Focus | None = None  # the focus object and shown names (D63), per frame
        self.screen: tuple[np.ndarray | None, Screen] = (None, Screen())  # what the view draws
        self.views: deque[tuple[float, np.ndarray, dict]] = deque(maxlen=SHOTS)
        # (name, times asked, [face] of the request): consent asked, the face held only until
        # the answer
        self.asking: tuple[str, int, list] | None = None
        # (face, last seen) of a visitor who asked to be forgotten. It serves the deletion, not
        # identification: RAM only, never written, dropped when another face or no face for
        # CLEAR_S follows (or at a restart). Until then no turn showing that face is stored.
        self.hiding: tuple[np.ndarray, float] | None = None
        # The conversation (D60, D70): the face it began with (RAM only, never written; None:
        # no face), and the first point id stored in it (ids are microseconds, Memory._id).
        self.face: np.ndarray | None = None
        self.since = time.time_ns() // 1000  # nothing from before a start is the speaker's
        # (name, offered) the visitor told in this conversation; offered: the robot offered
        # to remember their face (D69), once per conversation.
        self.told: tuple[str, bool] | None = None
        self.last_line = 0.0  # when the answer to the last answered line ended
        # (track, focus epoch) that "Track this" asked a name for
        self.current_visitor = ""
        self.candidate = self.confirming = None
        self.confirm_count, self.confirm_last = 0, 0.0
        self.confirm_tracks = set()
        self.teaching: tuple[int, int] | None = None
        self.ui_turns: deque[Turn] = deque(maxlen=8)  # current session only, never written by UI
        self.ui_turn: Turn | None = None
        self.ui_thinking = False
        self.panel: dict | None = None  # the last retrieval, for the view's memory panel
        self.stream: Iterator[str] | None = None  # the brain's answer while a turn decodes
        self.detections = 0                     # frames detected so far
        self.detect_failed: Exception | None = None  # set when detection stopped for good
        self.history: list[dict] = []
        # What each exchange of `history` looked at, in RAM only: a past question about something
        # shown gets one of these frames (earlier_view). Cleared wherever the history is, and by
        # a deletion, because a frame can show what was deleted.
        self.looked: list[Look] = []
        self.exchanges = 0                      # counts every exchange; history is capped
        self.last_frame: np.ndarray | None = None  # the frame of the previous turn
        self.jobs: queue.Queue = queue.Queue()  # GPU work for llama-server, in order
        self.lines: queue.Queue = queue.Queue()  # finished lines for the final transcript
        self.asked = 0                          # turns queued so far (one per heard line)
        self.turns: queue.Queue[Turn] = queue.Queue()  # finished turns, for replay and logs
        self.ready: Look | None = None          # the frame whose prompt prefix is prefilled
        self.speaking = False                   # a visitor is mid-line: background work yields
        self.speech_start = 0.0
        self.start_target: int | None = None  # the focus object when the current line began
        self.start_frame: tuple[np.ndarray | None, float] = (None, 0.0)  # frame, capture time
        self.closing = threading.Event()
        self.detecting = threading.Lock()       # held while a frame is detected and tracked
        self.delivery = threading.Condition(self.detecting)
        self.threads = [threading.Thread(target=t, name=t.__name__, daemon=True)
                        for t in (self._watch, self._detect, self._transcribe, self._work)]
        self.recognition = Recognition(self._preview)
        for t in self.threads:
            t.start()
        self.ears = Ears(self._heard_start, self._heard_line)
        token = os.environ.get("ROBOT_VIEW_TOKEN")  # the booth video view (D59), off without one
        self.video = View(self._shown, int(os.environ.get("ROBOT_VIEW_PORT", "8090")), token,
                          os.environ.get("ROBOT_VIEW_HOST", "127.0.0.1"), action=self._control,
                          state=lambda: self._shown(False), wake=self._wake_view,
                          memory=self._memory_list, thumb=self._thumbnail) if token else None

    def hear(self, chunk: np.ndarray) -> None:
        """Every audio input enters here. The robot does not hear itself (silence while its
        speaker plays and just after) and does not hear while muted."""
        if self.muted or self.speaker.playing(audio.SELF_VOICE_TAIL_S):
            chunk = np.zeros_like(chunk)
        self.ears.feed(chunk)

    def ask(self, text: str) -> None:
        """A typed line, entering where a transcript would (oracle replays, debugging)."""
        self._heard_start()
        t = time.time()
        self.speaking = False
        self.asked += 1
        self.jobs.put(("turn", Turn(question=text, line=t, transcribed=t, speech_end=t,
                                    speech_start=self.speech_start, target=self.start_target),
                          self.start_frame))

    def reset(self, memory: Path) -> None:
        """Start over with an empty memory and conversation (scripted sessions). Detection
        pauses so no sighting of the old session reaches the new memory, and the tracker starts
        over so objects still in view are sighted again."""
        self.recognition.pause()  # stop background publications before draining their consumer
        self.jobs.join()  # turns may still make priority model requests
        self.recognition.close()
        with self.detecting:
            self.memory.shard.close()
            self.people.shard.close()
            self.things.shard.close()
            self.people = People(memory)
            self.memory = Memory(memory)
            self.things = Things(memory, self.people)
            self.conversation_visitor = self.things.new_visitor()
            self.conversation_started = False
            self.named, self.ignored = self.things.labels(), self.things.ignored()
            self.history, self.looked, self.exchanges, self.ready = [], [], 0, None
            self.last_frame, self.points, self.tracker = None, {}, Tracker()
            self.away, self.visitors, self.asking, self.hiding = set(), {}, None, None
            self.told, self.last_line, self.face = None, 0.0, None
            self.teaching, self.start_target = None, None
            self.current_visitor = ""
            self._clear_confirmation()
            self.since, self.panel = time.time_ns() // 1000, None
            self.view, self.offers = (None, {}), {}
            self.focus, self.screen = None, (None, Screen())
            self.views.clear()
            self.verified, self.shown_taken, self.crop_due, self.item_checked = None, 0.0, {}, {}
            self.shown_frame, self.shown_record = 0, 0
            self.shown_known = False
            self.window = None
            self.session_id = secrets.token_hex(16)
            self.crop_times.clear()
            self.matches_pending, self.control_message = False, ""
            self.ui_turns.clear()
            self.ui_turn, self.ui_thinking = None, False
            self.delivery.notify_all()
        self.recognition = Recognition(
            self._preview, self.recognition.faces, self.recognition.crops)

    def _heard_start(self) -> None:
        self.speaking, self.speech_start = True, time.time()
        self.start_frame = self.camera.latest()  # what the visitor sees as they speak
        with self.detecting:
            self.start_target = self.focus and self.focus.target(
                [Track(*t) for t in self.tracker.scored()])
        if self._stale(self.start_frame[0]):
            self.jobs.put(("look", self.start_frame))

    def _heard_line(self, speech: np.ndarray, speech_end: float) -> None:
        self.speaking = False
        self.lines.put((speech, time.time(), speech_end, self.speech_start, self.start_frame,
                        self.start_target))

    def _transcribe(self) -> None:
        # Its own thread: the final transcript overlaps a prefill instead of queuing behind it.
        while (line := self.lines.get()) is not None:  # None: close() stops the thread
            speech, t_line, speech_end, speech_start, shot, target = line
            if text := self.scribe(speech):  # empty: noise the VAD took for speech
                self.asked += 1
                turn = Turn(question=text, line=t_line, transcribed=time.time(),
                            speech_end=speech_end, speech_start=speech_start, target=target)
                self.ui_turn, self.ui_thinking = turn, True
                self.jobs.put(("turn", turn, shot))
            self.lines.task_done()

    def _watch(self) -> None:
        # The same worker does bounded idle recognition and prefill; speech takes priority.
        while not self.closing.wait(WATCH_S):
            if self.speaking or self.ui_thinking or not self.jobs.empty():
                continue
            if look := self._undescribed():
                self.jobs.put(("describe", look))
                continue
            shot = self.camera.latest()
            if self._stale(shot[0]):
                self.jobs.put(("look", shot))

    def _detect(self) -> None:
        # Detection and tracking at camera rate on the newest frame; sightings are written by
        # the worker after the turns queued before them, never during a turn.
        due, failures = time.time(), 0
        while not self.closing.wait(max(0.0, due - time.time())):
            due = max(due + 1 / DETECT_FPS, time.time())
            frame, taken = self.camera.latest()
            if frame is None:
                continue
            try:
                self.detect = self.detect or Detector()
                found = self._track(frame, self.detect(frame), taken)
            except Exception as e:
                failures += 1
                print(f"detection failed ({failures} of {DETECT_RESTARTS + 1}):", flush=True)
                traceback.print_exc()
                with contextlib.suppress(Exception):
                    self.detect.close()
                self.detect = None  # reloaded on the next frame
                if failures > DETECT_RESTARTS:
                    self.detect_failed = e
                    return
                continue
            self.detections += 1
            if found:
                self.jobs.put(("sight", found))

    def _track(self, frame: np.ndarray, dets: list, taken: float | None = None) -> list[Sighting]:
        """Track one detected frame; keep its boxes with the frame they are in, for crops."""
        with self.detecting:
            found = self.tracker.update(dets, frame.shape[1], time.time())
            self.view, self.view_at = (frame, self.tracker.view()), time.time()
            self.view_taken = self.view_at if taken is None else taken
            if self.focus:
                for i in self.tracker.merged:
                    self.focus.named.pop(i, None)
                    self.focus.excluded.pop(i, None)
                    if i in self.focus.seen:
                        self.focus.seen[i].exclude_misses = 0
                        self.focus.seen[i].shown = None
                        self.focus.seen[i].admitted = None
                        self.focus.seen[i].epoch += 1
                        self.focus.seen[i].continuous = self.view_taken
            if not self.views or self.view_taken - self.views[-1][0] >= VIEW_S:
                self.views.append((self.view_taken, *self.view))
            self._refocus(frame)
            self._window_status()
            tracks = [Track(*t) for t in self.tracker.scored()]
            self.recognition.submit((frame, self.view_taken,
                tracks,
                {i: self.focus.epoch(i) for i in self.focus.visible}, self.session_id,
                self.focus.geometry(tracks)))
            self.delivery.notify_all()
        return found

    def _refocus(self, frame: np.ndarray) -> None:
        """Feed the focus the tracks in view on the frame just tracked, and keep the view's
        boxes for that frame (held under self.detecting)."""
        tracks = [Track(*t) for t in self.tracker.scored()]
        people = [t.box for t in tracks if t.label == "person"]
        self.focus = self.focus or Focus(frame.shape[1], frame.shape[0])
        self.focus.ignored = self.ignored
        self.focus.update(self.view_taken, tracks, people)
        self.item_checked = {i: epoch for i, epoch in self.item_checked.items()
                             if i in self.focus.seen}
        self.focus.checking = {t.id for t in tracks if self.things.items and t.label not in BODY
                               and self.item_checked.get(t.id) != self.focus.epoch(t.id)}
        if self.verified and (self.verified[2] != self.recognition.epoch or
                any(not self.focus.accepts(i, self.verified[0]) for i in self.verified[4])):
            self.verified = None
        self.screen = frame, Screen(self.focus.boxes(tracks, people), memory=self.panel)

    def _wake_view(self) -> None:
        with self.delivery:
            self.delivery.notify_all()

    def _completed_valid(self, record) -> bool:
        return bool(record and record[2] == self.recognition.epoch and
                    record[5] == self.session_id and 0 <= time.time() - record[0] <= .2 and
                    all(self.focus.accepts(i, record[0]) and
                        self.focus.epoch(i) == record[3][0][i][1] for i in record[4]))

    def _display_source(self, tracks):
        frame, taken = self.screen[0], self.view_taken
        shown_tracks, geometry, faces = tracks, None, []
        record = self.verified if self._completed_valid(self.verified) and \
            self.verified[0] >= self.shown_taken else None
        if record:
            taken, frame, _, (source, face, _), _, _ = record
            shown_tracks = [t for t in tracks if t.id in source and
                            self.focus.accepts(t.id, taken) and
                            self.focus.epoch(t.id) == source[t.id][1]]
            geometry = {i: box for i, (box, _) in source.items()}
            faces = [face] if face else []
        else:
            with self.recognition.condition:
                pending = next((p for p in (self.recognition.active, self.recognition.latest)
                    if p and p[4] == self.session_id and p[6] == self.recognition.epoch and
                    0 <= time.time() - p[1] <= .2), None)
                if pending:
                    frame, taken, shown_tracks, epochs, _, geometry, _ = pending
                    shown_tracks = [t for t in shown_tracks if self.focus.accepts(t.id, taken)
                                    and self.focus.epoch(t.id) == epochs[t.id]]
        return frame, taken, shown_tracks, geometry, faces, record

    def _publication_valid(self, frame, taken, record, session, gallery, epochs, cancel):
        with self.delivery:
            if cancel() or session != self.session_id or gallery != self.recognition.epoch or \
                    not 0 <= time.time() - taken <= .2 or taken < self.shown_taken:
                return False
            if record and (self.verified is not record or not self._completed_valid(record)):
                return False
            if any(not self.focus or not self.focus.accepts(i, taken) or
                   self.focus.epoch(i) != epoch for i, epoch in epochs.items()):
                return False
            if not record and self._completed_valid(self.verified) and self.verified[0] >= taken:
                return False
            if taken == self.shown_taken and id(frame) != self.shown_frame:
                return False
            if taken == self.shown_taken and self.shown_known and id(record) != self.shown_record:
                return False
            self.shown_taken, self.shown_frame = taken, id(frame)
            self.shown_record = id(record) if record else 0
            self.shown_known = bool(record and record[3][1] and record[3][1][5] == "known")
            return True

    def _offers(self, tracks: list[Track], label_map: dict[str, str]) -> list[dict]:
        """Refresh the Ignore choices (held under self.detecting). A visible, eligible named or
        focused track keeps a crop at most OFFER_REFRESH_S old; a stalled source stops
        refreshing. An offer stays for OFFER_HOLD_S after its last eligible moment, in view or not;
        a person is never offered."""
        now, (frame, boxes), taken = time.time(), self.view, self.view_taken
        labels = self.focus.names()
        for t in tracks:
            named = labels.get(t.id, (None, False))[1]
            old = self.offers.get(t.id)
            if frame is not None and t.id in boxes and t.label not in BODY and \
                    self.focus.eligible(t) and (named or t.id == self.focus.focus):
                if old is None or taken - old.seen >= OFFER_REFRESH_S or \
                        old.epoch != self.focus.epoch(t.id):
                    self.offers[t.id] = Offer(
                        label_map.get(labels[t.id][0], "") if named else "Unknown " + t.label,
                        labels[t.id][0] if named else None, t.label.capitalize(),
                        self.focus.epoch(t.id), cut(frame, boxes[t.id][1]).copy(), taken)
            elif t.label in BODY:
                self.offers.pop(t.id, None)
        self.offers = {i: o for i, o in self.offers.items() if now - o.seen <= OFFER_HOLD_S}
        return [{"track": i, "epoch": o.epoch, "title": o.title} for i, o in self.offers.items()]

    def _shown(self, display=True, deadline=None, cancel=lambda: False
               ) -> tuple[np.ndarray | None, Screen]:
        """Deliver completed sources; a timeout keeps fresh in-flight pixels anonymous."""
        with self.delivery:
            if display and deadline is not None:
                self.delivery.wait_for(lambda: cancel() or
                    (self._completed_valid(self.verified) and
                     (self.verified[0] > self.shown_taken or
                      (self.verified[0] == self.shown_taken and
                       id(self.verified[1]) == self.shown_frame and
                       not self.shown_known and
                       id(self.verified) != self.shown_record))),
                    timeout=max(0, deadline - time.monotonic()))
            screen = self.screen[1]
            tracks = [Track(*t) for t in self.tracker.scored()] if self.focus else []
            frame, taken, shown_tracks, geometry, faces, record = self._display_source(tracks)
            if self.focus:
                screen = replace(screen, boxes=self.focus.boxes(
                    shown_tracks, [], time.time(), geometry=geometry) + faces)
            objects = self.things.label_map()
            screen = replace(
                screen,
                boxes=[
                    (*b[:4], objects[b[4]], b[5])
                    if b[5] == "known" and b[4] in objects
                    else b
                    for b in screen.boxes
                ],
            )
            session, gallery = self.session_id, self.recognition.epoch
            epochs = {t.id: self.focus.epoch(t.id) for t in shown_tracks}
            screen = replace(screen, valid=(lambda: self._publication_valid(
                frame, taken, record, session, gallery, epochs, cancel)) if display else None,
                source=(taken, id(frame), id(record)))
            targets = self._offers(tracks, objects) if self.focus else []
            screen = replace(screen, control={"session": self.session_id,
                "targets": targets,
                "gallery": self.recognition.epoch,
                "message": self.control_message, "camera_source": self.camera_source,
                "muted": self.muted, "volume": self.volume},
                ignored_items=self.things.preferences(), settings=settings.snapshot(),
                window=self._window_status(objects))
            status = ("Hearing you" if self.speaking or self.lines.unfinished_tasks else
                      "Speaking" if self.speaker.playing() else
                      "Thinking" if self.ui_thinking else
                      "Say 'Hey Edgy'" if self.wake_word and
                      time.time() - self.last_line > CONVERSATION_S else "Listening")
            turns = list(self.ui_turns)
            turn = self.ui_turn
            if turn is not None and (not turns or turns[-1] is not turn):
                turns.append(turn)
            evidence = {}
            if turn is not None:
                if not turn.keep or self.hiding:
                    turns = [turn]  # Deleted visitor/object content leaves the live UI, too.
                evidence = {"knowledge": turn.facts if not turn.verbatim else
                            [turn.answer] if turn.answer in turn.facts else [],
                            "statements": turn.told if not turn.verbatim else [],
                            "memory_ids": turn.memories, "memories": turn.ui_evidence,
                            "answer_path": ("Code" if turn.verbatim else "Generated")
                            if turn.first_token else ""}
            transcript = [{"id": str(t.line), "question": t.question, "answer": t.answer}
                          for t in turns[-8:]]
            return frame, replace(screen, status=status, transcript=transcript,
                                  evidence=evidence, memory=self.panel)

    def _sight(self, found: list[Sighting]) -> None:
        """Unknown tracks live only in RAM. Only fresh recognition writes selected sightings."""
        for s in found:
            if s.ended:
                self._end(s.track)
            elif s.gone:
                self.away.add(s.track)
            else:
                self.away.discard(s.track)

    def _preview(self, frame, taken, tracks, epochs, session, geometry, gallery):
        """Model-owner background work; fresh results alone authorize selected writes."""
        if time.time() - taken > PREVIEW_TTL or gallery != self.recognition.epoch:
            return
        found_face = located_face(self.recognition.faces, frame)
        scores = self.people.scores(found_face[0]) if found_face else []
        person = scores[0][0] if scores and scores[0][2] >= THRESHOLD and (
            len(scores) == 1 or scores[1][2] < THRESHOLD) else None
        with self.detecting:
            focus = self.focus
            preferences = {i: focus.name(i) for i in epochs}
            if session == self.session_id and gallery == self.recognition.epoch:
                valid = {i for i in epochs if focus.accepts(i, taken) and
                         focus.epoch(i) == epochs[i]}
                self._verified_frame(frame, taken, tracks, valid, found_face, person, geometry,
                                     gallery)
        recognized, excluded = self._query_objects(frame, tracks, preferences, (taken, epochs))
        if time.time() - taken > PREVIEW_TTL:
            return
        with self.detecting:
            if session != self.session_id or gallery != self.recognition.epoch:
                return
            valid = {i for i in epochs if self.focus.accepts(i, taken) and
                     self.focus.epoch(i) == epochs[i]}
            for i, preference in excluded.items():
                if i in valid:
                    self.item_checked[i] = self.focus.epoch(i)
                    self.focus.checking.discard(i)
                    self.focus.exclude(i, preference)
                    if i in self.focus.excluded:
                        self.focus.named.pop(i, None)
            recognized = {i: hit for i, hit in recognized.items()
                          if i in valid and i not in self.focus.excluded}
            current = [Track(*t) for t in self.tracker.scored()]
            self.focus.update(self.view_taken, current,
                              [t.box for t in current if t.label == "person"],
                              recognized=recognized, recognized_at=taken)
            # Persist in the conversation worker, with a second source/epoch check.
            if recognized and not self.matches_pending:
                self.matches_pending = True
                self.jobs.put(("matches", frame, taken, tracks, recognized, person,
                               epochs, session, gallery))

    def _verified_frame(self, frame, taken, tracks, valid, face, person, geometry, gallery):
        """Publish each completed face result before crop work, including anonymous negatives."""
        people = [t for t in tracks if t.label == "person"]
        members = tuple(t.id for t in people)
        if any(i not in valid for i in members):
            if self.verified and taken >= self.verified[0]:
                self.verified = None
                self.delivery.notify_all()
            return  # Departed source people cannot publish even anonymous face outlines.
        candidates = [t for t in people if face and inside(face[2], t.box) >= 0.8]
        matched = person if len(candidates) == 1 and self.focus.eligible(candidates[0]) else None
        source = {t.id: (geometry[t.id], self.focus.epoch(t.id)) for t in tracks
                  if t.id in valid and t.id in geometry}
        outline = self._face_outline(face, matched, members if len(candidates) == 1 else (), taken)
        if self.verified is None or taken >= self.verified[0]:
            raw_face = face[2] if face and len(candidates) == len(members) == 1 else None
            self.verified = taken, frame, gallery, (source, outline, raw_face), \
                members, self.session_id
            self.delivery.notify_all()

    def _face_outline(self, face, matched, members, taken):
        """Filter drawing on adjacent verified sources; identity always comes from this face."""
        if not face:
            return None
        box, previous = face[2], self.verified
        if previous and previous[2] == self.recognition.epoch and \
                previous[5] == self.session_id and len(members) == 1 and \
                members == previous[4] and \
                all(self.focus.accepts(i, previous[0]) and
                    self.focus.epoch(i) == previous[3][0][i][1] for i in members) and \
                previous[3][1] and previous[3][2] and previous[3][1][4] == (matched or "") and \
                0 <= taken - previous[0] <= OCCLUSION_S:
            old = previous[3][2]
            delta = np.subtract(np.add(box[:2], box[2:]), np.add(old[:2], old[2:])) / 2
            if np.linalg.norm(delta) <= SNAP * self.focus.width:
                box = previous[3][1][:4] if taken == previous[0] else tuple(
                    a + SMOOTH * (b - a) for a, b in zip(previous[3][1][:4], box, strict=True))
        return (*box, matched or "", "known" if matched else "other")

    def _window_status(self, label_map=None):
        """End a teaching window for good when time runs out or its track is gone. Resets,
        new conversations, naming, and forgetting clear it where they happen."""
        window = self.window
        if window and (time.time() >= window["end"] or settings.window_s == 0 or
                not self.focus or window["track"] not in self.focus.visible or
                self.focus.epoch(window["track"]) != window["epoch"]):
            self.window = window = None
        name = ((self.things.label(window["name"]) if label_map is None else
                 label_map.get(window["name"], "")) if window else "")
        return {"active": bool(window), "name": name,
                "views_admitted": window["admitted"] if window else 0,
                "seconds_left": max(0., window["end"] - time.time()) if window else 0.}

    def _admit_window(self, window, track, vector, source, crop):
        """Add the taught track's crop if the window still holds that track (D154)."""
        taken, epochs = source
        with self.detecting:
            self._window_status()
            if self.window is not window or track.label in BODY or \
                    epochs.get(track.id) != window["epoch"] or \
                    not self.focus.accepts(track.id, taken) or \
                    time.time() - taken > PREVIEW_TTL:
                return
        # Outside the detection lock: forget runs on this same owner thread, so nothing races.
        own = self.things.score(vector, window["name"])
        # Added views preserve valid results and offers, so keep the gallery epoch.
        if own and own[1] >= settings.window_floor and \
                self.things.add_view(window["name"], vector, crop, source="window"):
            window["admitted"] += 1
            with (self.out / "turns.jsonl").open("a") as stream:
                stream.write(json.dumps({"event": "teaching_view", "name": own[0],
                    "track": track.id, "time": time.time(),
                    "session": self.session_id}) + "\n")

    def _start_window(self, track, epoch, name):
        """Learn more views of `name` from its taught track while that track lasts (D154)."""
        now = time.time()
        if settings.window_s > 0 and self.focus.epoch(track) == epoch and \
                track in self.focus.visible:
            self.window = dict(track=track, epoch=epoch, name=name,
                               end=now + settings.window_s, last=now, admitted=0)

    def _query_objects(self, frame, tracks, preferences, source=None):
        """Oldest-due eligible crop, reusing one vector for identity and item preference."""
        candidates = [t for t in tracks if t.label not in BODY and
                      self.focus.sized(t) and self.focus.confident(t, pending=True) and
                      t.label not in self.ignored]
        self._window_status()
        window = self.window
        source = source or (self.view_taken, {t.id: self.focus.epoch(t.id) for t in tracks})
        with self.detecting:
            if self.candidate and (self.focus.focus != self.candidate["track"] or
                    self.focus.epoch(self.candidate["track"]) != self.candidate["epoch"]):
                self.candidate = None
        active = {t.id for t in candidates}
        self.crop_due = {i: due for i, due in self.crop_due.items() if i in active}
        while self.crop_times and time.monotonic() - self.crop_times[0] >= 1:
            self.crop_times.popleft()
        recognized, excluded = {}, {}
        if (self.named or self.things.items) and len(self.crop_times) < 3 and candidates:
            eligible = self.things.visual_links(self.ignored)
            due = window and time.time() - window["last"] >= settings.window_gap_s
            taught = next((t for t in candidates if window and t.id == window["track"]), None)
            t = taught if due and taught else min(
                candidates, key=lambda t: self.crop_due.get(t.id, 0))
            self.crop_times.append(time.monotonic())
            self.crop_due[t.id] = time.monotonic()
            vector = self.recognition.crops([cut(frame, t.box)])[0]
            excluded[t.id] = self.things.excluded(vector)
            if due and t is taught:
                window["last"] = time.time()  # each attempt spends the gap, so others get slots
                rivals = [o.box for o in tracks if o.id != t.id and o.label == t.label]
                crowded = bool(rivals) and iou(np.array([t.box]), np.array(rivals)).max() > .3
                if not excluded[t.id] and not crowded:  # an overlapping lookalike: impure crop
                    self._admit_window(window, t, vector, source, cut(frame, t.box))
            hit = self.things.score(vector, preferences[t.id])
            best = hit
            if preferences[t.id] and (not hit or hit[1] < settings.match):
                other = self.things.score(vector)
                best = other
                if other and other[1] >= settings.match and other[0] in eligible:
                    hit = other
            self._near_match(t, best if best and best[0] in eligible and
                             not excluded[t.id] else None, vector, cut(frame, t.box), source)
            recognized[t.id] = hit if hit and hit[0] in eligible else (None, 0.0)
        return recognized, excluded

    def _clear_confirmation(self):
        self.candidate = self.confirming = None
        self.confirm_count, self.confirm_last = 0, 0.0
        self.confirm_tracks = set()

    def _near_match(self, track, hit, vector, crop, source):
        """Keep one copied near view until the focused track has persisted."""
        now = time.time()
        rows = self.things.shard.retrieve([hit[0]], True, False) if hit and hit[0] else []
        with self.detecting:
            epoch = source[1].get(track.id)
            key = (track.id, epoch)
            valid = (settings.ask_max > 0 and rows and
                     rows[0].payload.get("owner") == self.current_visitor and
                     settings.match - settings.guess_band <= hit[1] < settings.match and
                     self.focus.focus == track.id and self.focus.epoch(track.id) == epoch and
                     self.focus.accepts(track.id, source[0]) and
                     now - source[0] <= PREVIEW_TTL)
            candidate = self.candidate
            if not valid or key in self.confirm_tracks:
                if candidate and candidate["track"] == track.id:
                    self.candidate = None
                return
            if candidate and (candidate["object"], candidate["track"], candidate["epoch"]) != (
                    hit[0], track.id, epoch):
                self.candidate = None
                return
            if candidate is None:
                candidate = self.candidate = dict(object=hit[0], track=track.id, epoch=epoch,
                    vector=vector.copy(), crop=crop.copy(), first=now, count=0,
                    visitor=self.current_visitor, queued=False)
            candidate["count"] += 1
            if candidate["count"] >= 2 and now - candidate["first"] >= settings.ask_delay_s and \
                    not candidate["queued"]:
                candidate["queued"] = True
                self.jobs.put(("confirm", candidate))

    def _confirm(self, candidate):
        """Ask once through the normal voice path, only in a conversation blank."""
        now = time.time()
        with self.detecting:
            if self.candidate is not candidate:
                return
            self.candidate = None
            if not (0 <= now - self.last_line <= CONVERSATION_S and
                    now - self.last_line >= settings.ask_blank_s and
                    not self.speaking and not self.ui_thinking and self.jobs.empty() and
                    self.lines.unfinished_tasks == 0 and not self.speaker.playing() and
                    not self.teaching and not self.asking and not self.confirming and
                    self.confirm_count < settings.ask_max and
                    now - self.confirm_last >= 60 and
                    candidate["visitor"] == self.current_visitor and
                    self.focus.focus == candidate["track"] and
                    self.focus.epoch(candidate["track"]) == candidate["epoch"] and
                    candidate["track"] in self.focus.visible and
                    (candidate["track"], candidate["epoch"]) not in self.confirm_tracks):
                return
        rows = self.recognition.call(lambda f, c: self.things.shard.retrieve(
            [candidate["object"]], True, False))
        if not rows or rows[0].payload.get("owner") != self.current_visitor:
            return
        text = f"Is this your {rows[0].payload['name']}?"
        self.ui_thinking = True
        pcm = self.voice.say(text)
        self.ui_thinking = False
        if self.speaking or self.lines.unfinished_tasks:  # the visitor spoke during synthesis
            return
        turn = Turn(question="", line=now, answer=text)
        self.ui_turn = turn
        self.ui_turns.append(turn)
        self.speaker.play(pcm)
        self.last_line = time.time() + len(pcm) / RATE
        self.confirm_count += 1
        self.confirm_last = now
        self.confirm_tracks.add((candidate["track"], candidate["epoch"]))
        self.confirming = {**candidate, "expiry": time.time() + CONVERSATION_S}

    def _confirmation_answer(self, turn):
        pending, self.confirming = self.confirming, None
        if not pending:
            return None
        reply = turn.question.lower().replace("’", "'")
        yes = bool(re.match(r"\W*(yes|yeah|yep|yup|sure|correct|it is|that's (it|mine))\b", reply))
        no = bool(re.match(r"\W*(no|nope|not mine|it isn't|it's not)\b", reply))
        if not yes and not no:
            return None
        with self.detecting:
            valid = (time.time() <= pending["expiry"] and
                     turn.visitor == pending["visitor"] == self.current_visitor and
                     self.focus and pending["track"] in self.focus.visible and
                     self.focus.focus == pending["track"] and
                     self.focus.epoch(pending["track"]) == pending["epoch"])
        if not valid:
            return None
        def admit(f, c):
            rows = self.things.shard.retrieve([pending["object"]], True, False)
            if not rows or rows[0].payload.get("owner") != turn.visitor:
                return False
            if yes:
                self.things.add_view(pending["object"], pending["vector"],
                                     pending["crop"], source="confirmed")
            return True
        if not self.recognition.call(admit):
            return None
        return "Thanks, I will remember it from this side too." if yes else "Okay."

    def _remember_matches(self, frame: np.ndarray, taken: float, tracks: list[Track],
                          recognized: dict, person: str | None) -> None:
        """Only this snapshot's sure matches may create or advance visual sightings."""
        if self.hiding or time.time() - taken > PREVIEW_TTL:
            return
        for t in tracks:
            name, score = recognized.get(t.id, (None, 0.0))
            claims = {i for i, n in self.focus.named.items()
                      if i in self.focus.visible and
                      ((n.name == name and n.confidence >= settings.match) or
                       (n.run[0] == name and n.score >= settings.match))}
            if name and score >= settings.match and t.label not in self.ignored and \
                    claims == {t.id}:
                pid = self.points.get(t.id)
                row = self.memory.points([pid]) if pid else []
                if not row or row[0].get("named") != name:
                    pid = None
                if pid:
                    self.memory.set(pid, label=t.label, region=region(t.box, frame.shape[1]),
                                    last_seen=taken)
                else:
                    pid = self.points[t.id] = self.memory.sighting(
                        t.label, region(t.box, frame.shape[1]), taken, name)
                if person:
                    self.recognition.call(lambda f, c, pid=pid: self.people.link(person, [pid]))
        if recognized:
            self._retain(time.time())

    def _end(self, track: int) -> None:
        """A track no new track can continue: forget its id."""
        self.points.pop(track, None)  # its last_seen was written when it went out of view
        self.away.discard(track)
        self.visitors.pop(track, None)

    def _whois(self, frame: np.ndarray, turn: Turn | None = None
               ) -> tuple[np.ndarray, str | None] | None:
        """The visitor's face in the whole `frame` (people.face) and the enrolled person it
        matches by the two-shot rule, or None without a usable face. An identity turn logs
        the face width, the step time, and the two best people's scores, never the face."""
        started = time.time()
        def identify(faces, crops):
            found = face(faces, frame)
            scores = self.people.scores(found[0])[:2] if found else []
            return found, scores
        found, scores = self.recognition.call(identify)
        name = scores[0][0] if scores and scores[0][2] >= THRESHOLD else None
        if turn is not None:
            turn.identity = {"face_px": found[1] if found else 0, "claimed": None,
                             "face_ms": round(1000 * (time.time() - started), 1),
                             "scores": [[n, round(b, 3), round(s, 3)] for n, b, s in scores]}
        return (found[0], name) if found else None

    def _retain(self, now: float) -> None:
        """Bound memory to the retention window and caps (Memory.retain) after each write,
        never evicting the point of a track that is not gone."""
        evicted = set(self.memory.retain(now, {
            p for t, p in self.points.items() if t not in self.away}))
        self.points = {t: p for t, p in self.points.items() if p not in evicted}
        for turn in [*self.ui_turns, self.ui_turn]:
            if turn is not None:
                turn.ui_evidence = [m for m in turn.ui_evidence if m.get("id") not in evicted]

    def _stale(self, frame: np.ndarray | None) -> bool:
        """The prefilled look no longer matches `frame` or the conversation."""
        return frame is not None and (self.ready is None or self.ready.exchanges != self.exchanges
                                      or scene_change(self.ready.frame, frame) > SCENE_CHANGE)

    def _work(self) -> None:
        # One worker: llama-server jobs run in order, and a turn reuses the last look.
        while (job := self.jobs.get()) is not None:  # None: close() stops the thread
            if job[0] == "look":
                self._look(job[1])
            elif job[0] == "turn":
                self._turn(*job[1:])
            elif job[0] == "confirm":
                self._confirm(job[1])
            elif job[0] == "sight":
                self._sight(*job[1:])
            elif job[0] == "matches":
                self.matches_pending = False
                _, frame, taken, tracks, hits, person, epochs, session, gallery = job
                with self.detecting:
                    hits = {i: hit for i, hit in hits.items() if session == self.session_id
                            and gallery == self.recognition.epoch and self.focus.accepts(i, taken)
                            and self.focus.epoch(i) == epochs[i] and i not in self.focus.excluded}
                self._remember_matches(frame, taken, tracks, hits, person)
            elif job[0] == "control":
                self.control_message = self._item_control(*job[1:])
            elif job[0] == "memory":
                self.control_message = self._memory_job(*job[1:])
            elif job[0] == "describe":
                self._describe_idle(job[1])
            else:
                self._caption_job(job)
            self.jobs.task_done()

    def _caption_job(self, job):
        if (rows := self.memory.points([job[1]])) and \
                rows[0].get("label") not in self.ignored and \
                rows[0].get("named") in self.things.visual_links(self.ignored) and \
                (caption := self.brain.caption(job[2], lambda: self.speaking)) is not None:
            self.memory.set(job[1], caption=caption)

    def _look(self, shot: tuple[np.ndarray, float]) -> None:
        changed = self.last_frame is not None and scene_change(
            self.last_frame, shot[0]) > SCENE_CHANGE
        # After the view changes, the brain's earlier answers describe a scene that is gone: keep
        # only what the visitor said, which a 2B brain otherwise trusts over the image (D27).
        history = [m for m in self.history if m["role"] == "user"] if changed else self.history
        look = Look(shot[0], shot[1], brain.jpeg(shot[0]), self.exchanges, changed, history)
        self.brain.prefill(brain.messages(history, look.image))
        self.ready = look

    def _undescribed(self) -> Look | None:
        """The oldest retained look without a caption that ends its view run: one caption per
        view, never one per duplicate frame."""
        looks = self.looked
        return next((x for i, x in enumerate(looks) if x.caption is None and (
            i + 1 == len(looks) or differs(x, looks[i + 1]))), None)

    def _describe_idle(self, look: Look) -> None:
        """The idle caption job: dropped when a deletion or a new conversation took the look
        meanwhile, or when foreground work arrived. The caption evicts the prefilled prefix, so
        the next _look prefills it again (`ready` is no longer valid)."""
        if self.speaking or self.ui_thinking or not self.jobs.empty():
            return
        if any(x is look for x in self.looked) and look.caption is None:
            self._describe(look)
            self.ready = None

    def _describe(self, look: Look) -> None:
        """Caption a retained look from its own frame, the one path for the idle worker and for a
        turn that needs it now; the caption stays None if speech interrupts it."""
        look.caption = self.brain.caption(look.image, lambda: self.speaking) or None

    def _look_back(self, turn: Turn, selected: Look, memories: list[str]) -> str | None:
        """What the selected look (earlier_view) showed, from its own caption, made now when the
        idle worker has not yet: the answer to a plain question, or None for a comparison with
        the present, whose Memories line gets it instead. Never another look's caption."""
        turn.selected, turn.caption = selected.taken, "ready"
        if selected.caption is None:
            started = time.time()
            self._describe(selected)
            turn.caption, turn.caption_s = "demand", time.time() - started
        thing = main_object(unmention(selected.caption or "", self.ignored))
        turn.delivered = thing is not None  # a comparison's line is sent only if the brain answers
        if thing is None:
            turn.caption = "failed"
        ago = brain.age(turn.speech_start - selected.taken)
        if compares(turn.question):
            if thing:
                memories.append(f"{ago}: you showed me {thing}")
            return None
        return showed(thing, ago) if thing else UNAVAILABLE

    def _code_answer(self, turn: Turn, now: np.ndarray, track: int | None, look: Look,
                     recalled: list[dict], memories: list[str]) -> str | None:
        """The answer given in code, or None for the brain: identity, then the visitor's things,
        then what the selected earlier look showed (which alone decides the path: its answer, or
        the brain with its Memories line), then stored shown objects and sightings."""
        if not turn.visitor:
            self._resolve_visitor(turn, now)
        if answer := self._confirmation_answer(turn):
            return answer
        teaching, self.teaching = self.teaching, None  # asked once; any other line drops it
        if answer := self._identity(turn, now, track) or self._things(turn, teaching):
            return answer
        if selected := earlier_view(turn.question, self.looked, look, differs):
            return self._look_back(turn, selected, memories)
        return shown(turn.question, recalled, lambda m: brain.age(turn.speech_start - m["ts"])
                     ) or self._sighted(turn)

    def _turn(self, turn: Turn, shot: tuple[np.ndarray | None, float]) -> None:
        """Answer about the frame shown when this line's speech started, or about an earlier
        look of the same scene; the frame used is the one stored as evidence. A line is
        answered only after the wake phrase, or as a follow-up within CONVERSATION_S of the
        last answer (D65); the wake phrase is not part of the question."""
        heard = woken(turn.question)
        if self.wake_word and heard is None and \
                turn.speech_start - self.last_line > CONVERSATION_S:
            turn.kind = "background"  # logged for false-accept checks, never answered or stored
            self.ui_turn = None
            self._log(turn)
            return
        turn.question = heard or turn.question  # "Hey Edgy." alone: the brain greets back
        self.ui_turn, self.ui_thinking = turn, True
        self.ui_turns.append(turn)
        if self._stale(shot[0]):  # the scene changed after the last look
            self._look(shot)
        if (look := self.ready) is None:
            self.ui_thinking = False
            return  # no camera frame yet: nothing to answer about
        started, detections = time.time(), self.detections
        question = self.embed([turn.question])[0]
        found = self.knowledge.search(question)
        turn.facts = [fact for _, fact in found]
        turn.verbatim = bool(found) and found[0][0] >= VERBATIM
        past = about_past(turn.question)
        recalled, memories = self._recall(turn, look.frame) if past else ([], [])
        # The frame at speech start: the cached look may show an earlier visitor.
        now, taken = (look.frame, look.taken) if shot[0] is None else shot
        # The visitor speaking now (D60, D70): a new face ends the conversation, so none of the
        # earlier exchanges or first-person statements reach this prompt.
        if self._resolve_visitor(turn, now):
            self.ui_turns.clear()
            self.ui_turns.append(turn)
            self.history, self.looked, self.teaching = [], [], None
            self._look((now, taken))  # re-prefilled without the earlier exchanges
            look = self.ready
        statements = self._told(question, turn)
        turn.told = [m["said"] for m in statements]
        told = [f"{brain.age(turn.speech_start - m['ts'])}: {m['said']}" for m in statements]
        self.panel = {"shards": ["knowledge", "seen"], "ms": 1000 * (time.time() - started),
                      "hits": [(f"knowledge: {fact}", score) for score, fact in found] + [
                          (f"said: {m['said']}", m["score"]) for m in statements] + [
                          (f"seen: {line}", None) for line in memories]}
        track = self._visitor()
        recalled_answer = self._code_answer(turn, now, track, look, recalled, memories)
        turn.ui_evidence = self._evidence(turn) if turn.keep and not self.hiding else []
        turn.retrieved = time.time()
        self.last_frame, turn.looked = look.frame, look.taken
        # Each kind of turn gets only its evidence: the image for sight, or whenever the question
        # points at the present; never for small talk or knowledge (it pulled answers to the room).
        turn.kind = self.route(question)
        sees = compares(turn.question) or (turn.kind == "sight" and not past)
        image = look.image if sees else None
        msgs = brain.messages(look.history, image, memories, turn.facts,
                              turn.question, look.changed, past, told)
        # Logged without the image and the system prompt (brain.SYSTEM, fixed per release).
        turn.prompt = [{**m, "content": [c for c in m["content"] if c.get("type") == "text"]}
                       if isinstance(m["content"], list) else m
                       for m in msgs if m["role"] != "system"]
        if recalled_answer:
            turn.verbatim = True
            tokens = self._said(recalled_answer, turn)
        elif turn.verbatim:
            turn.delivered = False  # a fact answered: a comparison's line was not sent
            tokens = self._said(turn.facts[0], turn)
        else:
            tokens = self._tokens(msgs, turn)
        audio_parts = self._speak(tokens, turn)
        turn.done = time.time()
        turn.detect_fps = (self.detections - detections) / (turn.done - started)
        turn.wav = f"{int(turn.line * 1000)}.wav"
        spoken = np.concatenate(audio_parts or [np.zeros(1)])
        turn.audio_s = len(spoken) / RATE
        audio.write_wav(self.out / turn.wav, spoken, RATE)
        self.history = (self.history + [{"role": "user", "content": turn.question},
                                        {"role": "assistant", "content": turn.answer}]
                        )[-2 * HISTORY_TURNS:]
        self.exchanges += 1
        # Findable later; a command ("this is my phone") is an action, never evidence of
        # ownership (things.py holds what was named).
        statement = None if is_question(turn.question) or command(
            turn.question, self.vocab) else question
        if self._store(turn, (now, taken), statement, track):  # one privacy decision for both
            if self.looked and not differs(self.looked[-1], look):
                look.caption = self.looked[-1].caption  # one caption per view run
            self.looked = (self.looked + [look])[-HISTORY_TURNS:]
        # The answer ends when its audio does (the speech end in tests without audio).
        self.last_line = max(turn.speech_end, turn.first_audio + turn.audio_s)
        self._log(turn)

    def _log(self, turn: Turn) -> None:
        self.ui_thinking = False
        if not turn.keep or self.hiding:
            turn.ui_evidence = []
            self.panel = None
            self.ui_turns.clear()
            self.ui_turns.append(turn)
        with (self.out / "turns.jsonl").open("a") as f:
            record = asdict(turn)
            record.pop("ui_evidence")
            f.write(json.dumps(record) + "\n")
        self.turns.put(turn)

    def _told(self, question: np.ndarray, turn: Turn) -> list[dict]:
        """The visitor's earlier statements nearest `question`, except those about an ignored
        kind, and first-person ones (D70) told before this conversation."""
        return [m for m in self.memory.told(question, before=turn.speech_start, n=4)
                if not mentions(m["said"], self.ignored) and (
                    not FIRST_PERSON.search(m["said"]) or m["id"] > self.since)][:2]

    def _store(self, turn: Turn, shot: tuple[np.ndarray, float],
               statement: np.ndarray | None, track: int | None) -> bool:
        """Remember conversation text, linked to the enrolled person in the speech-start frame.
        Nothing while a forgotten visitor may be in view (`hiding`), for a person track that
        asked to be forgotten, or for a turn that deleted an object ("forget my phone" would be
        a new statement about it). Returns whether the turn may be kept: the caller keeps the
        turn's frame in RAM only then."""
        if not turn.keep:
            return False
        frame, taken = shot
        seen = self._whois(frame)
        if self._hidden(seen, track):
            return False
        self._hear_name(turn)
        pid = turn.frame_id = self.memory.add(
            None, turn.question, statement, taken, visitor=turn.visitor)
        if turn.named:
            self.things.link(turn.named, pid)  # "forget my phone" deletes it
        if seen and seen[1]:
            self.recognition.call(lambda f, c: self.people.link(seen[1], [pid]))
        self._retain(time.time())
        return True

    def _hidden(self, seen: tuple[np.ndarray, str | None] | None, track: int | None) -> bool:
        """Whether a turn with face `seen` must not be stored after a "forget me": the same
        face, or no face on the forgotten track or before CLEAR_S has passed. Another face (a
        new visitor, even on the same track) ends the hiding and the track's forgotten state."""
        face_, last = self.hiding or (None, 0.0)
        if seen and face_ is not None and float(seen[0] @ face_) >= THRESHOLD:
            self.hiding = face_, time.time()
            return True
        v = self.visitors.get(track, Visitor())
        if seen:
            self.hiding, v.forgotten = None, False
            return False
        if face_ is not None and time.time() - last > CLEAR_S:
            self.hiding = None
        return self.hiding is not None or v.forgotten

    def _visitor(self) -> int | None:
        """The person track in view with the largest box (at a booth, the one speaking)."""
        with self.detecting:
            boxes = {t: box for t, (label, box) in self.tracker.view().items()
                     if label == "person"}
        return max(boxes, key=lambda t: (boxes[t][2] - boxes[t][0]) * (boxes[t][3] - boxes[t][1]),
                   default=None)

    def _identity(self, turn: Turn, frame: np.ndarray, track: int | None) -> str | None:
        """Identity requests answered in code (robot/people.py) from the face in the current
        frame, never from a track: consent, enrollment, "forget me", "do you remember me",
        "what's my name", and the offer to remember a face after "I'm Ana". None for any
        other turn."""
        if not turn.visitor:
            self._resolve_visitor(turn, frame)
        req = request(turn.question)
        asked, self.asking = self.asking, None
        if asked and not (req and req[0] == "forget") and (
                answer := self._consent(turn, asked, frame)) is not None:
            return answer
        if req is None and not name_in(turn.question):
            return None
        seen = self.turn_seen
        vec, name = seen or (None, None)
        turn.identity["claimed"] = name
        self._hear_name(turn)
        if req and req[0] == "forget":
            turn.keep = False
            ok = self._forget(track, name, vec, turn.visitor)
            return (
                done("forget", name, ok)
                if name
                else (
                    "Done. I have forgotten you."
                    if ok
                    else "I could not forget you. Please ask again."
                )
            )
        if req and req[0] == "enroll" and req[1] and not name and self.people.person(req[1]):
            return f"I already know someone called {req[1]}."
        if req is None:
            return None if name else self._offer(vec)
        answer, action = reply(turn.question, (name, 1.0) if name else None, seen is not None,
                               self.told[0] if self.told else None)
        if action:
            self.asking = action[1], 1, [vec]
        return answer

    def _offer(self, vec: np.ndarray | None) -> str | None:
        """After a name told by an unknown face, offer once per linked visitor to remember
        it (D69): a yes from the same face enrolls through _consent; anything else, or no face
        at the telling (no offer), keeps the name told only."""
        told, offered = self.told
        if offered or vec is None:
            return None
        self.told = told, True
        self.asking = told, 2, [vec]  # 2: an unclear reply never re-asks
        return f"Nice to meet you, {told}! Want me to remember your face so I recognize you " \
               "next time?"

    def _converse(self, turn: Turn, seen: tuple[np.ndarray, str | None] | None) -> bool:
        """Go on with the conversation or start a new one (D60, D70); True for a new one. It
        goes on while the face `seen` now matches the face it is held with; without a held
        face, while this line started at most CONVERSATION_S after the last answer ended (a
        face seen then joins it). A new one drops the told name and the earlier first-person
        statements."""
        held = self.face
        linked = (seen is not None and float(seen[0] @ held) >= THRESHOLD) if held is not None \
            else turn.speech_start - self.last_line <= CONVERSATION_S
        if not self.conversation_started:
            linked = True
        self.conversation_started = True
        if not linked:
            self._clear_confirmation()
            self.window = None
            self.told, self.since = None, time.time_ns() // 1000
            self.conversation_visitor = self.things.new_visitor()
        self.face = seen[0] if seen else None
        return not linked

    def _resolve_visitor(self, turn: Turn, frame: np.ndarray) -> bool:
        """Resolve the speaker once before identity or object actions."""
        if turn.visitor:
            return False
        seen = self._whois(frame, turn)
        new = self._converse(turn, seen)
        person = self.people.person(seen[1]) if seen and seen[1] else None
        self.turn_seen = seen
        turn.visitor = person["visitor"] if person else self.conversation_visitor
        if turn.visitor != self.current_visitor:
            self._clear_confirmation()
        self.current_visitor = turn.visitor
        return new

    def _hear_name(self, turn: Turn) -> None:
        """Hold the told name and update the current visitor record, if it exists."""
        if name := name_in(turn.question):
            self.told = name, bool(self.told and self.told[1])
            self.things.tell(turn.visitor, name)

    def _consent(self, turn: Turn, asked: tuple[str, int, list], frame: np.ndarray
                 ) -> str | None:
        """The answer to "May I remember your face?": enroll on yes, decline on no, ask once
        more when unclear, then None (the conversation goes on)."""
        name, times, shots = asked
        if (yes := consent(turn.question)) is None:
            if times < 2:
                self.asking = name, times + 1, shots
                return f"Sorry, may I remember your face, {name}? Please say yes or no."
            return None
        if yes and self.people.person(name):
            seen = self.turn_seen
            if not seen or seen[1] != name:
                return f"I already know someone called {name}."
        return done("enroll", name, self._enroll(name, shots, frame, turn)) if yes else DECLINED

    def _enroll(self, name: str, shots: list[np.ndarray], frame: np.ndarray, turn: Turn) -> bool:
        """Enroll `name` after consent from the face that asked and the face that said yes
        (two frames, one person): face vectors in the people shard, no image."""
        if (seen := self._whois(frame, turn)) is None or any(
                float(seen[0] @ s) < THRESHOLD for s in shots):
            return False  # no face now, or not the face that asked
        return self.recognition.call(lambda f, c: self.people.enroll(
            name, [*shots, seen[0]], time.time(), turn.visitor), mutate=True)

    def _forget(self, track: int | None, name: str | None, face_: np.ndarray | None,
                visitor: str) -> bool:
        """Delete visitor evidence before removing the object and person references."""
        with self.detecting:
            self._clear_confirmation()
            self.window = None  # no more views are learned for a visitor being forgotten
        try:
            rows = self.things.objects(visitor)
            person = self.people.person(name) if name else None
            self.memory.forget_visitor(visitor)
            self.memory.forget([turn for row in rows for turn in row.payload["turns"]])
            if person:
                self.memory.forget(person.get("linked", []))
            for row in rows:
                self.memory.forget_named(str(row.id))
            self.things.remove_thumbnails([
                view["thumbnail"] for row in rows for view in row.payload["views"]])
            self.recognition.call(lambda f, c: self.things.forget_visitor(visitor), mutate=True)
            if name:  # last: until here the face still resolves to `visitor` for a retry
                self.recognition.call(lambda f, c: self.people.forget(name), mutate=True)
            for row in rows:
                if self.focus:
                    self.focus.forget(str(row.id))
            self.named = self.things.labels()
            self.points = {t: p for t, p in self.points.items() if self.memory.points([p])}
        except Exception:
            traceback.print_exc()
            return False
        if track is not None:
            self.visitors[track] = Visitor(forgotten=True)
        self.hiding = (face_, time.time()) if face_ is not None else None
        self.told, self.looked, self.face, self.asking = None, [], None, None
        self.history, self.ready, self.exchanges = [], None, 0
        self.panel = None
        for turn in [*self.ui_turns, self.ui_turn]:
            if turn is not None:
                turn.ui_evidence = []
        self.ui_turns.clear()
        self.turn_seen = None
        self.teaching = None
        with self.delivery:
            self.verified = None
            self.delivery.notify_all()
        return True

    def _object_owner(self, turn: Turn, name: str) -> tuple[str | None, str, str]:
        """Resolve a named possessive only through an enrolled person."""
        if not re.search(r"\bmy\s", turn.question, re.I) and "'s " in name:
            person_name, object_name = name.split("'s ", 1)
            person = self.people.person(person_name.title())
            return (person["visitor"] if person else None, object_name, f"{person_name}'s")
        return turn.visitor, name, "yours"

    def _things(self, turn: Turn, teaching: tuple[int, int] | None = None) -> str | None:
        """Commands and questions about the visitor's things (robot/things.py): naming,
        "forget my phone", and "where is my phone?". `teaching`: the track "Track this" asked a
        name for, answered by this line within the conversation window. None for any other
        turn."""
        if teaching is not None and turn.speech_start - self.last_line <= CONVERSATION_S and (
                slot := name_slot(turn.question, self.vocab)):
            return self._name(turn, *slot, pin=teaching)
        if cmd := command(turn.question, self.vocab):
            kind, name, labels = cmd
            if kind == "teach":
                self.candidate = self.confirming = None
                self.window = None
                self._settle(turn.speech_start)
                if (track := self._target(turn)) is None:
                    return NOTHING_HELD
                with self.detecting:
                    self.teaching = track, self.focus.epoch(track)
                return "What should I call it?"
            if kind == "name":
                self._settle(turn.speech_start)
                return self._name(turn, name, labels)
            turn.keep = False
            owner, name, possessive = self._object_owner(turn, name)
            if owner is None:
                return f"I don't know which {name} is {possessive}."
            return self._forget_thing(owner, name, labels)
        return self._thing_question(turn)

    def _thing_question(self, turn: Turn) -> str | None:
        """Answer only from the requested owner's object."""
        if (asked := question(turn.question, self.vocab)) is None:
            return None
        mode, name, labels = asked
        self._settle(turn.speech_start)
        owner, name, possessive = self._object_owner(turn, name)
        if owner is None:
            return f"I don't know which {name} is {possessive}."
        if (named := self.things.named(owner, name, labels)) is None:
            # Not an object ("my favorite color"), or "have you seen my keys?" without named
            # keys: the sightings or the brain answer.
            return (
                None
                if not labels and possessive == "yours"
                else ("No, I" if mode == "remember" else "I")
                + f" don't know which {name} is {possessive}."
            )
        if set(named["labels"]) & self.ignored:
            return f"I am ignoring {plural(name)}, so I do not remember any."
        return self._mine(turn, mode, named, "your" if owner == turn.visitor else possessive)

    def _valid_item(self, data):
        """The choice is a current offer of the same session, gallery, and track object."""
        offer = self.offers.get(data.get("track"))
        return bool(offer and data.get("session") == self.session_id and
                    data.get("gallery") == self.recognition.epoch and
                    data.get("epoch") == offer.epoch and
                    0 <= time.time() - offer.seen <= OFFER_HOLD_S)

    def _setting(self, action, data):
        """Apply live microphone, volume, or recognition settings."""
        if action == "settings":
            settings.change(data)
            return True
        if action == "mute":
            if type(data.get("on")) is not bool:
                return False
            self.muted = data["on"]
            return True
        with self.volume_lock:
            try:
                audio.set_volume(data.get("percent"))
            except audio.VolumeNotSaved as error:  # the mixer changed: show the level and why
                self.volume = data["percent"]
                with self.detecting:
                    self.control_message = str(error)
                return False
            except (ValueError, subprocess.SubprocessError, OSError):
                return False
            self.volume = data["percent"]
        return True

    def _control(self, action, data):
        """Queue crop-dependent Ignore; Restore uses the serial memory owner directly."""
        direct = {"mute": self._setting, "volume": self._setting, "settings": self._setting,
                  "forget_object": self._memory_control, "remove_view": self._memory_control}
        if action in direct and isinstance(data, dict):
            return direct[action](action, data)
        if action not in ("ignore", "restore") or not isinstance(data, dict):
            return False
        with self.detecting:
            if action == "ignore" and not self._valid_item(data):
                return False
            if action == "restore" and (data.get("session") != self.session_id or
                    data.get("gallery") != self.recognition.epoch or
                    data.get("id") not in {p["id"] for p in self.things.preferences()}):
                return False
            if action == "ignore":
                if self.jobs.qsize() >= 8:
                    return False
                self.jobs.put(("control", action, data))
                return True
        try:
            message = self._item_control(action, data)
        except RuntimeError as error:
            if str(error) not in ("Recognition is closed", "Recognition requests are full"):
                raise
            message = "That selection expired. Select it again."
        with self.detecting:
            if data.get("session") != self.session_id:
                return False
            self.control_message = message
        return message == "I will notice that item again."

    def _memory_control(self, action, data):
        """Queue a Memory tab edit on the conversation worker, which also writes sightings and
        teaching crops, so a deletion can never race a write of the same object's evidence."""
        if not valid_id(data.get("object")) or (action == "remove_view" and
                not valid_id(data.get("view"))) or self.jobs.qsize() >= 8:
            return False
        self.jobs.put(("memory", action, data))
        return True

    def _memory_job(self, action, data):
        done = self.recognition.call(lambda f, c: self._memory_edit(action, data), mutate=True)
        return "Done." if done else "That memory no longer exists."

    def _memory_list(self):
        def read(f, c):
            objects = []
            for row in self.things.objects():
                ident, payload = str(row.id), row.payload
                label = self.things.label(ident)
                sightings = self.memory.sightings(float("inf"), n=1000000, named=[ident])
                objects.append({"id": ident, "label": label,
                    "owner_label": label.removesuffix("'s " + payload["name"]),
                    "views": [{k: v[k] for k in ("id", "time", "source")}
                              for v in payload["views"]],
                    "last_seen": sightings[0]["last_seen"] if sightings else None,
                    "sightings": len(sightings)})
            return sorted(objects, key=lambda obj: max(
                v["time"] for v in obj["views"]), reverse=True)
        return self.recognition.call(read)

    def _thumbnail(self, ident):
        def read(f, c):
            for row in self.things.objects():
                for view in row.payload["views"]:
                    if view["id"] == ident:
                        try:
                            return (self.things.thumbs / view["thumbnail"]).read_bytes()
                        except FileNotFoundError:
                            return None
            return None
        return self.recognition.call(read)

    def _memory_edit(self, action, data):
        rows = self.things.shard.retrieve([data["object"]], True, False)
        if not rows or rows[0].payload.get("type") != "object":
            return False
        named = {"id": str(rows[0].id), **rows[0].payload}
        if action == "remove_view":
            if data["view"] not in {v["id"] for v in named["views"]}:
                return False
            if len(named["views"]) > 1:
                removed = self.things.remove_view(named["id"], data["view"])
                if removed:
                    self._clear_object_evidence(named["id"])
                return removed
        self._forget_object(named)
        return True

    def _ignore_vectors(self, crops, shot, chosen, gallery):
        """Borrow saved views only when the exact current crop verifies the chosen name."""
        if gallery != self.recognition.epoch:
            return None
        current = crops([shot])
        if chosen:
            hit = self.things.score(current[0], chosen)
            if not hit or hit[0] != chosen or hit[1] < settings.match:
                return None
            return self.things.descriptors(chosen)
        return current

    def _restore_item(self, data):
        """Validate and restore on the recognition owner before clearing display state."""
        with self.detecting:
            if data.get("session") != self.session_id or \
                    self.recognition.epoch != data["gallery"] + 1 or \
                    not self.things.restore_item(data["id"]):
                return False
            if self.focus:
                self.focus.restore(data["id"])
            self.verified = None
            self.delivery.notify_all()
            return True

    def _item_control(self, action, data):
        if action == "restore":
            if data.get("session") != self.session_id or \
                    data.get("gallery") != self.recognition.epoch:
                return "That selection expired. Select it again."
            restored = self.recognition.call(lambda f, c: self._restore_item(data), mutate=True)
            return "I will notice that item again." if restored else "That selection expired."
        with self.detecting:
            if not self._valid_item(data):
                return "That selection expired. Select it again."
            track, offer = data["track"], self.offers[data["track"]]
            title = offer.title if offer.chosen else offer.label
        vectors = self.recognition.call(
            lambda f, c: self._ignore_vectors(c, offer.shot, offer.chosen, data["gallery"]))
        if vectors is None:
            return "That selection expired. Select it again."
        # Mutation invalidates the gallery epoch before entering the owner. The source
        # epoch, session, and selected geometry still have to be current at persistence.
        def persist(faces, crops):
            with self.detecting:
                if self.recognition.epoch != data["gallery"] + 1 or \
                        self.offers.get(track) is not offer or \
                        not self._valid_item({**data, "gallery": self.recognition.epoch}):
                    return None
                ident = self.things.ignore_item(title, vectors)
                del self.offers[track]
                hidden = self.things.hidden_ids()
                self.focus.named = {i: n for i, n in self.focus.named.items()
                                    if n.name not in hidden}
                if track in self.focus.seen and self.focus.epoch(track) == offer.epoch:
                    self.focus.exclude(track, ident)
                    if self.focus.focus == track:
                        self.focus.focus, self.focus.changed = None, time.time()
                        self.focus.challenger = None, 0.0
                self.verified = None
                self.delivery.notify_all()
                return ident
        ident = self.recognition.call(persist, mutate=True)
        if ident:
            self.looked = []  # a retained look may show the item
        return "Okay, I will ignore only that item." if ident else "That selection expired."

    def _settle(self, since: float) -> None:
        """Wait, at most SETTLE_S, until the view holds tracks confirmed after `since` (the
        speech start): a thing shown as the visitor speaks is the thing asked about."""
        deadline = time.time() + SETTLE_S
        while (self.view_at < since + CONFIRM / DETECT_FPS and time.time() < deadline
               and not self.detect_failed):
            time.sleep(0.02)

    def _target(self, turn: Turn, pin: tuple[int, int] | None = None) -> int | None:
        """The object a naming turn binds to (D67): an explicit `pin` track while it is in
        view, else None; otherwise the focus object as it stood at the line's speech start,
        while it is still in view (a focus lost for a moment before the line still counts;
        _bind needs a fresh accepted view anyway), else the focus or held object now."""
        with self.detecting:
            if self.focus is None:
                return None
            if pin is not None:
                return pin[0] if pin[0] in self.focus.visible else None
            if turn.target in self.focus.visible:
                return turn.target
            return self.focus.target([Track(*t) for t in self.tracker.scored()])

    def _name(self, turn: Turn, name: str, labels: list[str],
              pin: tuple[int, int] | None = None) -> str:
        """Bind `name` to the object _target gives, else the one fresh, visible association
        for this exact name."""
        if "'s " in name and not re.search(r"\bmy\s", turn.question, re.I):
            turn.keep = False
            return "I can only learn things that are yours. Say: this is my mouse."
        old = self.things.named(turn.visitor, name, [])
        if {*labels, *(old["labels"] if old else [])} & self.ignored:
            return f"I am ignoring {plural(name)}. Ask me to notice it again first."
        found = self._target(turn, pin)
        with self.detecting:
            tracks = [Track(*t) for t in self.tracker.scored()]
            if found is None and old and self.focus and pin is None:
                names = self.focus.names()
                candidates = [t.id for t in tracks if t.id in self.focus.visible and
                              self.focus.eligible(t) and
                              names.get(t.id) == (old["id"], True) and
                              self.focus.named[t.id].score >= settings.match and
                              0 <= time.time() - self.focus.named[t.id].refreshed <= PREVIEW_TTL]
                if len(candidates) == 1:
                    found = candidates[0]
        if found is None:
            return f"I don't see {article(name)} held up. Hold it up and say it again."
        return self._bind(turn, name, labels, found, pin and pin[1])

    def _bind(self, turn: Turn, name: str, labels: list[str], track: int,
              pinned: int | None = None) -> str:
        """Remember the actual binding crop, its source box/time, and deletion links. `pinned`:
        the focus epoch the track must still have (a track that left and returned is new)."""
        with self.detecting:
            self.window = None
            views = [v for v in [(self.view_taken, *self.view), *reversed(self.views)]
                     if track in v[2] and self.focus.accepts(track, v[0])]
            epoch = self.focus.epoch(track)
            gallery, session = self.recognition.epoch, self.session_id
        if not views or pinned not in (None, epoch):
            return "Sorry, I lost sight of it. Hold it up and say it again."
        taken, frame, view = views[0]
        label, box = view[track]
        if label in BODY:
            return "I only track objects, not people."
        views = [v for v in views if v[2][track][0] not in BODY]  # earlier person views too
        old = self.things.named(turn.visitor, name, [])
        name = old["name"] if old else name
        if {label, *labels, *(old["labels"] if old else [])} & self.ignored:
            return f"I am ignoring {plural(name)}. Ask me to notice it again first."
        seen = self._whois(frame)
        if self._hidden(seen, self._visitor()):
            return "I cannot remember this while the forgotten visitor is in view."
        shots = [cut(f, v[track][1]) for _, f, v in views[:SHOTS]]
        vectors = self.recognition.call(lambda f, c: c(shots))
        if any(self.things.excluded(v) for v in vectors):
            return "I am ignoring this item. Restore it in the camera controls first."
        def bind(faces, crops):
            with self.detecting:
                if self.view[1].get(track, (label,))[0] in BODY or \
                        not self.focus.accepts(track, taken) or \
                        self.focus.epoch(track) != epoch or \
                        self.recognition.epoch != gallery + 1 or self.session_id != session or \
                        time.time() - taken > PREVIEW_TTL:
                    return None
                return self.things.name(
                    turn.visitor,
                    name,
                    sorted({*labels, label}),
                    vectors,
                    shots,
                    self.told[0] if self.told else None,
                )
        stored = self.recognition.call(bind, mutate=True)
        if stored is None:
            return "Sorry, I lost sight of it. Hold it up and say it again."
        ident = stored
        self.named = self.things.labels()
        pid = self.memory.add(shots[0], turn.question, ts=taken, named=ident, label=label,
                              visitor=turn.visitor,
                              box=list(box), source_size=[frame.shape[1], frame.shape[0]])
        self.things.link(ident, pid)
        sighting = self.points[track] = self.memory.sighting(
            label, region(box, frame.shape[1]), taken, ident)
        if seen and seen[1]:
            self.recognition.call(lambda f, c: self.people.link(seen[1], [pid, sighting]))
        turn.memories, turn.named = [pid], ident
        with self.detecting:
            self.focus.bind(track, ident, taken)
            self._start_window(track, epoch, ident)
        self.jobs.put(("caption", pid, brain.jpeg(shots[0])))
        self._retain(time.time())
        return f"Got it, that is your {name}. " + (
            "Turn it slowly so I can see all sides." if settings.window_s > 0 else
            "I will remember it.")

    def _forget_thing(self, owner: str, name: str, labels: list[str]) -> str:
        """Delete evidence first, then thumbnails, the object, and its item Ignore rules."""
        if (named := self.things.named(owner, name, labels, include_ignored=True)) is None:
            return f"I don't know your {name}, so there is nothing to forget."
        self.recognition.call(lambda f, c: self._forget_object(named), mutate=True)
        return f"Done. I have forgotten your {named['name']}."

    def _forget_object(self, named):
        """Shared serial-owner deletion for speech and the Memory tab."""
        if any(p and p["object"] == named["id"] for p in (self.candidate, self.confirming)):
            self.candidate = self.confirming = None
        self.memory.forget(named["turns"])
        self.memory.forget_named(named["id"])
        self.things.forget(named["id"])
        self.points = {t: p for t, p in self.points.items() if self.memory.points([p])}
        with self.detecting:
            if self.window and self.window["name"] == named["id"]:
                self.window = None
            if self.focus:
                self.focus.forget(named["id"])
            self.verified = None
            self.delivery.notify_all()
        self.named, self.looked = self.things.labels(), []
        self._clear_object_evidence(named["id"])

    def _clear_object_evidence(self, ident):
        """Discard displayed sources after any object edit, including thumbnail removal."""
        for turn in [*self.ui_turns, self.ui_turn]:
            if turn is not None:
                turn.ui_evidence = [m for m in turn.ui_evidence if m.get("object") != ident]
        self.panel = None

    def named_evidence(self, turn: Turn, named: dict, this: bool = False
                       ) -> tuple[list[str], int | None, int, str]:
        """Retrieval for a question about the visitor's object `named`: evidence lines (what
        it looks like, when it was named, each object in view with its score, its latest
        matched sightings), the track in view that meets the recognition threshold (None: no
        claim), how many tracks of its kind are in view, and when it was last seen ("20
        seconds ago"). Every object in view is scored, whatever its label; `this`: only the
        one nearest the center. Sets turn.memories to the evidence ids."""
        name = named["name"]
        if set(named["labels"]) & self.ignored:
            return [], None, 0, ""
        with self.detecting:
            frame, view = self.view
            here = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        found = {t: box for t, (label, box) in view.items()
                 if label != "person" and label not in self.ignored}
        if this:
            found = {t: found[t] for t in [_central(found, frame.shape[1])] if t}
        scores = {t: self._score(named, v) for t, v in zip(
            found, self.recognition.call(lambda f, c: c(
                [cut(frame, b) for b in found.values()])) if found else [],
            strict=True)}
        mine = max(scores, key=scores.__getitem__, default=None)
        mine = mine if mine is not None and scores[mine] >= settings.match else None
        past = self.memory.sightings(turn.speech_start, 3, here, named=[named["id"]])
        turns = self.memory.points(named["turns"])
        turn.memories = [t["id"] for t in turns] + [s["id"] for s in past] + (
            [self.points[mine]] if mine in self.points else [])
        ago = lambda ts: brain.age(turn.speech_start - ts)  # noqa: E731
        looks = next((x for t in turns if (x := main_object(t.get("caption", "")))), name)
        lines = [f"The visitor's {name}: {looks}" + (
            f", named {ago(turns[-1]['ts'])}" if turns else "")] + [
            f"In view now: {view[t][0]}, match {scores[t]:.2f} (needs {settings.match})"
            for t in found] + [
            f"Matched sighting: {x['label']}, last seen {ago(x['last_seen'])}" for x in past]
        last = ago(past[0]["last_seen"]) if past else ago(turns[-1]["ts"]) if turns else ""
        return lines, mine, sum(view[t][0] in named["labels"] for t in found), last

    def _score(self, named: dict, v: np.ndarray) -> float:
        """A crop vector's MaxSim score against the requested object `named`."""
        hit = self.things.score(v, named["id"])
        return hit[1] if hit else 0.0

    def _mine(self, turn: Turn, mode: str, named: dict, possessive: str = "your") -> str:
        """A minimal code answer from named_evidence until those lines go to the brain."""
        name = named["name"]
        _, mine, found, last = self.named_evidence(turn, named, mode == "this")
        if mode == "this":
            return (f"I don't see {article(name)} right now." if not found else
                    f"Yes, this is {possessive} {name}." if mine is not None else
                    f"No, I don't think this is {possessive} {name}.")
        said = f"Yes, I remember {possessive} {name}. " * (mode == "remember")
        if mine is not None:
            return said + f"Yes, {possessive} {name} is here now."
        if found:
            owned = "yours" if possessive == "your" else possessive
            return said + f"I see {article(name)}, but I am not sure it is {owned}."
        return said + (f"I last saw {possessive} {name} {last}; I don't see it now." if last else
                       f"I don't see {possessive} {name} now.")

    def _recall(self, turn: Turn, frame: np.ndarray) -> tuple[list[dict], list[str]]:
        """Captioned frames (newest first) and the Memories lines, oldest first, one short line
        each with its age: each distinct caption, and the newest sighting of each kind out of
        view (no sides, D61). What is in view now is the present, not something seen before."""
        selected = self.things.visual_links(self.ignored)
        recalled = [{**m, "caption": unmention(m["caption"], self.ignored)}  # shown() reads lines
                    for m in self.memory.recent(before=turn.speech_start,
                                                selected=selected,
                                                skip=self.ignored)
                    if "box" in m or np.abs(
                        m["thumb"] - thumb(frame).astype(np.float32)).mean() > SCENE_CHANGE]
        with self.detecting:  # a consistent snapshot of the tracks
            in_view = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        newest: dict[str, dict] = {}  # kind -> its newest sighting: one line per object
        for s in self.memory.sightings(turn.speech_start, SIGHTINGS, in_view, self.ignored,
                                       named=selected):
            newest.setdefault(kind_of(s["label"]), s)
        sights = list(newest.values())[:LINES]
        turn.memories = [m["id"] for m in recalled + sights]
        ago = lambda ts: brain.age(turn.speech_start - ts)  # noqa: E731
        captions = {" ".join(m["caption"].split()): m for m in recalled[::-1]  # one line each,
                    if m["caption"]}  # and one frame told twice is one line
        lines = sorted([(m["ts"], f"{ago(m['ts'])}: {c}") for c, m in captions.items()] + [
            (s["last_seen"], f"{ago(s['last_seen'])}: you saw {article(s['label'])}; it is not "
                             "in view now") for s in sights], key=lambda x: x[0])
        return recalled, [line for _, line in lines]

    def _evidence(self, turn: Turn) -> list[dict]:
        """Resolve supplied evidence once on the conversation worker, with stored object links."""
        points = self.memory.points(turn.memories)
        ids = {m["named"] for m in points if m.get("named")}
        point_ids = {m["id"] for m in points}
        def objects(f, c):
            named, links = {}, {}
            for row in self.things.objects():
                ident, payload = str(row.id), row.payload
                if ident not in ids and not point_ids.intersection(payload["turns"]):
                    continue
                named[ident] = {"label": self.things.label(ident),
                    "view": next((v["id"] for v in payload["views"]
                                  if (self.things.thumbs / v["thumbnail"]).is_file()), None)}
                links.update({pid: ident for pid in payload["turns"]})
            return named, links
        named, links = self.recognition.call(objects) if points else ({}, {})
        summaries = {}
        for point in sorted(points, key=lambda p: p.get("last_seen", p.get("ts", 0))):
            ident = point.get("named") or links.get(point["id"])
            obj = named.get(ident)
            if point.get("named") and obj is None:
                continue
            text = point.get("caption") or point.get("said") or point.get("label")
            if not text:
                continue
            source = "Observed object" if "last_seen" in point else (
                "Stored caption" if point.get("caption") else "Stored statement")
            item = {"id": point["id"], "label": obj["label"] if obj else source,
                    "text": text, "source": source,
                    "time": point.get("last_seen", point.get("ts"))}
            if obj:
                item.update(object=ident, view=obj["view"])
            summaries[ident or point["id"]] = item
        if turn.delivered:
            look = next((look for look in self.looked if look.taken == turn.selected), None)
            if look and look.caption:
                summaries["session"] = {"label": "Session caption", "text": look.caption,
                                        "source": "Generated caption in this conversation",
                                        "time": look.taken}
        return list(summaries.values())

    def _sighted(self, turn: Turn) -> str | None:
        """The answer to a sighting question from the sightings and the tracks in view now, or
        None for another question or when no sighting matches (the brain answers then, with
        captions). The sightings it names become the turn's evidence."""
        if self.detect_failed:  # the tracks in view are stale: claim nothing about now
            return None
        context = [m["content"] for m in self.history[:-3:-1]]  # the last answer first
        if (query := sighting_query(turn.question, context, self.vocab)) is None:
            return None
        if (labels := query[1].get("label")) and labels <= self.ignored:
            return f"I am ignoring {plural(kind_of(min(labels)))}, so I do not remember any."
        with self.detecting:
            here = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        # Enough tracks to group by kind and region before the answer limit (ponytail: a
        # window, not a group-by; Edge 0.8 has none. Facet on label if one kind floods it).
        past = self.memory.sightings(turn.speech_start, SIGHTINGS, here, self.ignored,
                                     named=self.things.visual_links(self.ignored), **query[1])
        with self.detecting:
            now = [{"id": -t, "label": label, "region": region(box, self.view[0].shape[1]),
                    "last_seen": self.view_taken} for t, (label, box) in self.view[1].items()
                   if label not in self.ignored and t not in self.focus.excluded
                   and t not in self.focus.checking]
        if found := sighting_answer(*query, past, now,
                                    lambda ts: brain.age(turn.speech_start - ts)):
            answer, ids = found
            turn.memories = [i for i in ids if i > 0]
            return answer
        return None

    def _said(self, fact: str, turn: Turn) -> Iterator[str]:
        turn.first_token, turn.answer = time.time(), fact
        yield fact

    def _tokens(self, msgs: list[dict], turn: Turn) -> Iterator[str]:
        """The brain's answer as it streams. Decode pauses while the first phrase is
        synthesized (D66): _speak closes self.stream, and the next delta asked for resumes it
        with the answer so far as an assistant prefill. Closing this generator closes the
        stream (an interrupted turn stops decoding)."""
        self.stream = self.brain.answer(msgs)
        try:
            while (delta := next(self.stream, None)) is not None:
                turn.first_token = turn.first_token or time.time()
                turn.answer += delta
                yield delta
                if self.stream is None:  # paused
                    turn.resumed = True
                    self.stream = self.brain.answer(msgs, prior=turn.answer)
        finally:
            if self.stream:
                self.stream.close()
            self.stream = None
        turn.answer = turn.answer.strip()

    def _speak(self, tokens: Iterator[str], turn: Turn) -> list[np.ndarray]:
        """Synthesize and play the answer phrase by phrase. If synthesis fails, `tokens` is
        closed, which stops decoding, before the error propagates."""
        audio_parts = []
        try:
            for text in phrases(tokens):
                if not turn.first_phrase and self.stream:  # Kokoro waits for the GPU (D66)
                    self.stream.close()  # llama-server stops this generation
                    self.stream = None
                turn.first_phrase = turn.first_phrase or time.time()
                pcm = self.voice.say(text)
                turn.first_audio = turn.first_audio or time.time()
                self.speaker.play(pcm)
                audio_parts.append(pcm)
        finally:
            tokens.close()
        return audio_parts

    def close(self) -> None:
        """Finish the queued work, stop the threads, and release the shards and llama-server,
        so a new Robot can open the same memory folder (a restart)."""
        watch, detect, transcribe, work = self.threads
        if self.video:
            self.video.close()
        self.closing.set()
        watch.join()               # no more looks
        detect.join()              # no more sightings
        if self.detect:
            self.detect.close()
        self.lines.put(None)
        transcribe.join()          # no more turns
        self.recognition.pause()   # no preview producer remains; priority turn requests still work
        self.jobs.join()           # the last turns and the captions they queue
        self.jobs.put(None)
        work.join()
        self.recognition.close()
        self.speaker.close()  # let the last phrase finish playing
        self.memory.shard.close()
        self.people.shard.close()
        self.things.shard.close()
        self.knowledge.shard.close()
        self.brain.close()


def main() -> None:
    from robot.camera import Camera, FileCamera
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--camera-file", type=Path,
                   help="recorded camera fixture, in stored orientation")
    a = p.parse_args()
    with contextlib.suppress(audio.VolumeNotSaved):  # the level is set; saving can wait
        audio.set_volume(audio.saved_volume())
    chunks, play = audio.mic(), audio.aplay(audio.SPEAKER, RATE)
    camera = FileCamera() if a.camera_file else Camera()
    robot = Robot(camera, SHARED / "sessions" / time.strftime("%Y%m%d-%H%M%S"), play=play)
    if a.camera_file:
        camera.show(a.camera_file)  # begin the clip after model warmup
        robot.camera_source = "Recorded camera"
    print("listening", flush=True)
    for chunk in chunks:
        robot.hear(chunk)
        if robot.detect_failed:
            raise RuntimeError("detection stopped") from robot.detect_failed
    robot.close()
    camera.close()


if __name__ == "__main__":
    main()
