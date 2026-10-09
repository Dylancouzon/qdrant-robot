"""Keep missing, empty, and split synthesized outputs visible in speech verification."""

import json
import wave
from pathlib import Path

import pytest

from eval import speech


def test_continuous_speech_keeps_splits_and_missing_outputs():
    rows = [
        {"type": "metadata", "duration_s": 10},
        {"type": "utterance", "id": "a", "ok": False, "turns": []},
        {
            "type": "utterance",
            "id": "b",
            "ok": False,
            "turns": [
                {"answer": "first", "wav": "first.wav"},
                {"answer": "second", "wav": "second.wav"},
            ],
        },
        {
            "type": "completion",
            "completed": True,
            "worker_exit": 0,
            "utterance_ids": ["a", "b"],
            "audio_dir": "/run/audio",
        },
    ]
    answers, audio = speech.speech_rows(rows)
    assert [row["id"] for row in answers] == ["a", "b", "b"]
    assert not any(row["structural_ok"] for row in answers)
    assert answers[0]["wav"] is None and audio == "/run/audio"
    with pytest.raises(ValueError):
        speech.speech_rows(rows[:-1])


def test_missing_and_empty_wavs_fail_without_asr(tmp_path, monkeypatch):
    result = tmp_path / "run.jsonl"
    rows = [
        {"id": "missing", "wav": "absent.wav", "answer": "hello"},
        {"id": "empty", "wav": "empty.wav", "answer": "hello"},
        {"audio_dir": "/run/audio"},
    ]
    result.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def copy(args, **kwargs):
        assert kwargs["timeout"] == 120
        with wave.open(str(Path(args[-1]) / "empty.wav"), "wb") as wav:
            wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))

    def recognize(_):
        raise AssertionError("missing and empty audio must not reach ASR")

    monkeypatch.setattr(speech.subprocess, "run", copy)
    monkeypatch.setattr(speech, "Scribe", lambda: recognize)
    assert speech.main(result) == 1
    scored = [
        json.loads(line) for line in result.with_suffix(".speech.jsonl").read_text().splitlines()
    ]
    assert not any(row["pass"] for row in scored[:-1])
    assert scored[-1]["completed"] and scored[-1]["passed"] == 0
    assert scored[0]["wav_sha256"] is None and scored[1]["wav_sha256"] is not None


def test_incompatible_wav_rate_is_rejected(tmp_path):
    path = tmp_path / "wrong.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\0\0" * 32)
    with pytest.raises(ValueError, match="24 kHz"):
        speech.load_24k(path)
