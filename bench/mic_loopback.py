#!/usr/bin/env python3
"""Loopback microphone test with no human. `make` (Mac) joins fixture WAVs with natural gaps into
one playlist; `record` (Jetson) plays it on the USB speaker while the USB microphone records,
once per capture gain, after 30 s of room silence; `analyze` (Mac) feeds each recording through
the real `robot.asr.Ears` at 80 ms chunks (virtual clock, so it runs faster than real time),
transcribes every line with `Scribe`, and scores splits, false lines, edge errors, added
end-of-speech delay, and WER.

    python -m bench.mic_loopback make
    python bench/mic_loopback.py record DIR --gains 496,350,250,150     (on the robot)
    python -m bench.mic_loopback analyze [--best-gain 350]
    python -m bench.mic_loopback selftest
"""

import argparse
import hashlib
import itertools
import json
import platform
import random
import re
import subprocess
import sys
import time
import types
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build/detect-quality/mic"  # Mac: playlist, recordings (private voice)
RATE = 16000
SILENCE_S = 30.0  # room silence recorded before the playlist
SILENCE_END_S = 29.0  # aplay starts after this; its click is not silence
MARGIN_S = 0.5  # a segment this close to a played file is its line
DEVICE = "plughw:CARD=Device,DEV=0"


# ---------------------------------------------------------------- make (Mac)


def texts() -> dict[str, str]:
    out = {}
    for f in sorted((ROOT / "eval/dev").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            out.update({s["id"]: s["say"] for s in json.loads(line).get("steps", []) if "say" in s})
    return out


def speech_span(audio: np.ndarray) -> tuple[float, float]:
    """First and last second at which the clean file's Silero probability is above START_P."""
    from robot.asr import FRAME, START_P, Vad

    vad = Vad()
    p = [vad(audio[k : k + FRAME]) for k in range(0, len(audio) - FRAME + 1, FRAME)]
    hot = [k for k, v in enumerate(p) if v >= START_P]
    return hot[0] * FRAME / RATE, (hot[-1] + 1) * FRAME / RATE


def make() -> None:
    from robot.audio import read_wav, write_wav

    rng, text = random.Random(0), texts()
    real = sorted((ROOT / "eval/dev/audio-real").glob("*.wav"))
    synth = [
        p
        for p in sorted((ROOT / "eval/dev/audio").glob("*.wav"))
        if p.stem in text and p.stem not in {r.stem for r in real}
    ]
    files = [("real", p) for p in real] + [("synthetic", p) for p in rng.sample(synth, 20)]
    rng.shuffle(files)
    track, lines, t = [np.zeros(2 * RATE, np.float32)], [], 2.0
    for kind, path in files:
        audio = read_wav(path)
        ss, se = speech_span(audio)
        lines.append(
            {
                "id": path.stem,
                "kind": kind,
                "text": text[path.stem],
                "file_start_s": t,
                "file_end_s": t + len(audio) / RATE,
                "speech_start_s": t + ss,
                "speech_end_s": t + se,
            }
        )
        gap = rng.uniform(2.0, 4.0)
        track += [audio, np.zeros(int(gap * RATE), np.float32)]
        t += len(audio) / RATE + gap
    OUT.mkdir(parents=True, exist_ok=True)
    write_wav(OUT / "playlist.wav", np.concatenate(track), RATE)
    (OUT / "manifest.json").write_text(json.dumps({"lines": lines, "length_s": t}, indent=1))
    print(f"{len(lines)} lines, {t:.0f} s -> {OUT}")


# ---------------------------------------------------------------- record (Jetson)

CONTROLS = ("Mic Capture Volume", "Speaker Playback Volume")


def amixer(*args: str) -> str:
    return subprocess.run(
        ["amixer", "-c", "Device", *args], check=True, capture_output=True, text=True
    ).stdout


def mixer() -> dict[str, int]:
    """Raw value of each control we touch or must keep (named controls, so `Mic` playback stays)."""
    return {
        c: int(re.search(r": values=(\d+)", amixer("cget", f"name={c}")).group(1)) for c in CONTROLS
    }


def record(out: Path, gains: list[int]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    playlist = out / "playlist.wav"
    with wave.open(str(playlist)) as w:
        length = w.getnframes() / w.getframerate()
    before = mixer()
    print("mixer at start:", before, flush=True)
    meta = {"mixer_before": before, "recordings": {}}
    try:
        for gain in gains:
            amixer("cset", f"name={CONTROLS[0]}", str(gain))
            assert mixer()[CONTROLS[0]] == gain, mixer()
            path = out / f"rec-{gain}.wav"
            cap = subprocess.Popen(
                [
                    "arecord",
                    "-q",
                    "-D",
                    DEVICE,
                    "-f",
                    "S16_LE",
                    "-r",
                    str(RATE),
                    "-c",
                    "1",
                    "-d",
                    str(int(SILENCE_S + length + 4)),
                    str(path),
                ]
            )
            time.sleep(SILENCE_S)
            subprocess.run(["aplay", "-q", "-D", DEVICE, str(playlist)], check=True)
            cap.wait()
            meta["recordings"][gain] = {"file": path.name, "mixer": mixer()}
            print(f"gain {gain}: {path}", flush=True)
    finally:
        amixer("cset", f"name={CONTROLS[0]}", str(before[CONTROLS[0]]))  # the speaker is never set
        meta["mixer_after"] = mixer()
        (out / "record.json").write_text(json.dumps(meta, indent=1))
        print("mixer at end:", meta["mixer_after"], flush=True)
    assert meta["mixer_after"] == before, "mixer not restored"


# ---------------------------------------------------------------- analyze (Mac)


def read(path: Path) -> np.ndarray:
    from robot.audio import read_wav

    return read_wav(path)


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


def envelope(audio: np.ndarray) -> np.ndarray:
    n = len(audio) // 16 * 16
    return np.abs(audio[:n]).reshape(-1, 16).mean(1)  # 1 ms


def lag(play: np.ndarray, rec: np.ndarray, t0: float, t1: float) -> float:
    """Seconds by which `rec` trails `play`, from the envelopes of play[t0:t1] (seconds); the
    search covers a start from 1 s before to 2 s after the nominal start at SILENCE_S."""
    a = envelope(play[int(t0 * RATE) : int(t1 * RATE)])
    b = envelope(rec[int((SILENCE_S - 1 + t0) * RATE) : int((SILENCE_S + t1 + 2) * RATE)])
    a, b = a - a.mean(), b - b.mean()
    n = 1 << (len(a) + len(b)).bit_length()
    c = np.fft.irfft(np.fft.rfft(b, n) * np.conj(np.fft.rfft(a, n)), n)[:3000]
    return SILENCE_S - 1 + np.argmax(c) / 1000


def shift_model(play: np.ndarray, rec: np.ndarray, length: float):
    """Recording time of playlist time t: a line fit over eight windows, because the playback and
    capture clocks drift apart (about 0.4 ms per second)."""
    edges = np.linspace(2.0, length - 3, 9)
    slope, base = np.polyfit(
        (edges[:-1] + edges[1:]) / 2,
        [lag(play, rec, a, b) for a, b in zip(edges[:-1], edges[1:], strict=True)],
        1,
    )
    return lambda t: t + base + slope * t


def segment(audio: np.ndarray, consts: dict) -> list[dict]:
    """Lines the real `Ears` finds in `audio` fed in 80 ms chunks, with its constants overridden.
    A virtual clock stands in for arrival time, so `done_s - end_s` is the added delay."""
    import robot.asr as asr
    from robot.audio import CHUNK_S

    old = {k: getattr(asr, k) for k in consts} | {"time": asr.time}
    clock = [0.0]
    asr.time = types.SimpleNamespace(time=lambda: clock[0])
    for k, v in consts.items():
        setattr(asr, k, v)
    found, starts = [], []

    def on_line(line, end):
        found.append({"start_s": starts[-1], "end_s": end, "done_s": clock[0], "audio": line})

    try:
        ears = asr.Ears(lambda: starts.append(ears.start / RATE), on_line)
        step = int(RATE * CHUNK_S)
        for k in range(0, len(audio), step):
            chunk = audio[k : k + step]
            clock[0] = (k + len(chunk)) / RATE
            ears.feed(chunk)
    finally:
        for k, v in old.items():
            setattr(asr, k, v)
    return found


def pct(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q)), 3) if values else None


class Transcripts:
    """Parakeet text per distinct line audio, cached across arms and runs (build/ only)."""

    def __init__(self):
        from robot.asr import Scribe

        self.file = OUT / "transcripts.json"
        self.scribe = Scribe()
        self.cache = json.loads(self.file.read_text()) if self.file.exists() else {}

    def __call__(self, audio: np.ndarray) -> str:
        key = hashlib.sha1(audio.tobytes()).hexdigest()
        if key not in self.cache:
            self.cache[key] = self.scribe(audio)
            self.file.write_text(json.dumps(self.cache))
        return self.cache[key]


def match(segs: list[dict], lines: list[dict], shift) -> tuple[list[list[dict]], list[dict]]:
    """Segments per played line (a segment overlapping the line's file, shifted by the recording
    lag and widened by MARGIN_S), and the segments that overlap none. `shift` maps playlist time
    to recording time."""
    per, false = [[] for _ in lines], []
    for s in segs:
        for k, line in enumerate(lines):
            if (
                s["start_s"] < shift(line["file_end_s"]) + MARGIN_S
                and s["end_s"] > shift(line["file_start_s"]) - MARGIN_S
            ):
                per[k].append(s)
                break
        else:
            false.append(s)
    return per, false


def score(
    name: str,
    audio: np.ndarray,
    shift,
    lines: list[dict],
    consts: dict,
    transcribe: Transcripts,
    silence_s: float,
) -> dict:
    """One arm: `audio` is a recording (`shift` maps playlist time to recording time), or the clean
    playlist (identity shift). Speech time is the first `silence_s` seconds, scored apart."""
    from bench.asr_bench import wer

    segs = segment(audio, consts)
    quiet = [s for s in segs if s["start_s"] < silence_s]
    per, false = match([s for s in segs if s["start_s"] >= silence_s], lines, shift)
    counts = [len(p) for p in per]
    start = [
        (p[0]["start_s"] - shift(ln["speech_start_s"])) * 1000
        for p, ln in zip(per, lines, strict=True)
        if p
    ]
    end = [
        (p[-1]["end_s"] - shift(ln["speech_end_s"])) * 1000
        for p, ln in zip(per, lines, strict=True)
        if p
    ]
    pad = consts["PAD_S"]
    lost = [
        max(0.0, (p[0]["start_s"] - pad - shift(ln["speech_start_s"])) * 1000)
        for p, ln in zip(per, lines, strict=True)
        if p
    ]  # speech onset the recognizer never hears
    delay = [(s["done_s"] - s["end_s"]) * 1000 for s in segs]
    wers = [
        wer(ln["text"], " ".join(transcribe(s["audio"]) for s in p))
        for p, ln in zip(per, lines, strict=True)
    ]
    return {
        "arm": name,
        "consts": consts,
        "played": len(lines),
        "one_line": counts.count(1),
        "split": sum(c >= 2 for c in counts),
        "missed": counts.count(0),
        "false_in_silence": len(quiet),
        "false_between": len(false),
        "start_err_ms": {"p10": pct(start, 10), "p50": pct(start, 50), "p90": pct(start, 90)},
        "onset_lost_ms": {
            "p50": pct(lost, 50),
            "p90": pct(lost, 90),
            "over_100": int(sum(v > 100 for v in lost)),
        },
        "end_err_ms": {"p10": pct(end, 10), "p50": pct(end, 50), "p90": pct(end, 90)},
        "delay_ms": {"p50": pct(delay, 50), "p95": pct(delay, 95)},
        "wer_mean": round(float(np.mean(wers)), 4),
        "split_ids": [ln["id"] for c, ln in zip(counts, lines, strict=True) if c >= 2],
        "missed_ids": [ln["id"] for c, ln in zip(counts, lines, strict=True) if c == 0],
    }


def levels(rec: np.ndarray, shift, lines: list[dict]) -> dict:
    quiet = rec[RATE : int(SILENCE_END_S * RATE)]
    speech = np.concatenate(
        [
            rec[int(shift(ln["speech_start_s"]) * RATE) : int(shift(ln["speech_end_s"]) * RATE)]
            for ln in lines
        ]
    )
    played = rec[int(shift(0.0) * RATE) :]
    noise = db(float(np.sqrt(np.mean(quiet**2))))
    return {
        "noise_floor_dbfs": round(noise, 1),
        "noise_frame_p99_dbfs": round(
            db(
                float(
                    np.percentile(
                        np.sqrt((quiet[: len(quiet) // 512 * 512].reshape(-1, 512) ** 2).mean(1)),
                        99,
                    )
                )
            ),
            1,
        ),
        "speech_rms_dbfs": round(db(float(np.sqrt(np.mean(speech**2)))), 1),
        "speech_peak_dbfs": round(db(float(np.abs(played).max())), 1),
        "snr_db": round(db(float(np.sqrt(np.mean(speech**2)))) - noise, 1),
        "clipped_samples": int((np.abs(played) >= 32767 / 32768).sum()),
    }


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2)))


def mix(play: np.ndarray, rec: np.ndarray, lines: list[dict], snr: float) -> np.ndarray:
    """The clean playlist with the room noise recorded in `rec` (its silence, tiled) added, speech
    set `snr` dB above that noise, as 16-bit samples that clip like the microphone's."""
    noise = rec[RATE : int(SILENCE_END_S * RATE)]
    speech = np.concatenate(
        [play[int(ln["speech_start_s"] * RATE) : int(ln["speech_end_s"] * RATE)] for ln in lines]
    )
    scaled = play * 10 ** ((db(rms(noise)) + snr - db(rms(speech))) / 20) + np.resize(
        noise, len(play)
    )
    return (np.clip(np.round(scaled * 32768), -32768, 32767) / 32768).astype(np.float32)


def highpass(x: np.ndarray, fc: float = 100.0) -> np.ndarray:
    """Causal 2nd-order Butterworth high-pass (RBJ biquad), the filter a robot would run."""
    w = 2 * np.pi * fc / RATE
    alpha, cos = np.sin(w) / np.sqrt(2), np.cos(w)
    a0 = 1 + alpha
    b0, b1, a1, a2 = (1 + cos) / 2 / a0, -(1 + cos) / a0, -2 * cos / a0, (1 - alpha) / a0
    y, x1, x2, y1, y2 = np.empty_like(x), 0.0, 0.0, 0.0, 0.0
    for n, v in enumerate(x.tolist()):
        y[n] = out = b0 * (v + x2) + b1 * x1 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, out
    return y


def tegrastats() -> dict:
    """Peak RAM and GPU load while the Jetson recorded (the loopback runs no model)."""
    log = (OUT / "tegrastats.log").read_text().splitlines()
    return {
        "samples": len(log),
        "ram_mb_max": max(int(re.search(r"RAM (\d+)/", x).group(1)) for x in log),
        "gr3d_pct_max": max(int(re.search(r"GR3D_FREQ (\d+)%", x).group(1)) for x in log),
    }


def analyze(best: int) -> None:
    from robot.asr import END_P, HANGOVER_S, PAD_S, START_FRAMES, START_P

    manifest = json.loads((OUT / "manifest.json").read_text())
    lines, play = manifest["lines"], read(OUT / "playlist.wav")
    recs = {int(p.stem[4:]): read(p) for p in sorted(OUT.glob("rec-*.wav"), reverse=True)}
    transcribe, rows, level = Transcripts(), [], {}
    base = {
        "HANGOVER_S": HANGOVER_S,
        "START_FRAMES": START_FRAMES,
        "START_P": START_P,
        "PAD_S": PAD_S,
    }
    shifts = {}
    for gain, rec in recs.items():
        shifts[gain] = shift_model(play, rec, manifest["length_s"])
        level[gain] = levels(rec, shifts[gain], lines) | {
            "lag_at_start_s": round(shifts[gain](0.0), 3),
            "drift_ms_per_s": round(
                1000 * (shifts[gain](100.0) - shifts[gain](0.0) - 100) / 100, 3
            ),
        }
        rows.append(
            score(f"gain {gain}", rec, shifts[gain], lines, base, transcribe, SILENCE_END_S)
        )
        print(rows[-1], flush=True)
    ident = lambda t: t  # noqa: E731
    rows.append(score("clean playlist", play, ident, lines, base, transcribe, 0.0))
    print(rows[-1], flush=True)
    for gain, snr in itertools.product(
        recs, (12, 18, 24)
    ):  # synthetic: real room noise, louder speech
        arm = mix(play, recs[gain], lines, snr)
        rows.append(
            score(f"mix gain {gain} snr {snr}", arm, ident, lines, base, transcribe, 0.0)
            | {"clipped_samples": int((np.abs(arm) >= 1).sum())}
        )
        print(rows[-1], flush=True)
    loop, mix12 = f"loopback gain {best}", mix(play, recs[best], lines, 12)
    arms = {
        loop: (recs[best], shifts[best], SILENCE_END_S),
        "clean playlist": (play, ident, 0.0),
        f"mix gain {best} snr 12": (mix12, ident, 0.0),
        f"mix gain {best} snr 18": (mix(play, recs[best], lines, 18), ident, 0.0),
    }
    for fc in (80, 100, 150, 200, 250, 300):  # optional arm 5: one cheap high-pass before the VAD
        arms[f"{loop} + high-pass {fc} Hz"] = (
            highpass(recs[best], fc),
            shifts[best],
            SILENCE_END_S,
        )
    for fc in (100, 200, 300):
        arms[f"mix gain {best} snr 12 + high-pass {fc} Hz"] = (highpass(mix12, fc), ident, 0.0)
    arms["clean playlist + high-pass 200 Hz"] = (highpass(play, 200), ident, 0.0)
    later = [
        base | {"HANGOVER_S": h, "START_FRAMES": f, "START_P": p}
        for h, f, p in itertools.product((0.35, 0.5, 0.6), (2, 3), (0.5, 0.6))
    ]  # arm 3
    later = [c for c in later if c != base]
    earlier = [
        base | {"START_FRAMES": f, "START_P": p, "PAD_S": pad}
        for f, p, pad in itertools.product((2, 1), (0.5, 0.4, 0.3), (0.2, 0.4))
    ]  # found late
    earlier = [c for c in earlier if c != base]
    for name, (audio, shift, quiet) in arms.items():
        variants = (
            ([base] if "high-pass" in name else [])
            + (later if name in (loop, "clean playlist", f"mix gain {best} snr 18") else [])
            + (
                earlier
                if name in (loop, f"{loop} + high-pass 100 Hz", f"mix gain {best} snr 12")
                else []
            )
        )
        for consts in variants:
            desc = " ".join(f"{k.lower()} {v}" for k, v in consts.items() if v != base[k])
            rows.append(
                score(f"{name} {desc}".strip(), audio, shift, lines, consts, transcribe, quiet)
            )
            print(rows[-1], flush=True)
    out = ROOT / "bench/results/2026-10-12-mic-loopback.json"
    out.write_text(
        json.dumps(
            {
                "what": "USB speaker to USB microphone loopback, Ears on the Mac",
                "machine_record": "robot",
                "machine_analyze": platform.platform(),
                "python": sys.version.split()[0],
                "revision": subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                ).stdout.strip(),
                "command": "python -m bench.mic_loopback analyze",
                "constants_base": base | {"END_P": END_P},
                "lines_played": len(lines),
                "levels": level,
                "tegrastats": tegrastats(),
                "recorded_mixer": json.loads((OUT / "record.json").read_text()),
                "arms": rows,
            },
            indent=1,
        )
    )
    print("->", out)


# ---------------------------------------------------------------- selftest


def selftest() -> None:
    rng = np.random.default_rng(0)
    burst = rng.normal(0, 0.1, RATE) * np.hanning(RATE)
    play = np.concatenate([np.zeros(RATE), burst, np.zeros(RATE), burst * 0.5, np.zeros(RATE)])
    rec = np.concatenate([np.zeros(int(SILENCE_S * RATE) + int(0.25 * RATE)), play]).astype(
        np.float32
    )
    assert abs(lag(play.astype(np.float32), rec, 0.0, 4.0) - (SILENCE_S + 0.25)) < 0.003
    rec = rec[int(0.4 * RATE) :]  # the recording opens after the nominal start
    assert abs(lag(play.astype(np.float32), rec, 0.0, 4.0) - (SILENCE_S - 0.15)) < 0.003
    lines = [{"file_start_s": 1.0, "file_end_s": 2.0}, {"file_start_s": 3.0, "file_end_s": 4.0}]
    seg = lambda a, b: {"start_s": a, "end_s": b}  # noqa: E731
    per, false = match([seg(1.1, 1.4), seg(1.6, 1.9), seg(9.0, 9.5)], lines, lambda t: t)
    assert [len(p) for p in per] == [2, 0] and len(false) == 1
    per, false = match([seg(3.3, 3.8)], lines, lambda t: t + 0.25)
    assert [len(p) for p in per] == [0, 1] and not false
    t = np.arange(RATE * 2) / RATE
    low, high = (
        rms(highpass(np.sin(2 * np.pi * f * t).astype(np.float32))[RATE:]) for f in (20, 1000)
    )
    assert low < 0.03 and high > 0.69, (low, high)  # 1 kHz passes (0.707 RMS), 20 Hz is cut
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "record", "analyze", "selftest"])
    ap.add_argument("dir", nargs="?", type=Path)
    ap.add_argument("--gains", default="496,350,250,150")
    ap.add_argument("--best-gain", type=int, help="gain for the endpointing grid (analyze)")
    a = ap.parse_args()
    if a.cmd == "analyze" and not a.best_gain:
        ap.error("analyze needs --best-gain")
    if a.cmd == "make":
        make()
    elif a.cmd == "record":
        record(a.dir, [int(g) for g in a.gains.split(",")])
    elif a.cmd == "analyze":
        analyze(a.best_gain)
    else:
        selftest()
