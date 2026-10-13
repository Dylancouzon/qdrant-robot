#!/usr/bin/env python3
"""End-of-turn policies against real pauses. Dylan's real lines get 0.4, 0.6, and 0.9 s of their own
room noise inserted at word gaps (one or two pauses per line; the unchanged lines are the
control). Each clip runs through the real `robot.asr.Ears` at 80 ms chunks on a virtual clock.
Arms: A flat hangover (0.35 now, 0.5, 0.6, 0.8); B Pipecat Smart Turn v3.2 asked at 0.35 s of
silence; C a Parakeet transcript check at 0.35 s. B and C hold a line that looks unfinished until
the cap of total silence, and merge it with speech that resumes before then.

    python -m bench.endpoint_arms run
    python bench/endpoint_arms.py smart-turn-time MODEL.onnx LINE.wav      (on the Jetson)
    python -m bench.endpoint_arms selftest
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
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build/detect-quality/endpoint"  # Mac: model, clips cache, transcripts (private voice)
RATE = 16000
PAUSES = (0.4, 0.6, 0.9)  # seconds of room noise inserted
LEAD_S, TAIL_S = 0.3, 3.0  # room noise around each line
CROSSFADE_S = 0.015
CAPS = (0.8, 1.2)  # total silence a held line waits for more speech
SMART_TURN = OUT / "smart-turn-v3.2-cpu.onnx"
# Words a question cannot end on. Not "that", "this", "it", "me", "you": questions end on them.
UNFINISHED = {
    "the",
    "a",
    "an",
    "my",
    "your",
    "his",
    "her",
    "its",
    "our",
    "their",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "with",
    "from",
    "by",
    "about",
    "and",
    "or",
    "but",
    "if",
    "because",
    "where",
    "what",
    "which",
    "who",
    "when",
    "how",
    "why",
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "could",
    "will",
    "would",
}


# ---------------------------------------------------------------- Smart Turn v3.2


def mel_filters() -> np.ndarray:
    """80 Slaney mel filters over the 201 bins of a 400-point FFT, as Whisper builds them."""

    def hz_to_mel(f):
        f = np.asarray(f, float)
        return np.where(
            f < 1000, 3 * f / 200, 15 + np.log(np.maximum(f, 1000) / 1000) * 27 / np.log(6.4)
        )

    def mel_to_hz(m):
        m = np.asarray(m, float)
        return np.where(m < 15, 200 * m / 3, 1000 * np.exp(np.log(6.4) / 27 * (m - 15)))

    centers = mel_to_hz(np.linspace(hz_to_mel(0), hz_to_mel(8000), 82))
    bins = np.linspace(0, 8000, 201)[:, None]
    down = (bins - centers[:-2]) / (centers[1:-1] - centers[:-2])
    up = (centers[2:] - bins) / (centers[2:] - centers[1:-1])
    return np.maximum(0, np.minimum(down, up)) * (2 / (centers[2:] - centers[:-2]))  # (201, 80)


def smart_turn_features(audio: np.ndarray) -> np.ndarray:
    """(1, 80, 800) log-mel features of the last 8 s of `audio`, left-padded with zeros, as the
    Pipecat `WhisperFeatureExtractor(chunk_length=8)` call with `do_normalize=True` builds them."""
    audio = audio[-8 * RATE :]
    audio = np.pad(audio, (8 * RATE - len(audio), 0)).astype(np.float64)
    audio = (audio - audio.mean()) / np.sqrt(audio.var() + 1e-7)
    padded = np.pad(audio, (200, 200), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, 400)[::160]
    power = np.abs(np.fft.rfft(frames * np.hanning(401)[:-1], axis=1)) ** 2
    log = np.log10(np.maximum(power @ mel_filters(), 1e-10))[:-1].T
    return ((np.maximum(log, log.max() - 8.0) + 4.0) / 4.0)[None].astype(np.float32)


class SmartTurn:
    def __init__(self, path: Path = SMART_TURN, threads: int = 1):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads, opts.inter_op_num_threads = threads, 1
        self.sess = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])

    def __call__(self, audio: np.ndarray) -> float:
        """Probability that the speaker has finished."""
        return float(
            self.sess.run(None, {"input_features": smart_turn_features(audio)})[0].ravel()[0]
        )


def smart_turn_time(model: Path, wav_path: Path) -> None:
    """CPU ms of one Smart Turn call (features and model) on an 8 s window, one and two threads."""
    with wave.open(str(wav_path)) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    audio = np.tile(audio, 1 + 8 * RATE // len(audio))[: 8 * RATE]
    for threads in (1, 2):
        st = SmartTurn(model, threads)
        st(audio)
        ms = []
        for _ in range(60):
            t = time.perf_counter()
            st(audio)
            ms.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        for _ in range(60):
            smart_turn_features(audio)
        print(
            json.dumps(
                {
                    "machine": platform.node(),
                    "threads": threads,
                    "call_ms_p50": round(float(np.percentile(ms, 50)), 1),
                    "call_ms_p95": round(float(np.percentile(ms, 95)), 1),
                    "features_ms": round((time.perf_counter() - t) / 60 * 1000, 1),
                }
            )
        )


# ---------------------------------------------------------------- fixtures


def own_noise(audio: np.ndarray, n: int) -> np.ndarray:
    """`n` samples of the quietest 200 ms of `audio` (its own room noise), mirrored to length."""
    frame = RATE // 50
    energy = (audio[: len(audio) // frame * frame].reshape(-1, frame) ** 2).mean(1)
    best = int(np.argmin(np.convolve(energy, np.ones(10), "valid")))
    quiet = audio[best * frame : (best + 10) * frame]
    cycle = np.concatenate([quiet, quiet[::-1]])
    return np.resize(cycle, n).astype(np.float32)


def fade(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a followed by b, with a short crossfade over the join."""
    n = int(CROSSFADE_S * RATE)
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    return np.concatenate([a[:-n], a[-n:] * (1 - ramp) + b[:n] * ramp, b[n:]])


def gap_points(scribe, audio: np.ndarray) -> list[tuple[int, str]]:
    """(sample, previous word) of the quietest 30 ms just before each word after the first."""
    result = scribe.model.with_timestamps().recognize(audio)
    words = []  # (start s, word)
    for t, tok in zip(result.timestamps, result.tokens, strict=True):
        if tok.startswith(" ") or not words:
            words.append((t, tok))
        else:
            words[-1] = (words[-1][0], words[-1][1] + tok)
    smooth = np.convolve(np.abs(audio), np.ones(RATE * 30 // 1000) / (RATE * 30 // 1000), "same")
    points = []
    for (_, before), (t, _) in zip(words, words[1:], strict=False):
        lo, hi = max(0, int((t - 0.25) * RATE)), min(len(audio), int((t + 0.05) * RATE))
        if lo < hi and t > 0.5 and len(audio) - hi > 0.4 * RATE:
            points.append(
                (lo + int(np.argmin(smooth[lo:hi])), re.sub(r"[^a-z']", "", before.lower()))
            )
    return points


def insert_pauses(audio: np.ndarray, points: list[int], seconds: float) -> np.ndarray:
    pieces, last = [], 0
    for p in sorted(points):
        pieces += [audio[last:p], own_noise(audio, int(seconds * RATE))]
        last = p
    pieces.append(audio[last:])
    out = pieces[0]
    for piece in pieces[1:]:
        out = fade(out, piece)
    return out


def clip(audio: np.ndarray, source: np.ndarray) -> np.ndarray:
    """The line between room noise, so the stream has a silent tail for the endpointer."""
    return np.concatenate(
        [own_noise(source, int(LEAD_S * RATE)), audio, own_noise(source, int(TAIL_S * RATE))]
    )


def fixtures(scribe, text: dict[str, str]) -> list[dict]:
    """Controls and pause variants of every real line. A variant whose Parakeet transcript differs
    from its control's words is dropped: the pause landed inside a word."""
    from bench.asr_bench import words
    from robot.audio import read_wav

    rng, rows = random.Random(0), []
    for path in sorted((ROOT / "eval/dev/audio-real").glob("*.wav")):
        audio = read_wav(path)
        heard = words(scribe(audio))
        rows.append(
            {
                "id": path.stem,
                "kind": "control",
                "pause_s": 0.0,
                "pauses": 0,
                "text": text[path.stem],
                "audio": clip(audio, audio),
            }
        )
        points = gap_points(scribe, audio)
        one = rng.choice(points)[0] if points else None
        far = [p for p, _ in points if one is not None and abs(p - one) > int(0.6 * RATE)]
        mid_phrase = [p for p, before in points if before in UNFINISHED]
        wheres = (
            {
                "word gap": [[one]]
                + ([sorted([one, rng.choice(far)])] if far and len(points) >= 4 else []),
                "mid phrase": [[rng.choice(mid_phrase)]] if mid_phrase else [],
            }
            if points
            else {}
        )
        for (kind, options), seconds in itertools.product(wheres.items(), PAUSES):
            for where in options:
                made = insert_pauses(audio, where, seconds)
                if words(scribe(made)) == heard:
                    rows.append(
                        {
                            "id": path.stem,
                            "kind": kind,
                            "pause_s": seconds,
                            "pauses": len(where),
                            "text": text[path.stem],
                            "audio": clip(made, audio),
                        }
                    )
    return rows


# ---------------------------------------------------------------- policies


class Models:
    """Parakeet text and Smart Turn probability per distinct audio, with the first call's CPU ms."""

    def __init__(self):
        from robot.asr import Scribe

        self.scribe, self.turn = Scribe(), SmartTurn()
        self.file = OUT / "transcripts.json"
        self.cache = json.loads(self.file.read_text()) if self.file.exists() else {}
        self.turn_cache = {}

    def text(self, audio: np.ndarray) -> tuple[str, float]:
        key = hashlib.sha1(audio.tobytes()).hexdigest()
        if key not in self.cache:
            t = time.perf_counter()
            self.cache[key] = [self.scribe(audio), (time.perf_counter() - t) * 1000]
            self.file.write_text(json.dumps(self.cache))
        return self.cache[key][0], self.cache[key][1] / 1000

    def smart_turn(self, audio: np.ndarray) -> tuple[float, float]:
        key = hashlib.sha1(audio.tobytes()).hexdigest()
        if key not in self.turn_cache:
            t = time.perf_counter()
            self.turn_cache[key] = (self.turn(audio), time.perf_counter() - t)
        return self.turn_cache[key]


def unfinished(text: str) -> bool:
    """The line ends on a word a question cannot end on, or is only the wake phrase."""
    from robot.asr import woken

    last = re.sub(r"[^a-z']", "", text.lower().split()[-1]) if text.split() else ""
    return woken(text) == "" or last in UNFINISHED


def policy(
    segs: list[dict], stream: np.ndarray, models: Models, kind: str, cap: float
) -> list[dict]:
    """Lines B or C would release from the candidate lines `segs` (found at the 0.35 s hangover).
    Each has `audio`, `end_s` (speech end), `release_s` (when it is let go, with model time), and
    `text_s` (when its transcript exists, counting the Parakeet run it needs)."""
    from robot.asr import PAD_S

    out, k = [], 0
    while k < len(segs):
        first = cur = k
        while True:
            seg = segs[cur]
            audio = (
                seg["audio"]
                if cur == first
                else stream[
                    int((segs[first]["start_s"] - PAD_S) * RATE) : int(
                        (seg["end_s"] + PAD_S) * RATE
                    )
                ]
            )
            if kind == "B":
                prob, cost = models.smart_turn(
                    stream[
                        max(0, int((segs[first]["start_s"] - PAD_S) * RATE)) : int(
                            seg["done_s"] * RATE
                        )
                    ]
                )
                done, ready = prob > 0.5, seg["done_s"] + cost
            else:
                text, asr = models.text(audio)
                done, ready = not unfinished(text), seg["done_s"] + asr
            nxt = segs[cur + 1] if cur + 1 < len(segs) else None
            if not done and nxt and nxt["start_s"] - seg["end_s"] < cap:
                cur += 1  # speech resumed: one line
                continue
            if kind == "B":
                text, asr = models.text(audio)
            release = ready if done else max(ready, seg["end_s"] + cap)
            out.append(
                {
                    "audio": audio,
                    "end_s": seg["end_s"],
                    "release_s": release,
                    "text": text,
                    "text_s": release + (0 if kind == "C" else asr),
                }
            )
            break
        k = cur + 1
    return out


def flat(segs: list[dict], models: Models) -> list[dict]:
    out = []
    for s in segs:
        text, asr = models.text(s["audio"])
        out.append(
            {
                "audio": s["audio"],
                "end_s": s["end_s"],
                "release_s": s["done_s"],
                "text": text,
                "text_s": s["done_s"] + asr,
            }
        )
    return out


def arms_for(segs_by_hang: dict, models: Models, stream: np.ndarray) -> dict[str, list[dict]]:
    arms = {f"A flat {h}": flat(segs_by_hang[h], models) for h in (0.35, 0.5, 0.6, 0.8)}
    for kind, cap in itertools.product("BC", CAPS):
        arms[f"{kind} {'smart turn' if kind == 'B' else 'transcript'} at 0.35 cap {cap}"] = policy(
            segs_by_hang[0.35], stream, models, kind, cap
        )
    for hang in (0.5, 0.6):  # a later look: pays the hangover on every turn, merges more
        arms[f"C transcript at {hang} cap 1.2"] = policy(
            segs_by_hang[hang], stream, models, "C", 1.2
        )
    return arms


# ---------------------------------------------------------------- run


def pct(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q)), 3) if values else None


def run() -> None:
    from bench.asr_bench import wer
    from bench.mic_loopback import segment, texts
    from robot.asr import HANGOVER_S, LONG_HANGOVER_S, PAD_S, START_FRAMES, START_P

    models = Models()
    rows = fixtures(models.scribe, texts())
    base = {
        "HANGOVER_S": HANGOVER_S,
        "LONG_HANGOVER_S": LONG_HANGOVER_S,
        "START_FRAMES": START_FRAMES,
        "START_P": START_P,
        "PAD_S": PAD_S,
    }
    results: dict[str, list[dict]] = {}
    probe: dict[str, list[float]] = {"fragment_before_0.9s_pause": [], "complete_control": []}
    for n, row in enumerate(rows):
        segs = {
            h: segment(
                row["audio"], base | {"HANGOVER_S": h, "LONG_HANGOVER_S": max(h, LONG_HANGOVER_S)}
            )
            for h in (0.35, 0.5, 0.6, 0.8)
        }
        first = segs[0.35][:1]
        if first and (
            (row["pause_s"] == 0.9 and row["pauses"] == 1 and len(segs[0.35]) > 1)
            or (row["pause_s"] == 0 and len(segs[0.35]) == 1)
        ):
            probe[
                "complete_control" if row["pause_s"] == 0 else "fragment_before_0.9s_pause"
            ].append(models.smart_turn(row["audio"][: int(first[0]["done_s"] * RATE)])[0])
        for arm, lines in arms_for(segs, models, row["audio"]).items():
            results.setdefault(arm, []).append(
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "pause_s": row["pause_s"],
                    "pauses": row["pauses"],
                    "lines": len(lines),
                    "wer": wer(row["text"], " ".join(line["text"] for line in lines)),
                    "wait_ms": (lines[0]["release_s"] - lines[0]["end_s"]) * 1000
                    if lines
                    else None,
                    "text_ms": (lines[0]["text_s"] - lines[0]["end_s"]) * 1000 if lines else None,
                }
            )
        print(f"{n + 1}/{len(rows)} {row['id']} {row['pause_s']}", flush=True)
    summary = {arm: summarize(per) for arm, per in results.items()}
    out = ROOT / "bench/results/2026-10-12-endpoint-arms.json"
    out.write_text(
        json.dumps(
            {
                "what": "end-of-turn policies on real-voice pause variants, "
                "Ears on a virtual clock",
                "machine": platform.platform(),
                "python": sys.version.split()[0],
                "revision": subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                ).stdout.strip(),
                "command": "python -m bench.endpoint_arms run",
                "constants": base,
                "smart_turn": {
                    "model": "pipecat-ai/smart-turn-v3 smart-turn-v3.2-cpu.onnx",
                    "license": "BSD-2-Clause",
                    "repo_revision": "f766f81d3cfdf7737ac64aad813d91bbfd56bf93",
                    "sha256": hashlib.sha256(SMART_TURN.read_bytes()).hexdigest(),
                    "code_revision": "pipecat-ai/smart-turn 4786657e242d (inference.py)",
                },
                "cpu_ms_mac": {
                    "smart_turn": {
                        "p50": pct([v[1] * 1000 for v in models.turn_cache.values()], 50),
                        "p95": pct([v[1] * 1000 for v in models.turn_cache.values()], 95),
                    },
                    "parakeet": {
                        "p50": pct([v[1] for v in models.cache.values()], 50),
                        "p95": pct([v[1] for v in models.cache.values()], 95),
                    },
                },
                "caps_s": CAPS,
                "pauses_s": PAUSES,
                "clips": len(rows),
                "controls": sum(r["pause_s"] == 0 for r in rows),
                "smart_turn_called_complete": {
                    k: {
                        "n": len(v),
                        "p_over_0.5": round(float(np.mean(np.array(v) > 0.5)), 3),
                        "median": pct(v, 50),
                    }
                    for k, v in probe.items()
                },
                "arms": summary,
                "per_clip": results,
            },
            indent=1,
        )
    )
    print("->", out)


def summarize(per: list[dict]) -> dict:
    """Split rate is extra lines per inserted pause (0 when every pause was merged)."""
    out = {}
    for kind, seconds in itertools.product(("word gap", "mid phrase"), PAUSES):
        rows = [r for r in per if r["kind"] == kind and r["pause_s"] == seconds]
        out[f"{kind} {seconds} s"] = {
            "split_per_pause": round(
                sum(r["lines"] - 1 for r in rows) / sum(r["pauses"] for r in rows), 3
            ),
            "clips_split": f"{sum(r['lines'] > 1 for r in rows)}/{len(rows)}",
            "wer": round(float(np.mean([r["wer"] for r in rows])), 4),
        }
    ctrl = [r for r in per if r["kind"] == "control"]
    out["controls_split"] = f"{sum(r['lines'] > 1 for r in ctrl)}/{len(ctrl)}"
    for key in ("wait_ms", "text_ms"):
        v = [r[key] for r in ctrl if r[key] is not None]
        out[f"control_{key}"] = {"p50": pct(v, 50), "p90": pct(v, 90)}
    out["wer_controls"] = round(float(np.mean([r["wer"] for r in ctrl])), 4)
    return out


# ---------------------------------------------------------------- selftest


def selftest() -> None:
    assert mel_filters().shape == (201, 80) and abs(mel_filters().sum(0).max()) < 0.05
    feats = smart_turn_features(
        np.random.default_rng(0).normal(0, 0.1, 3 * RATE).astype(np.float32)
    )
    assert feats.shape == (1, 80, 800) and np.isfinite(feats).all()
    assert (
        unfinished("Do you see my") and unfinished("Hey Edgy.") and not unfinished("What is this?")
    )
    tone = np.sin(np.arange(RATE) * 0.3).astype(np.float32) * 0.5
    tone[RATE // 2 :] *= 0.001  # a quiet second half: the "room noise"
    noise = own_noise(tone, RATE)
    assert abs(noise).max() < 0.01 and len(noise) == RATE
    made = insert_pauses(tone, [4000, 9000], 0.4)
    assert abs(len(made) - (len(tone) + 2 * int(0.4 * RATE) - 4 * int(CROSSFADE_S * RATE))) < 2
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "smart-turn-time", "selftest"])
    ap.add_argument("args", nargs="*", type=Path)
    a = ap.parse_args()
    if a.cmd == "run":
        run()
    elif a.cmd == "smart-turn-time":
        smart_turn_time(*a.args)
    else:
        selftest()
