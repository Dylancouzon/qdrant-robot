"""The robot: hears a line, looks, recalls, answers aloud, and remembers what its detector
tracks. One process; the LLM runs in a supervised llama-server child. Every turn logs its stage
times and saves its answer audio.

    python -m robot.main                       camera, camera microphone, no speaker
    python -m robot.main --speaker plughw:1,0  ... and an ALSA speaker
    python -m robot.main --listen 7070         microphone and speaker of a Mac client
"""
import argparse
import contextlib
import json
import os
import queue
import re
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from robot import audio, brain
from robot.asr import Ears, Scribe, woken
from robot.config import SHARED
from robot.detect import CONFIRM, Detector, Sighting, Tracker
from robot.faces import Faces
from robot.focus import Focus, Track
from robot.knowledge import VERBATIM, Knowledge
from robot.memory import (
    Memory,
    about_now,
    about_past,
    article,
    is_question,
    kind_of,
    main_object,
    shown,
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
    name_in,
    reply,
    request,
)
from robot.route import Router
from robot.text_embed import TextEmbedder
from robot.things import (
    MATCH,
    SHOTS,
    Crops,
    Things,
    command,
    cut,
    plural,
    mentions,
    question,
    unmention,
)
from robot.tts import RATE, Speaker, phrases
from robot.view import Screen, View

HISTORY_TURNS = 4  # the conversation window, in exchanges
WATCH_S = 0.3      # how often idle time checks whether the prefilled frame is stale
SCENE_CHANGE = 8.0  # mean absolute difference (0-255) of 64x36 grey thumbnails
# Camera rate: unthrottled detection halved LLM decode (research/detector.md).
DETECT_FPS = 15
DETECT_RESTARTS = 3  # detector failures it recovers from by reloading; the next one stops it
SIGHTINGS = 64  # the newest out-of-view sightings a sighting answer groups
WHERE = {"left": "on your left", "center": "in the center", "right": "on your right"}
# A statement about the speaker (D70): recalled only in the conversation it was told in.
FIRST_PERSON = re.compile(r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine|myself)\b", re.I)
# Identity is the face in the current frame, never a track (design
# reviews/20261008-161702-78890-design.md): a visitor replacing another keeps the track id.
# A face step runs only on an identity question and after a turn is spoken (to link it).
# Without an enrolled face match, a name told in this conversation answers (D60).
CONVERSATION_S = 20  # a line this soon after the last answer continues the conversation (D65)
CLEAR_S = 30  # after "forget me", turns are not stored until another face, or no face this long
VIEW_S = 0.33  # spacing of the recent views a named object's crops come from
SETTLE_S = 0.5  # how long a "my phone" turn waits for tracks confirmed after its speech start


def _central(boxes: dict[int, tuple], width: int) -> int | None:
    """The track whose box center is nearest the frame's vertical center line."""
    return min(boxes, key=lambda t: abs(sum(boxes[t][::2]) / 2 - width / 2), default=None)


def scene_change(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(thumb(a).astype(np.float32) - thumb(b)).mean())


@dataclass
class Look:
    """A frame whose prompt prefix, after `exchanges` exchanges, is in the brain's KV cache."""
    frame: np.ndarray
    taken: float                  # capture time: the evidence time of what the brain saw
    image: dict
    exchanges: int
    changed: bool                 # the view differs from the previous turn's
    history: list[dict]           # the conversation as prefilled with this frame


@dataclass
class Visitor:
    """What a person track carries for its life only (D49)."""
    forgotten: bool = False   # "forget me": nothing more of this track is written


@dataclass
class Turn:
    """One exchange, with wall-clock stage times (time.time())."""
    question: str = ""
    answer: str = ""
    facts: list[str] = field(default_factory=list)
    memories: list[int] = field(default_factory=list)  # evidence: ids of the frames recalled
    kind: str = ""                # sight, recall, social, or knowledge (robot/route.py)
    verbatim: bool = False        # answered from Edge in code (a fact, a shown object), no LLM
    told: list[str] = field(default_factory=list)  # earlier visitor statements recalled
    prompt: list = field(default_factory=list)  # the brain's messages without images or system
    frame_id: int = 0             # the frame this turn saw, stored as a memory
    speech_start: float = 0.0     # the VAD heard speech start
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
    named: str = ""               # the visitor's object this turn named: linked to its frame
    keep: bool = True             # False: not stored ("forget my phone")
    resumed: bool = False         # decode paused at the first phrase and resumed (D66)


class Robot:
    def __init__(self, camera, out: Path, memory: Path = SHARED / "memory",
                 play: Callable[[np.ndarray], None] | None = None, model: str = brain.MODEL,
                 wake_word: bool = True):
        """`wake_word` False: every line is answered (scripted sessions never say it)."""
        self.camera, self.out, self.wake_word = camera, out, wake_word
        out.mkdir(parents=True, exist_ok=True)
        self.knowledge, self.embed, self.faces = Knowledge(), TextEmbedder(), Faces()
        self.people = People(memory)
        self.memory = Memory(memory)
        self.things, self.crops = Things(memory), Crops()
        self.named, self.ignored = self.things.labels(), self.things.ignored()
        self.scribe = Scribe()
        self.route = Router(self.embed)
        self.voice = Speaker()
        self.speaker = audio.Mouth(play)
        self.brain = brain.Brain(model)
        self.detect, self.tracker = Detector(), Tracker()
        self.vocab = set(self.detect.names.values())  # the labels the detector can give
        self.points: dict[int, int] = {}  # track id -> its sighting point, while it is tracked
        self.away: set[int] = set()  # tracked ids reported gone: their points may be evicted
        self.visitors: dict[int, Visitor] = {}  # person track id -> what is known of them
        # (frame, Tracker.view()) of the last detected frame, and of up to SHOTS frames VIEW_S
        # apart: a box and the frame it was found in stay together for a crop.
        self.view: tuple[np.ndarray | None, dict] = (None, {})
        self.view_at = 0.0  # when self.view was detected
        self.focus: Focus | None = None  # the focus object and shown names (D63), per frame
        self.screen: tuple[np.ndarray | None, Screen] = (None, Screen())  # what the view draws
        self.views: deque[tuple[float, np.ndarray, dict]] = deque(maxlen=SHOTS)
        self.mine: dict[int, str] = {}  # track id -> the visitor's object it was named as
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
        self.panel: dict | None = None  # the last retrieval, for the view's memory panel
        self.stream: Iterator[str] | None = None  # the brain's answer while a turn decodes
        self.detections = 0                     # frames detected so far
        self.detect_failed: Exception | None = None  # set when detection stopped for good
        self.history: list[dict] = []
        self.exchanges = 0                      # counts every exchange; history is capped
        self.last_frame: np.ndarray | None = None  # the frame of the previous turn
        self.jobs: queue.Queue = queue.Queue()  # GPU work for llama-server, in order
        self.lines: queue.Queue = queue.Queue()  # finished lines for the final transcript
        self.asked = 0                          # turns queued so far (one per heard line)
        self.turns: queue.Queue[Turn] = queue.Queue()  # finished turns, for replay and logs
        self.ready: Look | None = None          # the frame whose prompt prefix is prefilled
        self.speaking = False                   # a visitor is mid-line: background work yields
        self.speech_start = 0.0
        self.start_frame: tuple[np.ndarray | None, float] = (None, 0.0)  # frame, capture time
        self.uncaptioned: list[tuple[int, dict]] = []  # (frame id, encoded frame)
        self.closing = threading.Event()
        self.detecting = threading.Lock()       # held while a frame is detected and tracked
        self.threads = [threading.Thread(target=t, name=t.__name__, daemon=True)
                        for t in (self._watch, self._detect, self._transcribe, self._work)]
        for t in self.threads:
            t.start()
        self.ears = Ears(self._heard_start, self._heard_line)
        token = os.environ.get("ROBOT_VIEW_TOKEN")  # the booth video view (D59), off without one
        self.video = View(self._shown, int(os.environ.get("ROBOT_VIEW_PORT", "8090")), token,
                          os.environ.get("ROBOT_VIEW_HOST", "127.0.0.1")) if token else None

    def hear(self, chunk: np.ndarray) -> None:
        self.ears.feed(chunk)

    def ask(self, text: str) -> None:
        """A typed line, entering where a transcript would (oracle replays, debugging)."""
        self._heard_start()
        t = time.time()
        self.speaking = False
        self.asked += 1
        self.jobs.put(("turn", Turn(question=text, line=t, transcribed=t, speech_end=t,
                                    speech_start=self.speech_start), self.start_frame))

    def reset(self, memory: Path) -> None:
        """Start over with an empty memory and conversation (scripted sessions). Detection
        pauses so no sighting of the old session reaches the new memory, and the tracker starts
        over so objects still in view are sighted again."""
        self.jobs.join()  # the turns first: a turn's recall takes self.detecting
        with self.detecting:
            self.jobs.join()  # sightings queued since
            self.memory.shard.close()
            self.people.shard.close()
            self.things.shard.close()
            self.people = People(memory)
            self.memory = Memory(memory)
            self.things = Things(memory)
            self.named, self.ignored = self.things.labels(), self.things.ignored()
            self.history, self.exchanges, self.ready = [], 0, None
            self.last_frame, self.points, self.tracker = None, {}, Tracker()
            self.away, self.visitors, self.asking, self.hiding = set(), {}, None, None
            self.told, self.last_line, self.face = None, 0.0, None
            self.since, self.panel = time.time_ns() // 1000, None
            self.view, self.mine = (None, {}), {}
            self.focus, self.screen = None, (None, Screen())
            self.views.clear()

    def _heard_start(self) -> None:
        self.speaking, self.speech_start = True, time.time()
        self.start_frame = self.camera.latest()  # what the visitor sees as they speak
        if self._stale(self.start_frame[0]):
            self.jobs.put(("look", self.start_frame))

    def _heard_line(self, speech: np.ndarray, speech_end: float) -> None:
        self.speaking = False
        self.lines.put((speech, time.time(), speech_end, self.speech_start, self.start_frame))

    def _transcribe(self) -> None:
        # Its own thread: the final transcript overlaps a prefill instead of queuing behind it.
        while (line := self.lines.get()) is not None:  # None: close() stops the thread
            speech, t_line, speech_end, speech_start, shot = line
            if text := self.scribe(speech):  # empty: noise the VAD took for speech
                self.asked += 1
                self.jobs.put(("turn", Turn(question=text, line=t_line,
                                            transcribed=time.time(), speech_end=speech_end,
                                            speech_start=speech_start), shot))
            self.lines.task_done()

    def _watch(self) -> None:
        # Keep a recent frame prefilled while nobody speaks, so a turn rarely waits for one.
        while not self.closing.wait(WATCH_S):
            shot = self.camera.latest()
            if not self.speaking and self.jobs.empty() and self._stale(shot[0]):
                self.jobs.put(("look", shot))

    def _detect(self) -> None:
        # Detection and tracking at camera rate on the newest frame; sightings are written by
        # the worker after the turns queued before them, never during a turn.
        due, failures = time.time(), 0
        while not self.closing.wait(max(0.0, due - time.time())):
            due = max(due + 1 / DETECT_FPS, time.time())
            frame, _ = self.camera.latest()
            if frame is None:
                continue
            try:
                self.detect = self.detect or Detector()
                found = self._track(frame, self.detect(frame))
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
                self.jobs.put(("sight", found, frame))

    def _track(self, frame: np.ndarray, dets: list) -> list[Sighting]:
        """Track one detected frame; keep its boxes with the frame they are in, for crops."""
        with self.detecting:
            found = self.tracker.update(dets, frame.shape[1], time.time())
            self.view, self.view_at = (frame, self.tracker.view()), time.time()
            if not self.views or time.time() - self.views[-1][0] >= VIEW_S:
                self.views.append((time.time(), *self.view))
            self._refocus(frame)
        return found

    def _refocus(self, frame: np.ndarray) -> None:
        """Feed the focus the tracks in view on the frame just tracked, and keep the view's
        boxes for that frame (held under self.detecting)."""
        tracks = [Track(*t) for t in self.tracker.scored()]
        people = [t.box for t in tracks if t.label == "person"]
        self.focus = self.focus or Focus(frame.shape[1], frame.shape[0])
        self.focus.ignored = self.ignored
        self.focus.update(self.view_at, tracks, people)
        self.screen = frame, Screen(self.focus.boxes(tracks, people), memory=self.panel)

    def _shown(self) -> tuple[np.ndarray | None, Screen]:
        """The view's source: the newest tracked frame and its boxes."""
        with self.detecting:
            return self.screen

    def _sight(self, found: list[Sighting], frame: np.ndarray) -> None:
        """One point per track (label, region, times; no frame: answers use labels, and a
        stored frame could hold a visitor's face): stored when confirmed, updated when its
        region or majority label changes and when it leaves; each write bounds the evidence
        to the retention window and caps (Memory.retain), never evicting a track that is not
        gone (in view, or missed for less than MAX_MISSED frames). An ignored kind's new track
        is not stored; a new track of a named kind is matched against the visitor's objects."""
        for s in found:
            pid = self.points.get(s.track)
            if s.ended:
                self._end(s.track)
            elif s.gone:
                self.away.add(s.track)
                if pid:
                    self.memory.set(pid, label=s.label, last_seen=s.seen)
            else:
                self.away.discard(s.track)
                if pid:
                    self.memory.set(pid, label=s.label, region=s.region, last_seen=s.seen)
                elif s.label not in self.ignored:
                    self.points[s.track] = self.memory.sighting(
                        s.label, s.region, s.seen, self.mine.get(s.track) or self._match(frame, s))
        self._retain(max(s.seen for s in found))

    def _end(self, track: int) -> None:
        """A track no new track can continue: forget its id."""
        self.points.pop(track, None)  # its last_seen was written when it went out of view
        self.away.discard(track)
        self.visitors.pop(track, None)
        self.mine.pop(track, None)

    def _whois(self, frame: np.ndarray, turn: Turn | None = None
               ) -> tuple[np.ndarray, str | None] | None:
        """The visitor's face in the whole `frame` (people.face) and the enrolled person it
        matches by the two-shot rule, or None without a usable face. An identity turn logs
        the face width, the step time, and the two best people's scores, never the face."""
        started, found = time.time(), face(self.faces, frame)
        scores = self.people.scores(found[0])[:2] if found else []
        name = scores[0][0] if scores and scores[0][2] >= THRESHOLD else None
        if turn is not None:
            turn.identity = {"face_px": found[1] if found else 0, "claimed": None,
                             "face_ms": round(1000 * (time.time() - started), 1),
                             "scores": [[n, round(b, 3), round(s, 3)] for n, b, s in scores]}
        return (found[0], name) if found else None

    def _match(self, frame: np.ndarray, s: Sighting) -> str | None:
        """The visitor's object a new track's crop matches, whatever its label, or None (no
        named object or a person: no embedding runs; or the score is under MATCH)."""
        if not self.named or s.label == "person":
            return None
        hit = self.things.score(self.crops([cut(frame, s.box)])[0])
        return hit[0] if hit and hit[1] >= MATCH else None

    def _retain(self, now: float) -> None:
        """Bound memory to the retention window and caps (Memory.retain) after each write,
        never evicting the point of a track that is not gone."""
        evicted = set(self.memory.retain(now, {
            p for t, p in self.points.items() if t not in self.away}))
        self.points = {t: p for t, p in self.points.items() if p not in evicted}

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
            elif job[0] == "sight":
                self._sight(*job[1:])
            elif (caption := self.brain.caption(job[2], lambda: self.speaking)) is None:
                self.uncaptioned.append(job[1:])  # a visitor spoke: retry after their turn
            else:
                self.memory.set(job[1], caption=caption)
            self.jobs.task_done()

    def _look(self, shot: tuple[np.ndarray, float]) -> None:
        changed = self.last_frame is not None and scene_change(
            self.last_frame, shot[0]) > SCENE_CHANGE
        # After the view changes, the brain's earlier answers describe a scene that is gone: keep
        # only what the visitor said, which a 2B brain otherwise trusts over the image (D27).
        history = [m for m in self.history if m["role"] == "user"] if changed else self.history
        look = Look(shot[0], shot[1], brain.jpeg(shot[0]), self.exchanges, changed, history)
        self.brain.prefill(brain.messages(history, look.image))
        self.ready = look

    def _turn(self, turn: Turn, shot: tuple[np.ndarray | None, float]) -> None:
        """Answer about the frame shown when this line's speech started, or about an earlier
        look of the same scene; the frame used is the one stored as evidence. A line is
        answered only after the wake phrase, or as a follow-up within CONVERSATION_S of the
        last answer (D65); the wake phrase is not part of the question."""
        heard = woken(turn.question)
        if self.wake_word and heard is None and \
                turn.speech_start - self.last_line > CONVERSATION_S:
            turn.kind = "background"  # logged for false-accept checks, never answered or stored
            self._log(turn)
            return
        turn.question = heard or turn.question  # "Hey Edgy." alone: the brain greets back
        if self._stale(shot[0]):  # the scene changed after the last look
            self._look(shot)
        if (look := self.ready) is None:
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
        if self.history and self._converse(turn, self._whois(now)):
            self.history = []
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
        recalled_answer = self._identity(turn, now, track) or self._things(turn) or shown(
            turn.question, recalled, lambda m: brain.age(turn.speech_start - m["ts"])
        ) or self._sighted(turn)
        turn.retrieved = time.time()
        self.last_frame = look.frame
        # Each kind of turn gets only its evidence: the image for sight, or whenever the question
        # points at the present; never for small talk or knowledge (it pulled answers to the room).
        turn.kind = self.route(question)
        sees = about_now(turn.question) or (turn.kind == "sight" and not past)
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
        statement = None if is_question(turn.question) else question  # findable later
        self._store(turn, (now, taken, look.image if now is look.frame else brain.jpeg(now)),
                    statement, track)
        # The answer ends when its audio does (the speech end in tests without audio).
        self.last_line = max(turn.speech_end, turn.first_audio + turn.audio_s)
        self._log(turn)

    def _log(self, turn: Turn) -> None:
        with (self.out / "turns.jsonl").open("a") as f:
            f.write(json.dumps(asdict(turn)) + "\n")
        self.turns.put(turn)

    def _told(self, question: np.ndarray, turn: Turn) -> list[dict]:
        """The visitor's earlier statements nearest `question`, except those about an ignored
        kind, and first-person ones (D70) told before this conversation."""
        return [m for m in self.memory.told(question, before=turn.speech_start, n=4)
                if not mentions(m["said"], self.ignored) and (
                    not FIRST_PERSON.search(m["said"]) or m["id"] > self.since)][:2]

    def _store(self, turn: Turn, shot: tuple[np.ndarray, float, dict],
               statement: np.ndarray | None, track: int | None) -> None:
        """Remember the turn after its answer was spoken: `shot` (the frame at speech start,
        its capture time, its image for the caption), what was said, a caption later, linked
        to the enrolled person whose face it shows. Nothing while a forgotten visitor may be
        in view (`hiding`), for a person track that asked to be forgotten, or for a turn that
        deleted an object ("forget my phone" would be a new statement about it)."""
        if not turn.keep:
            return
        frame, taken, image = shot
        seen = self._whois(frame)
        if self._hidden(seen, track):
            return
        self._hear_name(turn, seen)
        pid = turn.frame_id = self.memory.add(frame, turn.question, statement, taken)
        if turn.named:
            self.things.link(turn.named, pid)  # "forget my phone" deletes it
        if seen and seen[1]:
            self.people.link(seen[1], [pid])  # "forget me" deletes it if still kept
        self._retain(time.time())
        for job in [*self.uncaptioned, (pid, image)]:
            self.jobs.put(("caption", *job))
        self.uncaptioned = []

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
        asked, self.asking = self.asking, None
        if asked and (answer := self._consent(turn, asked, frame)) is not None:
            return answer
        if (req := request(turn.question)) is None and not name_in(turn.question):
            return None
        seen = self._whois(frame, turn)
        vec, name = seen or (None, None)
        turn.identity["claimed"] = name
        self._hear_name(turn, seen)
        if req is None:
            return None if name else self._offer(vec)
        answer, action = reply(turn.question, (name, 1.0) if name else None, seen is not None,
                               self.told[0] if self.told else None)
        if action and action[0] == "forget":
            return done("forget", action[1], self._forget(track, action[1], vec))
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
        if not linked:
            self.told, self.since = None, time.time_ns() // 1000
        self.face = seen[0] if seen else None
        return not linked

    def _hear_name(self, turn: Turn, seen: tuple[np.ndarray, str | None] | None) -> None:
        """Follow the conversation (_converse) and hold the name told in it."""
        self._converse(turn, seen)
        if name := name_in(turn.question):
            self.told = name, bool(self.told and self.told[1])

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
        return done("enroll", name, self._enroll(name, shots, frame, turn)) if yes else DECLINED

    def _enroll(self, name: str, shots: list[np.ndarray], frame: np.ndarray, turn: Turn) -> bool:
        """Enroll `name` after consent from the face that asked and the face that said yes
        (two frames, one person): face vectors in the people shard, no image."""
        if (seen := self._whois(frame, turn)) is None or any(
                float(seen[0] @ s) < THRESHOLD for s in shots):
            return False  # no face now, or not the face that asked
        return self.people.enroll(name, [*shots, seen[0]], time.time())

    def _forget(self, track: int | None, name: str, face_: np.ndarray) -> bool:
        """"Forget me" from the face matched now: the person point, every linked turn still
        kept (its frame, caption, and statement), and nothing more written for the person track
        in view; pending caption writes to a deleted point are dropped by Memory.set."""
        # Carried gap: a turn frame where this person appears unidentified (before enrollment,
        # or behind another visitor) is not linked, so it stays until retention (RETAIN_S, 12 h).
        try:
            self.memory.forget(self.people.forget(name))
        except Exception:
            traceback.print_exc()
            return False
        if track is not None:
            self.visitors[track] = Visitor(forgotten=True)
        self.hiding, self.told = (face_, time.time()), None
        return True

    def _things(self, turn: Turn) -> str | None:
        """Commands and questions about the visitor's things (robot/things.py): naming,
        "forget my phone", ignore rules, and "where is my phone?". None for any other turn."""
        if cmd := command(turn.question, self.vocab):
            kind, name, labels = cmd
            if kind == "name":
                self._settle(turn.speech_start)
                return self._name(turn, name, labels)
            if kind == "forget":
                turn.keep = False
                return self._forget_thing(name, labels)
            self.things.ignore(labels, kind == "ignore")
            self.ignored = self.things.ignored()
            return (f"Okay, I will ignore {plural(name)}." if kind == "ignore" else
                    f"Okay, I will notice {plural(name)} again.")
        if (asked := question(turn.question, self.vocab)) is None:
            return None
        mode, name, labels = asked
        self._settle(turn.speech_start)
        if mode == "ignoring":
            return (f"Yes, I am ignoring {plural(name)}." if set(labels) & self.ignored else
                    f"No, I am not ignoring {plural(name)}.")
        if (named := self.things.named(name, labels)) is None:
            # Not an object ("my favorite color"), or "have you seen my keys?" without named
            # keys: the sightings or the brain answer.
            return None if mode == "seen" or not labels else (
                "No, I" if mode == "remember" else "I") + f" don't know which {name} is yours."
        return self._mine(turn, mode, named)

    def _settle(self, since: float) -> None:
        """Wait, at most SETTLE_S, until the view holds tracks confirmed after `since` (the
        speech start): a thing shown as the visitor speaks is the thing asked about."""
        deadline = time.time() + SETTLE_S
        while (self.view_at < since + CONFIRM / DETECT_FPS and time.time() < deadline
               and not self.detect_failed):
            time.sleep(0.02)

    def _name(self, turn: Turn, name: str, labels: list[str]) -> str:
        """Bind `name` to the object the focus gives (D67, Focus.target): the focus object,
        else the most salient object held up. Otherwise ask for it held up."""
        with self.detecting:
            found = self.focus and self.focus.target([Track(*t) for t in self.tracker.scored()])
        if found is None:
            return f"I don't see {article(name)} held up. Hold it up and say it again."
        return self._bind(turn, name, labels, found)

    def _bind(self, turn: Turn, name: str, labels: list[str], track: int) -> str:
        """Store `name` with crops of `track` from the recent views, and tag its sighting."""
        with self.detecting:
            views = [v for v in [self.view, *(x[1:] for x in self.views)] if track in v[1]]
        if not views:
            return "Sorry, I lost sight of it. Hold it up and say it again."
        shots = [cut(frame, v[track][1]) for frame, v in views[:SHOTS]]
        label = views[0][1][track][0]  # its own label too: "bag" when a phone looks like one
        self.things.name(name, sorted({*labels, label}), self.crops(shots))
        self.named = self.things.labels()
        self.mine[track] = name  # its sighting may still be queued behind this turn
        if pid := self.points.get(track):
            self.memory.set(pid, named=name)
            turn.memories = [pid]
        turn.named = name
        return f"Got it, that is your {name}. I will remember it."

    def _forget_thing(self, name: str, labels: list[str]) -> str:
        """Delete the named object, the turns that named it (frame and statement), and its
        tag on every sighting; it survives no restart."""
        if (named := self.things.named(name, labels)) is None:
            return f"I don't know your {name}, so there is nothing to forget."
        self.memory.forget(self.things.forget(named["name"]))
        self.memory.untag(named["name"])
        # A sighting still queued for a bound track must not bring the tag back.
        self.mine = {t: n for t, n in self.mine.items() if n != named["name"]}
        self.named = self.things.labels()
        return f"Done. I have forgotten your {named['name']}."

    def named_evidence(self, turn: Turn, named: dict, this: bool = False
                       ) -> tuple[list[str], int | None, int, str]:
        """Retrieval for a question about the visitor's object `named`: evidence lines (what
        it looks like, when it was named, each object in view with its score, its latest
        matched sightings), the track in view that matches it at MATCH or above (None: no
        claim), how many tracks of its kind are in view, and when it was last seen ("20
        seconds ago"). Every object in view is scored, whatever its label; `this`: only the
        one nearest the center. Sets turn.memories to the evidence ids."""
        name = named["name"]
        with self.detecting:
            frame, view = self.view
            here = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        found = {t: box for t, (label, box) in view.items() if label != "person"}  # any label
        if this:
            found = {t: found[t] for t in [_central(found, frame.shape[1])] if t}
        scores = {t: self._score(named, v) for t, v in zip(
            found, self.crops([cut(frame, b) for b in found.values()]) if found else [],
            strict=True)}
        mine = max(scores, key=scores.__getitem__, default=None)
        mine = mine if mine is not None and scores[mine] >= MATCH else None
        past = self.memory.sightings(turn.speech_start, 3, here, named=[name])
        turns = self.memory.points(named["turns"])
        turn.memories = [t["id"] for t in turns] + [s["id"] for s in past] + (
            [self.points[mine]] if mine in self.points else [])
        ago = lambda ts: brain.age(turn.speech_start - ts)  # noqa: E731
        looks = next((x for t in turns if (x := main_object(t.get("caption", "")))), name)
        lines = [f"The visitor's {name}: {looks}" + (
            f", named {ago(turns[-1]['ts'])}" if turns else "")] + [
            f"In view now: {view[t][0]}, match {scores[t]:.2f} (needs {MATCH})" for t in found] + [
            f"Matched sighting: {x['label']}, last seen {ago(x['last_seen'])}" for x in past]
        last = ago(past[0]["last_seen"]) if past else ago(turns[-1]["ts"]) if turns else ""
        return lines, mine, sum(view[t][0] in named["labels"] for t in found), last

    def _score(self, named: dict, v: np.ndarray) -> float:
        """A crop vector's MaxSim score against the requested object `named`."""
        hit = self.things.score(v, named["name"])
        return hit[1] if hit else 0.0

    def _mine(self, turn: Turn, mode: str, named: dict) -> str:
        """A minimal code answer from named_evidence until those lines go to the brain."""
        name = named["name"]
        _, mine, found, last = self.named_evidence(turn, named, mode == "this")
        if mode == "this":
            return (f"I don't see {article(name)} right now." if not found else
                    f"Yes, this is your {name}." if mine is not None else
                    f"No, I don't think this is your {name}.")
        said = f"Yes, I remember your {name}. " * (mode == "remember")
        if mine is not None:
            return said + f"Yes, your {name} is here now."
        if found:
            return said + f"I see {article(name)}, but I am not sure it is yours."
        return said + (f"I last saw your {name} {last}; I don't see it now." if last else
                       f"I don't see your {name} now.")

    def _recall(self, turn: Turn, frame: np.ndarray) -> tuple[list[dict], list[str]]:
        """Captioned frames (newest first) and the Memories lines, oldest first: captions and
        sightings. What is in view now is the present, not something seen before."""
        recalled = [{**m, "caption": unmention(m["caption"], self.ignored)}
                    for m in self.memory.recent(before=turn.speech_start)
                    if np.abs(m["thumb"] - thumb(frame).astype(np.float32)).mean() > SCENE_CHANGE]
        with self.detecting:  # a consistent snapshot of the tracks
            in_view = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        sights = self.memory.sightings(before=turn.speech_start, hide=in_view, skip=self.ignored)
        turn.memories = [m["id"] for m in recalled + sights]
        ago = lambda ts: brain.age(turn.speech_start - ts)  # noqa: E731
        lines = sorted([(m["ts"], f"{ago(m['ts'])}: {m['caption']}") for m in recalled[::-1]] + [
            (s["last_seen"], f"{ago(s['last_seen'])}: {s['label']} {WHERE[s['region']]}")
            for s in sights], key=lambda x: x[0])
        return recalled, [f"{k}. {line}" for k, (_, line) in enumerate(lines, 1)]

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
        past = self.memory.sightings(turn.speech_start, SIGHTINGS, here, self.ignored, **query[1])
        now = [p for p in self.memory.points(here) if p["label"] not in self.ignored]
        if found := sighting_answer(*query, past, now,
                                    lambda ts: brain.age(turn.speech_start - ts)):
            answer, turn.memories = found
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
        self.jobs.join()           # the last turns and the captions they queue
        self.jobs.put(None)
        work.join()
        self.speaker.close()  # let the last phrase finish playing
        self.memory.shard.close()
        self.people.shard.close()
        self.things.shard.close()
        self.knowledge.shard.close()
        self.brain.close()


def main() -> None:
    from robot.camera import Camera
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--speaker", help="ALSA playback device")
    p.add_argument("--listen", type=int, help="TCP port for a Mac client (tools/talk.py)")
    a = p.parse_args()
    chunks, play = audio.mic(), audio.aplay(a.speaker, RATE) if a.speaker else None
    if a.listen:
        print(f"waiting for a client on port {a.listen}", flush=True)
        chunks, play = audio.serve(a.listen)
    robot = Robot(Camera(), SHARED / "sessions" / time.strftime("%Y%m%d-%H%M%S"), play=play)
    print("listening", flush=True)
    for chunk in chunks:
        robot.hear(chunk)
        if robot.detect_failed:
            raise RuntimeError("detection stopped") from robot.detect_failed
    robot.close()


if __name__ == "__main__":
    main()
