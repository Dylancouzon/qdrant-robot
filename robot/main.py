"""The robot: hears a line, looks, recalls, answers aloud. One process; the LLM runs in a
supervised llama-server child. Every turn logs its stage times and saves its answer audio.

    python -m robot.main            live: camera, camera microphone, speaker if any
"""
import json
import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

from robot import audio, brain
from robot.asr import Ears, Scribe
from robot.config import SHARED
from robot.knowledge import Knowledge
from robot.memory import Seen
from robot.text_embed import TextEmbedder
from robot.tts import RATE, Speaker, phrases

HISTORY_TURNS = 4  # the conversation window, in exchanges
WATCH_S = 0.3      # how often idle time checks whether the prefilled frame is stale
SCENE_CHANGE = 8.0  # mean absolute difference (0-255) of 64x36 grey thumbnails


def scene_change(a: np.ndarray, b: np.ndarray) -> float:
    def thumb(f: np.ndarray) -> np.ndarray:
        return cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (64, 36)).astype(np.float32)
    return float(np.abs(thumb(a) - thumb(b)).mean())


@dataclass
class Look:
    """A frame whose prompt prefix, after `exchanges` exchanges, is in the brain's KV cache."""
    frame: np.ndarray
    taken: float                  # capture time: the evidence time of what the brain saw
    image: dict
    exchanges: int


@dataclass
class Turn:
    """One exchange, with wall-clock stage times (time.time())."""
    question: str = ""
    answer: str = ""
    facts: list[str] = field(default_factory=list)
    memories: list[int] = field(default_factory=list)  # evidence: ids of the frames recalled
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
                 speaker_device: str | None = None, model: str = brain.MODEL):
        self.camera, self.out = camera, out
        out.mkdir(parents=True, exist_ok=True)
        self.knowledge, self.seen, self.embed = Knowledge(), Seen(memory), TextEmbedder()
        self.scribe = Scribe()
        self.voice = Speaker()
        self.speaker = audio.Mouth(RATE, speaker_device)
        self.brain = brain.Brain(model)
        self.history: list[dict] = []
        self.exchanges = 0                      # counts every exchange; history is capped
        self.jobs: queue.Queue = queue.Queue()  # GPU work for llama-server, in order
        self.lines: queue.Queue = queue.Queue()  # finished lines for the final transcript
        self.turns: queue.Queue[Turn] = queue.Queue()  # finished turns, for replay and logs
        self.ready: Look | None = None          # the frame whose prompt prefix is prefilled
        self.speaking = False                   # a visitor is mid-line: background work yields
        self.speech_start = 0.0
        self.start_frame: tuple[np.ndarray | None, float] = (None, 0.0)  # frame, capture time
        self.uncaptioned: list[tuple[int, list[dict]]] = []  # (frame id, prompt prefix)
        for target in (self._work, self._transcribe, self._watch):
            threading.Thread(target=target, name=target.__name__, daemon=True).start()
        self.ears = Ears(self._heard_start, self._heard_line)

    def hear(self, chunk: np.ndarray) -> None:
        self.ears.feed(chunk)

    def reset(self, memory: Path) -> None:
        """Start over with an empty memory and conversation (scripted sessions)."""
        self.jobs.join()
        self.seen.shard.close()
        self.seen, self.history, self.exchanges, self.ready = Seen(memory), [], 0, None

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
            if not (text := self.scribe(speech)):
                continue  # noise the VAD took for speech
            self.jobs.put(("turn", Turn(question=text, line=t_line,
                                        transcribed=time.time(), speech_end=speech_end,
                                        speech_start=speech_start), shot))

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
                self.seen.caption(job[1], caption)
            self.jobs.task_done()

    def _look(self, shot: tuple[np.ndarray, float]) -> None:
        look = Look(shot[0], shot[1], brain.jpeg(shot[0]), self.exchanges)
        self.brain.prefill(brain.messages(self.history, look.image))
        self.ready = look

    def _turn(self, turn: Turn, shot: tuple[np.ndarray | None, float]) -> None:
        """Answer about the frame shown when this line's speech started, or about an earlier
        look of the same scene; the frame used is the one stored as evidence."""
        if self._stale(shot[0]):  # the scene changed after the last look
            self._look(shot)
        if (look := self.ready) is None:
            return  # no camera frame yet: nothing to answer about
        turn.facts = [fact for _, fact in self.knowledge.search(self.embed([turn.question])[0])]
        recalled = self.seen.recent(before=turn.speech_start)
        turn.memories = [m["id"] for m in recalled]
        memories = [f"{brain.age(turn.speech_start - m['ts'])}: {m['caption']}"
                    for m in recalled]
        turn.retrieved = time.time()
        prefix = brain.messages(self.history, look.image)
        msgs = brain.messages(self.history, look.image, memories, turn.facts, turn.question)
        audio_parts = list(self._speak(phrases(self._tokens(msgs, turn)), turn))
        turn.done = time.time()
        turn.wav = f"{int(turn.line * 1000)}.wav"
        spoken = np.concatenate(audio_parts or [np.zeros(1)])
        turn.audio_s = len(spoken) / RATE
        audio.write_wav(self.out / turn.wav, spoken, RATE)
        self.history = (self.history + [{"role": "user", "content": turn.question},
                                        {"role": "assistant", "content": turn.answer}]
                        )[-2 * HISTORY_TURNS:]
        self.exchanges += 1
        pid = turn.frame_id = self.seen.add(look.frame, turn.question, ts=look.taken)
        for job in [*self.uncaptioned, (pid, prefix)]:
            self.jobs.put(("caption", *job))
        self.uncaptioned = []
        with (self.out / "turns.jsonl").open("a") as f:
            f.write(json.dumps(asdict(turn)) + "\n")
        self.turns.put(turn)

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
        self.seen.shard.close()
        self.knowledge.shard.close()
        self.brain.close()


def main() -> None:
    from robot.camera import Camera
    robot = Robot(Camera(), SHARED / "sessions" / time.strftime("%Y%m%d-%H%M%S"))
    print("listening", flush=True)
    for chunk in audio.mic():
        robot.hear(chunk)


if __name__ == "__main__":
    main()
