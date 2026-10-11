"""The self-voice and mute gate on Robot.hear, and the speaker volume control."""
import subprocess
import time
from types import SimpleNamespace as Stub

import numpy as np
import pytest

from robot import audio
from robot.main import Robot

LOUD = np.full(4, 0.5, np.float32)


def robot(playing: bool) -> tuple[Robot, list]:
    fed, r = [], Robot.__new__(Robot)
    r.ears, r.muted = Stub(feed=fed.append), False
    r.speaker = audio.Mouth(lambda _: None, 10)
    if playing:
        r.speaker.play(np.zeros(10, np.float32))
    return r, fed


def test_input_is_silent_while_playing_and_in_the_tail_then_live() -> None:
    r, fed = robot(playing=True)
    r.hear(LOUD)  # playing
    r.speaker.until = time.monotonic() - audio.SELF_VOICE_TAIL_S / 2
    r.hear(LOUD)  # in the tail
    r.speaker.until = time.monotonic() - audio.SELF_VOICE_TAIL_S - 0.01
    r.hear(LOUD)  # after the tail
    assert [bool(c.any()) for c in fed] == [False, False, True]
    r.speaker.close()


def test_mute_silences_input() -> None:
    r, fed = robot(playing=False)
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


def test_control_endpoint_sets_mute_and_volume(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audio, "VOLUME_FILE", tmp_path / "volume")
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: None)
    r = Robot.__new__(Robot)
    r.muted, r.volume = False, 62
    assert r._control("mute", {"on": True}) and r.muted
    assert not r._control("mute", {"on": "yes"}) and r.muted
    assert r._control("volume", {"percent": 30}) and r.volume == 30
    assert not r._control("volume", {"percent": 300}) and r.volume == 30
