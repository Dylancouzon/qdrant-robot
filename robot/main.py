"""The robot: hears a line, looks, recalls, answers aloud. One process; the LLM runs in a
supervised llama-server child. Every turn logs its stage times and saves its answer audio.

    python -m robot.main                       camera, camera microphone, no speaker
    python -m robot.main --speaker plughw:1,0  ... and an ALSA speaker
    python -m robot.main --listen 7070         microphone and speaker of a Mac client
"""
import argparse
import json
import queue
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from robot import audio, brain
from robot.asr import Ears, Scribe
from robot.config import SHARED
from robot.knowledge import VERBATIM, Knowledge
from robot.memory import Memory, about_now, about_past, is_question, shown, thumb
from robot.route import Router
from robot.text_embed import TextEmbedder
from robot.tts import RATE, Speaker, phrases

HISTORY_TURNS = 4  # the conversation window, in exchanges
WATCH_S = 0.3      # how often idle time checks whether the prefilled frame is stale
SCENE_CHANGE = 8.0  # mean absolute difference (0-255) of 64x36 grey thumbnails


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
        for target in (self._work, self._transcribe, self._watch):
            threading.Thread(target=target, name=target.__name__, daemon=True).start()
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
        """Start over with an empty memory and conversation (scripted sessions)."""
        self.jobs.join()
        self.memory.shard.close()
        self.memory, self.history, self.exchanges, self.ready = Memory(memory), [], 0, None
        self.last_frame = None

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
        while True:
            speech, t_line, speech_end, speech_start, shot = self.lines.get()
            if text := self.scribe(speech):  # empty: noise the VAD took for speech
                self.asked += 1
                self.jobs.put(("turn", Turn(question=text, line=t_line,
                                            transcribed=time.time(), speech_end=speech_end,
                                            speech_start=speech_start), shot))
            self.lines.task_done()

    def _watch(self) -> None:
        # Keep a recent frame prefilled while nobody speaks, so a turn rarely waits for one.
        while True:
            time.sleep(WATCH_S)
            shot = self.camera.latest()
            if not self.speaking and self.jobs.empty() and self._stale(shot[0]):
                self.jobs.put(("look", shot))

    def _stale(self, frame: np.ndarray | None) -> bool:
        """The prefilled look no longer matches `frame` or the conversation."""
        return frame is not None and (self.ready is None or self.ready.exchanges != self.exchanges
                                      or scene_change(self.ready.frame, frame) > SCENE_CHANGE)

    def _work(self) -> None:
        # One worker: llama-server jobs run in order, and a turn reuses the last look.
        while True:
            job = self.jobs.get()
            if job[0] == "look":
                self._look(job[1])
            elif job[0] == "turn":
                self._turn(*job[1:])
            elif (caption := self.brain.caption(job[2], lambda: self.speaking)) is None:
                self.uncaptioned.append(job[1:])  # a visitor spoke: retry after their turn
            else:
                self.memory.caption(job[1], caption)
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
        question = self.embed([turn.question])[0]
        found = self.knowledge.search(question)
        turn.facts = [fact for _, fact in found]
        turn.verbatim = bool(found) and found[0][0] >= VERBATIM
        past = about_past(turn.question)
        # Memories of the scene in view now are the present, not something shown before.
        recalled = [m for m in self.memory.recent(before=turn.speech_start)
                    if np.abs(m["thumb"] - thumb(look.frame).astype(np.float32)).mean()
                    > SCENE_CHANGE] if past else []
        turn.memories = [m["id"] for m in recalled]
        memories = [f"{k}. {brain.age(turn.speech_start - m['ts'])}: {m['caption']}"
                    for k, m in enumerate(reversed(recalled), 1)]  # oldest first
        statements = self.memory.told(question, before=turn.speech_start)
        turn.told = [m["said"] for m in statements]
        told = [f"{brain.age(turn.speech_start - m['ts'])}: {m['said']}" for m in statements]
        recalled_answer = shown(turn.question, recalled,
                                lambda m: brain.age(turn.speech_start - m["ts"]))
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
        self.jobs.join()
        self.speaker.q.join()  # let the last phrase finish playing
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
    robot.close()


if __name__ == "__main__":
    main()
