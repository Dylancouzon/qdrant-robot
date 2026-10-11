"""Audio in and out. In: the USB microphone through `arecord`, a Mac client over TCP
(`tools/talk.py --mac-audio`), or a WAV played at real-time pace for scripted sessions. Out:
phrases played in order on the USB speaker or sent back to the Mac client; every answer is
also saved as a WAV for scoring. The speaker volume is the USB `Speaker` mixer, saved in
`shared/`.
"""
import queue
import socket
import struct
import subprocess
import threading
import time
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

from robot.config import SHARED

RATE_IN = 16000
CHUNK_S = 0.08
# ALSA card "Device", the USB PnP Audio Device (JMTek 0c76:1203): the robot's microphone
# and speaker. It hears its own speaker at -17 dBFS, so input is silenced while speaking.
USB_AUDIO = "plughw:CARD=Device,DEV=0"
MIC, SPEAKER = USB_AUDIO, USB_AUDIO
SELF_VOICE_TAIL_S = 0.3  # calibration: room echo and device latency after the last phrase
VOLUME_FILE = SHARED / "speaker-volume"
DEFAULT_VOLUME = 62  # percent of the `Speaker` mixer


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


def saved_volume() -> int:
    try:
        return int(VOLUME_FILE.read_text())
    except (OSError, ValueError):
        return DEFAULT_VOLUME


def set_volume(percent: int) -> None:
    """Set the USB `Speaker` mixer to `percent` (0 to 100) and save it for the next start."""
    if type(percent) is not int or not 0 <= percent <= 100:
        raise ValueError(f"volume must be a whole percent from 0 to 100, got {percent!r}")
    subprocess.run(["amixer", "-q", "-c", "Device", "sset", "Speaker", f"{percent}%"], check=True)
    VOLUME_FILE.write_text(str(percent))


def pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()


def write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16(audio))


def aplay(device: str, rate: int) -> Callable[[np.ndarray], None]:
    def play(audio: np.ndarray) -> None:
        subprocess.run(["aplay", "-q", "-D", device, "-f", "S16_LE", "-r", str(rate), "-c", "1",
                        "-t", "raw"], input=pcm16(audio))
    return play


def serve(port: int) -> tuple[Iterator[np.ndarray], Callable[[np.ndarray], None]]:
    """Wait for one Mac client: its microphone in (int16, 16 kHz, mono), and a sender for
    answer audio out (each phrase: 4-byte little-endian length, then int16 samples)."""
    with socket.create_server(("0.0.0.0", port)) as server:
        conn, _ = server.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def chunks() -> Iterator[np.ndarray]:
        step = int(RATE_IN * CHUNK_S) * 2
        with conn.makefile("rb") as f:
            while data := f.read(step):
                yield np.frombuffer(data, np.int16).astype(np.float32) / 32768

    def send(audio: np.ndarray) -> None:
        pcm = pcm16(audio)
        conn.sendall(struct.pack("<I", len(pcm)) + pcm)
    return chunks(), send


class Mouth:
    """Plays phrases in order through `play` (None: no speaker); the turn keeps the audio.
    `until` is when the queued audio ends, from its sample count: `play` returns once the
    data is written, which is before it is audible."""

    def __init__(self, play: Callable[[np.ndarray], None] | None, rate: int):
        self.sink, self.rate, self.until = play, rate, 0.0
        self.q: queue.Queue[np.ndarray | None] = queue.Queue()
        self.thread = threading.Thread(target=self._run, name="mouth", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while (audio := self.q.get()) is not None:  # None: close() stops the thread
            if self.sink:
                self.sink(audio)
            self.q.task_done()
        self.q.task_done()

    def play(self, audio: np.ndarray) -> None:
        if self.sink:
            self.until = max(self.until, time.monotonic()) + len(audio) / self.rate
        self.q.put(audio)

    def playing(self, tail: float = 0.0) -> bool:
        """Audio is playing, or ended less than `tail` seconds ago."""
        return time.monotonic() < self.until + tail

    def close(self) -> None:
        """Play what is queued, then stop."""
        self.q.put(None)
        self.thread.join()


if __name__ == "__main__":
    import contextlib
    with contextlib.closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    mouth = Mouth(lambda _: None, 10)
    assert not mouth.playing(SELF_VOICE_TAIL_S)
    mouth.play(np.zeros(5, np.float32))  # 0.5 s of audio
    assert mouth.playing() and not Mouth(None, 10).playing(), "playing, and no speaker"
    mouth.until = time.monotonic() - 0.1
    assert not mouth.playing() and mouth.playing(SELF_VOICE_TAIL_S), "the tail follows the end"
    mouth.close()
    got: list = []
    t = threading.Thread(target=lambda: got.append(serve(port)))
    t.start()
    for _ in range(50):  # until the server listens
        with contextlib.suppress(OSError):
            client = socket.create_connection(("127.0.0.1", port))
            break
        time.sleep(0.05)
    t.join()
    chunks, send = got[0]
    client.sendall(np.full(int(RATE_IN * CHUNK_S), 16384, np.int16).tobytes())
    assert abs(next(chunks)[0] - 0.5) < 1e-6, "microphone chunk in"
    send(np.array([0.5, -0.5], np.float32))
    head = client.recv(4)
    assert struct.unpack("<I", head)[0] == 4 and len(client.recv(4)) == 4, "answer phrase out"
    print("selftest ok")
