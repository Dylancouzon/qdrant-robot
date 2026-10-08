"""Audio in and out. In: the camera's microphone through `arecord`, or a WAV played at
real-time pace for scripted sessions. Out: phrases played in order on an ALSA device when one
exists, and always saved as one WAV per answer for scoring.
"""
import queue
import subprocess
import threading
import time
import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np

RATE_IN = 16000
CHUNK_S = 0.08
MIC = "plughw:CARD=Light,DEV=0"  # the Arducam's microphone


def mic() -> Iterator[np.ndarray]:
    step = int(RATE_IN * CHUNK_S) * 2
    with subprocess.Popen(["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", str(RATE_IN),
                           "-c", "1", "-t", "raw"], stdout=subprocess.PIPE) as p:
        while chunk := p.stdout.read(step):
            yield np.frombuffer(chunk, np.int16).astype(np.float32) / 32768


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == RATE_IN and w.getnchannels() == 1, path
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def paced(audio: np.ndarray, silence_s: float = 0.0) -> Iterator[np.ndarray]:
    """Chunks of audio, then silence, released at real-time pace like a microphone."""
    audio = np.concatenate([audio, np.zeros(int(RATE_IN * silence_s), np.float32)])
    step = int(RATE_IN * CHUNK_S)
    t0 = time.perf_counter()
    for k in range(0, len(audio), step):
        time.sleep(max(0.0, t0 + k / RATE_IN - time.perf_counter()))
        yield audio[k:k + step]


def write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


class Mouth:
    """Plays phrases in order on `device` (None: no speaker) and keeps each answer's audio."""

    def __init__(self, rate: int, device: str | None = None):
        self.rate, self.device = rate, device
        self.q: queue.Queue[np.ndarray] = queue.Queue()
        threading.Thread(target=self._run, name="mouth", daemon=True).start()

    def _run(self) -> None:
        while True:
            audio = self.q.get()
            if self.device:
                pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
                subprocess.run(["aplay", "-q", "-D", self.device, "-f", "S16_LE", "-r",
                                str(self.rate), "-c", "1", "-t", "raw"], input=pcm)
            self.q.task_done()

    def play(self, audio: np.ndarray) -> None:
        self.q.put(audio)
