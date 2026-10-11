"""Speech out: Kokoro-82M on the GPU, fed short phrases cut from the streaming answer so the
first words play while the rest is still being generated.
"""
import re
import unicodedata
from collections.abc import Iterable, Iterator

import numpy as np
import onnxruntime as ort
from kokoro_onnx import Kokoro

from robot.config import MODELS

VOICE = "af_heart"
# Spoken as people say them; Kokoro reads "Qdrant" as "Cube-rant" (heard in a transcribed answer).
SAY_AS = {"qdrant-edge-py": "quadrant edge pie", "Qdrant": "quadrant"}
RATE = 24000
FIRST_WORDS = 2   # the first phrase may end at a comma after this many words
MAX_WORDS = 18    # never hold more than this before speaking
BREAK_AFTER = 4   # the first phrase may also end before a connecting word after this many words
BREAKS = {"and", "but", "with", "because", "which", "while", "so", "near", "next", "behind",
          "under", "on", "in", "at", "where", "who"}
_END = re.compile(r"[.!?;:](?=\s|$)|,(?=\s)")


def speakable(text: str) -> str:
    """Drop emoji and other pictographs, which Kokoro would read out by name."""
    return "".join(c for c in text if unicodedata.category(c) != "So"
                   and c not in "\u200d\ufe0f").strip()


def phrases(deltas: Iterable[str]) -> Iterator[str]:
    """Cut streamed text into speakable phrases: at sentence ends, at commas once the phrase
    is long enough (early for the first one), or at MAX_WORDS."""
    buf, first = "", True
    for delta in deltas:
        buf += delta
        while True:
            cut = None
            for m in _END.finditer(buf):
                n = len(buf[:m.end()].split())
                if buf[m.start()] != "," or n >= (FIRST_WORDS if first else 8):
                    cut = m.end()
                    break
            words = list(re.finditer(r"\S+", buf))
            if first:  # speak sooner: a connecting word may start the next phrase
                brk = next((w.start() for w in words[BREAK_AFTER:]
                            if w.group().lower() in BREAKS and w.end() < len(buf)), None)
                cut = min(c for c in (cut, brk) if c is not None) if brk else cut
            if cut is None and len(words) > MAX_WORDS:
                cut = words[MAX_WORDS - 1].end()
            if not cut:
                break
            phrase, buf = buf[:cut].strip(), buf[cut:]
            if phrase:
                first = False
                yield phrase
    if buf.strip():
        yield buf.strip()


class _Shrinking:
    """An ORT session whose GPU arena gives memory back after every run: each phrase length is
    a new shape, and the arena would otherwise keep a block per shape (+1.3 GB measured)."""

    def __init__(self, sess: ort.InferenceSession):
        self.sess, self.opts = sess, ort.RunOptions()
        self.opts.add_run_config_entry("memory.enable_memory_arena_shrinkage", "gpu:0")

    def run(self, outputs, feeds, *_):  # the caller's run options are replaced by ours
        return self.sess.run(outputs, feeds, self.opts)

    def __getattr__(self, name: str):
        return getattr(self.sess, name)


class Speaker:
    def __init__(self):
        d = MODELS / "kokoro"
        # Every phrase has a new input length: an exhaustive cuDNN search would rerun each time.
        cuda = "CUDAExecutionProvider" in ort.get_available_providers()
        providers = ([("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC",
                                                "arena_extend_strategy": "kSameAsRequested"})]
                     if cuda else ["CPUExecutionProvider"])
        sess = ort.InferenceSession(str(d / "kokoro-v1.0.onnx"), providers=providers)
        self.kokoro = Kokoro.from_session(_Shrinking(sess) if cuda else sess,
                                          str(d / "voices-v1.0.bin"))
        self.say("Ready.")  # warm every kernel before the first visitor

    def say(self, text: str) -> np.ndarray:
        text = speakable(text)
        if not text:
            return np.zeros(0, np.float32)
        for written, spoken in SAY_AS.items():
            text = text.replace(written, spoken)
        audio, rate = self.kokoro.create(text, voice=VOICE, lang="en-us")
        assert rate == RATE
        return audio


if __name__ == "__main__":
    assert speakable("How's yours going? \U0001F60A") == "How's yours going?"
    assert speakable("I \u2764\ufe0f Qdrant \U0001F468\u200d\U0001F4BB") == "I  Qdrant"
    assert speakable("\U0001F60A") == "" and speakable("Edge: 0.5 ms, 90%") == "Edge: 0.5 ms, 90%"
    got = list(phrases(["Two cats", ", sleeping on", " a pink blanket. One of them is ",
                        "curled up next to a remote control, and the other", " is stretched out"]))
    assert got == ["Two cats,", "sleeping on a pink blanket.",
                   "One of them is curled up next to a remote control,",
                   "and the other is stretched out"], got
    assert list(phrases(["Yes."])) == ["Yes."]
    assert list(phrases(["I see an old motorcycle ", "in a garage with clothes."])) == [
        "I see an old motorcycle", "in a garage with clothes."]
    assert list(phrases(["It is in ", "the box."])) == ["It is in the box."], "too short to cut"
    long = " ".join(["word"] * 30)
    assert all(len(p.split()) <= MAX_WORDS for p in phrases([long]))
    print("selftest ok")
