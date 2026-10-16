"""The self-voice and mute gate on Robot.hear, and the speaker volume control."""
import queue
import subprocess
import threading
import time
from types import SimpleNamespace as Stub

import numpy as np
import pytest

from robot import audio
from robot.main import Robot
from robot.head import Head

LOUD = np.full(4, 0.5, np.float32)
PHRASE = np.zeros(10, np.float32)
TAIL = 0.2


def gated_robot(sink) -> tuple[Robot, list]:
    fed, r = [], Robot.__new__(Robot)
    r.worker_failed, r.detect_failed, r.head = None, None, Head()
    r.ears, r.muted, r.speaker = Stub(feed=fed.append), False, audio.Mouth(sink)
    return r, fed


def test_gate_stays_closed_until_the_last_delayed_phrase_returns_plus_the_tail(monkeypatch) -> None:
    monkeypatch.setattr(audio, "SELF_VOICE_TAIL_S", TAIL)
    returns: queue.Queue = queue.Queue()
    done = threading.Semaphore(0)

    def sink(_):
        returns.get()  # the phrase is audible until the test lets it return
        done.release()

    r, fed = gated_robot(sink)
    for _ in range(3):
        r.speaker.play(PHRASE)
    for _ in range(2):  # the first two phrases end; the third is still playing
        returns.put(None)
        done.acquire()
        r.hear(LOUD)
    returns.put(None)
    r.speaker.q.join()
    r.hear(LOUD)  # inside the tail after the last sink call
    time.sleep(TAIL + 0.05)
    r.hear(LOUD)
    assert [bool(c.any()) for c in fed] == [False, False, False, True]
    r.speaker.close()


def test_failing_sink_reopens_the_gate_and_the_next_phrase_plays(monkeypatch) -> None:
    monkeypatch.setattr(audio, "SELF_VOICE_TAIL_S", TAIL)
    calls = []

    def sink(_):
        calls.append(1)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, "aplay")

    r, fed = gated_robot(sink)
    r.speaker.play(PHRASE)
    r.speaker.play(PHRASE)
    r.speaker.q.join()
    time.sleep(TAIL + 0.05)
    r.hear(LOUD)
    assert len(calls) == 2 and fed[0].any()
    r.speaker.close()


def test_mute_silences_input() -> None:
    r, fed = gated_robot(None)
    r.muted = True
    r.hear(LOUD)
    r.muted = False
    r.hear(LOUD)
    assert [bool(c.any()) for c in fed] == [False, True]
    r.speaker.close()


def test_volume_is_validated_saved_and_applied(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(audio, "VOLUME_FILE", tmp_path / "volume")
    monkeypatch.setattr(subprocess, "run", lambda args, **_: calls.append(args))
    assert audio.saved_volume() == audio.DEFAULT_VOLUME
    for bad in (-1, 101, 50.5, "50", True, None):
        with pytest.raises(ValueError):
            audio.set_volume(bad)
    assert not calls and not (tmp_path / "volume").exists()
    audio.set_volume(40)
    assert calls[0][-3:] == ["sset", "Speaker", "40%"] and audio.saved_volume() == 40


@pytest.mark.parametrize("saved", ["300", "-5", "loud", ""])
def test_unusable_saved_volume_falls_back_to_the_default(tmp_path, monkeypatch, saved) -> None:
    monkeypatch.setattr(audio, "VOLUME_FILE", tmp_path / "volume")
    (tmp_path / "volume").write_text(saved)
    assert audio.saved_volume() == audio.DEFAULT_VOLUME


def test_control_endpoint_sets_mute_and_volume(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audio, "VOLUME_FILE", tmp_path / "volume")
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: None)
    r = Robot.__new__(Robot)
    r.muted, r.volume, r.volume_lock = False, 62, threading.Lock()
    r.detecting, r.control_message = threading.Lock(), ""
    assert r._control("mute", {"on": True}) and r.muted
    assert not r._control("mute", {"on": "yes"}) and r.muted
    assert r._control("volume", {"percent": 30}) and r.volume == 30
    assert not r._control("volume", {"percent": 300}) and r.volume == 30
    monkeypatch.setattr(audio, "VOLUME_FILE", tmp_path / "missing" / "volume")
    assert not r._control("volume", {"percent": 20}) and r.volume == 20
    assert "set to 20% but not saved" in r.control_message
