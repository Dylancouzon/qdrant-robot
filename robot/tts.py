"""Speech out: Kokoro-82M on the GPU, fed short phrases cut from the streaming answer so the
first words play while the rest is still being generated.
"""
import re
from collections.abc import Iterable, Iterator

import numpy as np
import onnxruntime as ort
from kokoro_onnx import Kokoro

from robot.config import MODELS

VOICE = "af_heart"
RATE = 24000
FIRST_WORDS = 2   # the first phrase may end at a comma after this many words
MAX_WORDS = 18    # never hold more than this before speaking
BREAK_AFTER = 4   # the first phrase may also end before a connecting word after this many words
BREAKS = {"and", "but", "with", "because", "which", "while", "so", "near", "next", "behind",
          "under", "on", "in", "at", "where", "who"}
_END = re.compile(r"[.!?;:](?=\s|$)|,(?=\s)")


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


class Speaker:
    def __init__(self):
        d = MODELS / "kokoro"
        # Every phrase has a new input length: an exhaustive cuDNN search would rerun each time.
        cuda = "CUDAExecutionProvider" in ort.get_available_providers()
        providers = ([("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"})]
                     if cuda else ["CPUExecutionProvider"])
        sess = ort.InferenceSession(str(d / "kokoro-v1.0.onnx"), providers=providers)
        self.kokoro = Kokoro.from_session(sess, str(d / "voices-v1.0.bin"))
        self.say("Ready.")  # warm every kernel before the first visitor

    def say(self, text: str) -> np.ndarray:
        audio, rate = self.kokoro.create(text, voice=VOICE, lang="en-us")
        assert rate == RATE
        return audio


if __name__ == "__main__":
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
