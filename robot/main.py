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
import queue
import threading
import time
import traceback
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from robot import audio, brain
from robot.asr import Ears, Scribe
from robot.config import SHARED
from robot.detect import Detector, Sighting, Tracker
from robot.knowledge import VERBATIM, Knowledge
from robot.memory import (
    Memory,
    about_now,
    about_past,
    is_question,
    shown,
    sighting_answer,
    sighting_query,
    thumb,
)
from robot.route import Router
from robot.text_embed import TextEmbedder
from robot.tts import RATE, Speaker, phrases

HISTORY_TURNS = 4  # the conversation window, in exchanges
WATCH_S = 0.3      # how often idle time checks whether the prefilled frame is stale
SCENE_CHANGE = 8.0  # mean absolute difference (0-255) of 64x36 grey thumbnails
# Camera rate: unthrottled detection halved LLM decode (research/detector.md).
DETECT_FPS = 15
DETECT_RESTARTS = 3  # detector failures it recovers from by reloading; the next one stops it
SIGHTINGS = 64  # the newest out-of-view sightings a sighting answer groups
WHERE = {"left": "on your left", "center": "in the center", "right": "on your right"}


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


class Robot:
    def __init__(self, camera, out: Path, memory: Path = SHARED / "memory",
                 play: Callable[[np.ndarray], None] | None = None, model: str = brain.MODEL):
        self.camera, self.out = camera, out
        out.mkdir(parents=True, exist_ok=True)
        self.knowledge, self.memory, self.embed = Knowledge(), Memory(memory), TextEmbedder()
        self.scribe = Scribe()
        self.route = Router(self.embed)
        self.voice = Speaker()
        self.speaker = audio.Mouth(play)
        self.brain = brain.Brain(model)
        self.detect, self.tracker = Detector(), Tracker()
        self.vocab = set(self.detect.names.values())  # the labels the detector can give
        self.points: dict[int, int] = {}  # track id -> its sighting point, while it is tracked
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
            self.memory, self.history, self.exchanges, self.ready = Memory(memory), [], 0, None
            self.last_frame, self.points, self.tracker = None, {}, Tracker()

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
                with self.detecting:
                    found = self.tracker.update(self.detect(frame), frame.shape[1], time.time())
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

    def _sight(self, found: list[Sighting], frame: np.ndarray) -> None:
        """One point per track: stored when confirmed, updated when it moves region (with the
        new source frame) and when it leaves."""
        jpg = None
        for s in found:
            pid = self.points.pop(s.track, None) if s.gone else self.points.get(s.track)
            if s.gone:
                if pid:
                    self.memory.set(pid, last_seen=s.seen)
                continue
            jpg = jpg or self.memory.save(frame)
            if pid:
                self.memory.set(pid, region=s.region, last_seen=s.seen, frame=jpg)
            else:
                self.points[s.track] = self.memory.sighting(s.label, s.region, s.seen, jpg)

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
        look of the same scene; the frame used is the one stored as evidence."""
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
        statements = self.memory.told(question, before=turn.speech_start)
        turn.told = [m["said"] for m in statements]
        told = [f"{brain.age(turn.speech_start - m['ts'])}: {m['said']}" for m in statements]
        recalled_answer = shown(turn.question, recalled,
                                lambda m: brain.age(turn.speech_start - m["ts"])
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
        audio_parts = list(self._speak(phrases(tokens), turn))
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
        pid = turn.frame_id = self.memory.add(look.frame, turn.question, statement, look.taken)
        for job in [*self.uncaptioned, (pid, look.image)]:
            self.jobs.put(("caption", *job))
        self.uncaptioned = []
        with (self.out / "turns.jsonl").open("a") as f:
            f.write(json.dumps(asdict(turn)) + "\n")
        self.turns.put(turn)

    def _recall(self, turn: Turn, frame: np.ndarray) -> tuple[list[dict], list[str]]:
        """Captioned frames (newest first) and the Memories lines, oldest first: captions and
        sightings. What is in view now is the present, not something seen before."""
        recalled = [m for m in self.memory.recent(before=turn.speech_start)
                    if np.abs(m["thumb"] - thumb(frame).astype(np.float32)).mean() > SCENE_CHANGE]
        with self.detecting:  # a consistent snapshot of the tracks
            in_view = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        sights = self.memory.sightings(before=turn.speech_start, hide=in_view)
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
        with self.detecting:
            here = {self.points[t] for t in self.tracker.in_view() if t in self.points}
        # Enough tracks to group by kind and region before the answer limit (ponytail: a
        # window, not a group-by; Edge 0.8 has none. Facet on label if one kind floods it).
        past = self.memory.sightings(turn.speech_start, SIGHTINGS, here, **query[1])
        if found := sighting_answer(*query, past, self.memory.points(here),
                                    lambda ts: brain.age(turn.speech_start - ts)):
            answer, turn.memories = found
            return answer
        return None

    def _said(self, fact: str, turn: Turn) -> Iterator[str]:
        turn.first_token, turn.answer = time.time(), fact
        yield fact

    def _tokens(self, msgs: list[dict], turn: Turn) -> Iterator[str]:
        for delta in self.brain.answer(msgs):
            turn.first_token = turn.first_token or time.time()
            turn.answer += delta
            yield delta
        turn.answer = turn.answer.strip()

    def _speak(self, texts: Iterator[str], turn: Turn) -> Iterator[np.ndarray]:
        for text in texts:
            turn.first_phrase = turn.first_phrase or time.time()
            pcm = self.voice.say(text)
            turn.first_audio = turn.first_audio or time.time()
            self.speaker.play(pcm)
            yield pcm

    def close(self) -> None:
        """Finish the queued work, stop the threads, and release the shards and llama-server,
        so a new Robot can open the same memory folder (a restart)."""
        watch, detect, transcribe, work = self.threads
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
