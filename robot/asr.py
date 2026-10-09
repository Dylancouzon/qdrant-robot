"""Speech in. Silero VAD (CPU) finds where a visitor's line starts and ends: the start lets the
brain prefill early, the end hands the line's audio to Parakeet TDT 0.6B v2 (int8, CPU), which
writes the transcript: 0.8% WER on dev fixtures in 0.22 s p50 (D24).
"""
import re
import time
from collections import deque
from collections.abc import Callable

import numpy as np
import onnx_asr
import onnxruntime as ort

from robot.config import MODELS

RATE = 16000
FRAME = 512                  # Silero's frame at 16 kHz (32 ms), after 64 samples of context
CONTEXT = 64
START_P, END_P = 0.5, 0.35   # speech starts above START_P, ends below END_P (hysteresis)
START_FRAMES = 2             # voiced frames in a row before a line starts (64 ms)
HANGOVER_S = 0.35            # silence that ends a line; mid-sentence pauses are shorter
LONG_S, LONG_HANGOVER_S = 4.0, 0.7  # long questions pause longer (0.58 s in dev, D37)
MIN_SPEECH_S = 0.25          # shorter lines are noise
MAX_LINE_S = 25.0            # under BUFFER_S; a 16 s fixture question split at 15 s
PAD_S = 0.2                  # audio kept before and after a line, so edge words are whole
BUFFER_S = 30
THREADS = 4                  # Parakeet's share of the six cores
# Names the acoustic model spells by sound. Visitors say "quadrant".
_QDRANT = r"(?:quadranth?|q ?drant|cue ?drant|kudrant)"
_FIXES = [(re.compile(rf"\b(?:{_QDRANT}|quadr[aeiou]n\w*?)(?:age|ed?ge)\b", re.I),
           "Qdrant Edge"),  # "quadrantage", "quadrundage"
          (re.compile(rf"\b{_QDRANT}s?\b", re.I), "Qdrant"),
          (re.compile(r"\bmulti[ -]vector", re.I), "multivector")]  # the knowledge phrasing
# The wake phrase (D65): "hey", "hi", or "okay", then the name as Parakeet spells it on
# synthetic voices (eval/dev/wake.jsonl: Edgie, Eji, Aji, Achie; "Hiyaji" for "Hi Edgy").
# Never the name alone: "edgy" is a word, and "edge" is said all day at the booth.
_WAKE = re.compile(r"^\W*(?:(?:hey|hi|hiya|okay|ok)\W+(?:edgy|edgie|edgey|eji|aji|achie)|hiyaji)"
                   r"\b\W*", re.I)


def normalize(text: str) -> str:
    for pattern, name in _FIXES:
        text = pattern.sub(name, text)
    return text.strip()


def woken(text: str) -> str | None:
    """`text` without its leading wake phrase, or None when it starts with none."""
    return text[m.end():] if (m := _WAKE.match(text)) else None


class Scribe:
    """Final transcript of one line of speech, on the CPU while the GPU prefills the frame."""

    def __init__(self):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = THREADS
        opts.enable_cpu_mem_arena = False  # each input length would otherwise grow the arena
        opts.add_session_config_entry("session.disable_prepacking", "1")  # one copy of weights
        self.model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", MODELS / "parakeet-v2",
                                         quantization="int8", providers=["CPUExecutionProvider"],
                                         sess_options=opts)
        self.model.recognize(np.zeros(RATE, np.float32))  # warm up

    def __call__(self, audio: np.ndarray) -> str:
        return normalize(self.model.recognize(audio))


class Vad:
    """Silero VAD: speech probability per 32 ms frame, with its recurrent state."""

    def __init__(self):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        self.sess = ort.InferenceSession(str(MODELS / "silero/silero_vad.onnx"), opts,
                                         providers=["CPUExecutionProvider"])
        self.state = np.zeros((2, 1, 128), np.float32)
        self.context = np.zeros(CONTEXT, np.float32)
        self.sr = np.array(RATE, np.int64)

    def __call__(self, frame: np.ndarray) -> float:
        x = np.concatenate([self.context, frame])[None]
        p, self.state = self.sess.run(None, {"input": x, "state": self.state, "sr": self.sr})
        self.context = frame[-CONTEXT:]
        return float(p[0, 0])


class Ears:
    def __init__(self, on_start: Callable[[], None], on_line: Callable[[np.ndarray, float], None]):
        """on_start(): a line began. on_line(audio, speech_end): the line's audio (padded) and
        the wall time its speech ended, mapped through each chunk's arrival time."""
        self.on_start, self.on_line = on_start, on_line
        self.vad = Vad()
        self.fed = 0                                   # samples so far
        self.buffer = np.zeros(BUFFER_S * RATE, np.float32)  # the newest audio, oldest first
        self.arrivals: deque[tuple[int, float]] = deque(maxlen=2000)  # (end sample, wall)
        self.pending = np.zeros(0, np.float32)         # samples not yet in a VAD frame
        self.voiced = 0                                # voiced frames in a row, before a line
        self.start: int | None = None                  # first sample of the current line
        self.silence = 0                               # trailing silent samples in the line

    def feed(self, chunk: np.ndarray) -> None:
        """16 kHz mono float32 audio, in order, at any chunk size."""
        self.keep(chunk)
        self.arrivals.append((self.fed, time.time()))
        self.pending = np.concatenate([self.pending, chunk])
        while len(self.pending) >= FRAME:
            frame, self.pending = self.pending[:FRAME], self.pending[FRAME:]
            self.step(self.vad(frame), self.fed - len(self.pending))

    def step(self, p: float, end: int) -> None:
        """Advance the line state with the probability of the frame ending at sample `end`."""
        if self.start is None:
            self.voiced = self.voiced + 1 if p >= START_P else 0
            if self.voiced >= START_FRAMES:
                self.start, self.silence = end - START_FRAMES * FRAME, 0
                self.on_start()
            return
        self.silence = self.silence + FRAME if p < END_P else 0
        speech_end = end - self.silence
        hangover = LONG_HANGOVER_S if speech_end - self.start > LONG_S * RATE else HANGOVER_S
        if self.silence >= hangover * RATE or end - self.start >= MAX_LINE_S * RATE:
            start, self.start, self.voiced = self.start, None, 0
            if speech_end - start >= MIN_SPEECH_S * RATE:
                pad = int(PAD_S * RATE)
                self.on_line(self.cut(start - pad, speech_end + pad), self.wall(speech_end))

    def keep(self, chunk: np.ndarray) -> None:
        self.fed += len(chunk)
        self.buffer = np.roll(self.buffer, -len(chunk))
        self.buffer[-len(chunk):] = chunk

    def cut(self, start: float, end: float) -> np.ndarray:
        """Stream samples [start, end) still in the buffer."""
        first = self.fed - len(self.buffer)
        a, b = max(int(start), first, 0) - first, min(int(end), self.fed) - first
        return self.buffer[a:b].copy()

    def wall(self, sample: float) -> float:
        """Wall time at which a stream sample arrived (live audio arrives as it is spoken)."""
        for end, t in self.arrivals:
            if end >= sample:
                return t - (end - sample) / RATE
        return time.time()


if __name__ == "__main__":
    assert normalize("What is quadrant edge?") == "What is Qdrant edge?"
    assert normalize("a quadrangle") == "a quadrangle"
    assert normalize("What is quadrantage?") == "What is Qdrant Edge?"
    assert normalize("What is quadrundage?") == "What is Qdrant Edge?"
    assert normalize("quadrant edge") == "Qdrant edge"
    assert normalize("What is Quadranth Edge?") == "What is Qdrant Edge?"
    assert normalize("What is a multi vector?") == "What is a multivector?"
    assert woken("Hey Edgie, what do you see?") == "what do you see?"
    assert woken("Hiyaji, do you remember me?") == "do you remember me?"
    assert woken("okay edgy") == "" and woken("Hey Eji what did I show you?") is not None
    for other in ("Edgy, what do you see?", "Qdrant Edge is fast.", "Hey, that edge is sharp.",
                  "That is edgy.", "Hey Eddie, come here.", "Hey Edge, hi."):
        assert woken(other) is None, other
    ears = object.__new__(Ears)  # only the buffer and line logic, without loading a model
    ears.fed, ears.buffer = 0, np.zeros(4, np.float32)
    ears.keep(np.array([1, 2, 3], np.float32))
    ears.keep(np.array([4, 5, 6], np.float32))
    assert ears.cut(2, 5).tolist() == [3, 4, 5] and ears.cut(0, 9).tolist() == [3, 4, 5, 6]
    events: list = []
    ears.on_start, ears.on_line = lambda: events.append("start"), lambda a, t: events.append(t)
    ears.voiced, ears.start, ears.silence = 0, None, 0
    ears.fed, ears.buffer = RATE * 4, np.zeros(RATE * 4, np.float32)
    ears.arrivals = deque([(RATE * 4, 100.0)])
    for k, p in enumerate([0.9] * 20 + [0.1] * 12, 1):  # 0.64 s of speech, 0.38 s of silence
        ears.step(p, k * FRAME)
    assert events[0] == "start" and len(events) == 2, events
    assert abs(events[1] - (100.0 - (RATE * 4 - 20 * FRAME) / RATE)) < 1e-6, "speech end time"
    for voiced, pause in ((130, 18), (520, 0)):  # a 0.58 s pause after 4 s; a 16.6 s line
        events.clear()
        ps = [0.9] * voiced + [0.1] * pause + [0.9] * 5 + [0.1] * 22
        for k, p in enumerate(ps, 1):
            ears.step(p, k * FRAME)
        assert events[0] == "start" and len(events) == 2, (voiced, events)
    print("selftest ok")
