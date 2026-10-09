"""The brain: two supervised llama-server children on the GPU. Granite 4.0-H-Micro holds the
dialogue (text only: current observation, memories, facts, and the conversation); SmolVLM2-500M
observes the speech-start frame for the question and captions stored source frames (D111).
The dialogue prefix (system and history) is prefilled while nobody speaks.

    python -m robot.brain serve granite4-h-micro     run only a server (benchmarks)
"""
import base64
import json
import os
import subprocess
import sys
import time
import re
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import cv2
import numpy as np

from robot.config import SHARED

URL = "http://127.0.0.1:8080"           # the dialogue model
OBSERVER_URL = "http://127.0.0.1:8081"  # the observer model
SERVER = SHARED / "src/llama.cpp/build/bin/llama-server"
GGUF = SHARED / "models/gguf"
LOG = SHARED / "logs/llama-server.log"
OBSERVER_LOG = SHARED / "logs/observer-server.log"
MODELS = {  # D111: granite4-h-micro and smolvlm2-500m; the others stay for bake-offs.
    # (weights, projector or None, extra args)
    "granite4-h-micro": ("granite-4.0-h-micro-Q4_K_M.gguf", None, []),
    "smolvlm2-500m": ("SmolVLM2-500M-Video-Instruct-Q8_0.gguf",
                      "mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf", []),
    "qwen3vl-2b": ("Qwen3VL-2B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf", []),
    "qwen3vl-4b": ("Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf", []),
    # Sliding-window layers need the full cache for prefix reuse; per-layer embeddings stay
    # on disk and are read on demand.
    "gemma4-e2b": ("gemma-4-E2B-it-Q4_0.gguf", "mmproj-gemma-4-E2B-it-Q8_0.gguf",
                   ["--swa-full", "-lzm", "on"]),
    "qwen35-2b": ("q35-Qwen3.5-2B-Q4_K_M.gguf", "q35-mmproj-F16.gguf", []),
    "qwen35-4b": ("q35-Qwen3.5-4B-Q4_K_M.gguf", "q35-4b-mmproj-F16.gguf", []),
    "gemma3-4b": ("g3-gemma-3-4b-it-Q4_K_M.gguf", "g3-mmproj-model-f16.gguf", ["--swa-full"]),
    "minicpmv4": ("mcpm4-ggml-model-Q4_K_M.gguf", "mcpm4-mmproj-model-f16.gguf", []),
    "qwen25vl-3b": ("q25vl-Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
                    "q25vl-mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf", []),
    "lfm2vl-3b": ("lfm2-LFM2-VL-3B-Q4_K_M.gguf", "lfm2-mmproj-LFM2-VL-3B-Q8_0.gguf", []),
}
MODEL = "granite4-h-micro"
OBSERVER = "smolvlm2-500m"
_SENTENCE = re.compile(r"[^.!?]+[.!?](?=\s|$)")
IMAGE_WIDTH = 672   # frames are downscaled before encoding; the server caps tokens anyway
IMAGE_TOKENS = 256  # the observer's image budget
CONTEXT_TOKENS = 4096  # dialogue: current evidence and the output reserve first, then history
MAX_TOKENS = 128
MAX_SENTENCES = 3
MIN_WORDS = 6       # shorter sentences ("Of course!", "I see it now.") do not count
OBSERVER_CONTEXT = 2048
OBSERVE_TOKENS = 64  # observer limits: facts for the dialogue, not a spoken answer
OBSERVE_SENTENCES = 2
SYSTEM = (
    "You are Edgy, a small robot at the Qdrant booth. Everything you do runs on the Jetson "
    "board inside you: hearing, seeing, thinking, speaking, and your memory, which is "
    "Qdrant Edge.\n"
    "Answer in at most three short spoken sentences: no lists, no markdown, no emojis. "
    "Answer the question directly, starting with the answer itself, never with filler such "
    "as 'great question'; do not describe the whole scene unless asked. "
    "When the visitor tells you something about themselves, reply to that, warmly. "
    "You enjoy small talk and tell short, clean jokes when asked, and you may use general "
    "knowledge.\n"
    "The line under 'Camera now' is what your camera shows at this moment, with its capture "
    "time. It is the present: trust it over anything said before, because things move and "
    "people take objects away. Never claim to see what it does not say; without it, you "
    "cannot see the present, so say so if asked what you see. "
    "Lines under 'Memories' describe what you saw before, oldest first, with their age: use "
    "them only for questions about the past. For questions about Qdrant, answer from the "
    "listed facts, close to their wording; Qdrant is a vector search engine. Your memories "
    "and what the visitor told you are real: answer from them; 'do you remember X?' asks "
    "for X, so say X. Only when none of them answers a question about the past, say you do "
    "not remember. Treat tool results as source evidence and earlier replies as possibly "
    "outdated. Preserve source uncertainty. Do not infer possession, agency, or named "
    "referents absent from the evidence."
)
EVIDENCE_TOOL = {"type": "function", "function": {
    "name": "source_evidence",
    "description": "Code-supplied camera observations, memories, visitor statements, and facts.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}}


def template(msgs: list[dict]) -> dict:
    """The same dialogue template metadata for counting, prefill, and generation."""
    return {"chat_template_kwargs": {"enable_thinking": False}, "tool_choice": "none",
            **({"tools": [EVIDENCE_TOOL]} if any(m["role"] == "tool" for m in msgs) else {})}


# "your memories" alone made the 2B ignore what the visitor told it (small-talk-3).
PAST = "The visitor asks about the past: answer from the lines above.\n"
EVIDENCE = "Answer from these memories; if one answers the question, use it.\n\n"
# The observer sees only the speech-start frame and the question; no persona, no conversation.
OBSERVE = ("Answer from this image only, in one or two short factual sentences that name the "
           "objects, colors, and text that matter. Question: {}")
# Main object first: recall answers with the first thing a caption names (prompt probes, D29).
CAPTION = ("Answer in this form: 'Main object: <the most prominent object>. Around it: "
           "<other things, with left, center, or right>.'")


def server_args(model: str, url: str = URL, context: int = CONTEXT_TOKENS) -> list[str]:
    weights, mmproj, extra = MODELS[model]
    # No host-RAM prompt cache (8 GiB by default, it pushed the robot into swap); one slot.
    vision = ["-mm", str(GGUF / mmproj), "--image-max-tokens", str(IMAGE_TOKENS)] if mmproj else []
    return [str(SERVER), "-m", str(GGUF / weights), *vision, "-ngl", "99", "-fa", "on",
            "-c", str(context), "-ub", "256", "--cache-ram", "0", "-np", "1", "--jinja",
            "--reasoning", "off", "--host", "127.0.0.1", "--port", url.rsplit(":", 1)[1], *extra]


def _spawn(args: list[str], log: Path, url: str) -> subprocess.Popen:
    """Start one llama-server child and wait until it is healthy."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:  # one server run per file: why it failed stays readable
        proc = subprocess.Popen(args, stdout=f, stderr=f)
    for _ in range(600):
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited with {proc.returncode}; see {log}")
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1).read()
            return proc
        except OSError:
            time.sleep(0.2)
    _stop([proc])
    raise RuntimeError(f"llama-server did not become healthy; see {log}")


def _stop(procs: list[subprocess.Popen]) -> None:
    for proc in procs:
        proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def jpeg(frame: np.ndarray) -> dict:
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (IMAGE_WIDTH, round(h * IMAGE_WIDTH / w)),
                       interpolation=cv2.INTER_AREA)
    data = base64.b64encode(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 90])[1])
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + data.decode()}}


def sentences(text: str) -> int:
    """Finished statements of at least MIN_WORDS words; shorter ones ("Of course!") and
    questions (a joke's setup) do not count, so an answer can follow them."""
    return sum(len(m.split()) >= MIN_WORDS and not m.endswith("?")
               for m in _SENTENCE.findall(text))


def _content(r) -> Iterator[str]:
    """The text deltas of a streamed chat completion."""
    for raw in r:
        line = raw.decode().strip()
        if line.startswith("data: ") and line != "data: [DONE]":
            for choice in json.loads(line[6:]).get("choices", []):
                if delta := choice.get("delta", {}).get("content"):
                    yield delta


def unecho(prior: str, deltas: Iterable[str]) -> Iterator[str]:
    """`deltas` without their leading echo of `prior` (llama-server streams an assistant
    prefill back first). Text that is not an exact echo is kept and logged, never dropped."""
    held: str | None = ""
    for d in deltas:
        if held is None:
            yield d
            continue
        held += d
        if not prior.startswith(held[:len(prior)]):
            print(f"resume: the stream does not echo the prefill; kept {held!r}", flush=True)
            yield held
            held = None
        elif len(held) >= len(prior):
            if held := held[len(prior):]:
                yield held
            held = None
    if held:
        print(f"resume: the stream ended inside the echo {held!r}", flush=True)


def age(seconds: float) -> str:
    if seconds < 90:
        return f"{round(seconds)} seconds ago"
    if seconds < 3600:
        return f"{round(seconds / 60)} minutes ago"
    return f"{round(seconds / 3600)} hours ago"


def messages(history: list[dict], now: str = "", memories: list[str] = (), facts: list[str] = (),
             question: str | None = None, past: bool = False, told: list[str] = ()
             ) -> list[dict]:
    """The dialogue prompt, text only. Without a question it is the prefix that prefill caches:
    the system prompt and the conversation. `now`: the observer's line about the speech-start
    frame, with its capture time ("" when the turn does not look). Evidence follows the
    exact visitor question as one code-constructed call and matching tool result. `past`
    adds the existing past-evidence hint to the result."""
    if question is None:
        return [{"role": "system", "content": SYSTEM}, *history,
                {"role": "user", "content": [{"type": "text", "text": ""}]}]
    camera = f"Camera now:\n- {now}\n\n" if now else ""
    blocks = (("Memories", memories), ("The visitor told you", told), ("Facts", facts))
    text = "".join(f"{title}:\n- " + "\n- ".join(lines) + "\n\n"
                   for title, lines in blocks if lines)
    lead = EVIDENCE if memories or told else ""
    note = PAST if past else ""
    msgs = [{"role": "system", "content": SYSTEM}, *history,
            {"role": "user", "content": question}]
    if camera or text:
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{
            "id": "source_evidence", "type": "function",
            "function": {"name": "source_evidence", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "source_evidence",
             "content": f"{camera}{lead}{text}{note}"}]
    return msgs


class Brain:
    def __init__(self, model: str = MODEL):
        """The dialogue model `model` and the observer, each on its own port and log."""
        self.proc = _spawn(server_args(model), LOG, URL)
        try:
            self.observer = _spawn(server_args(OBSERVER, OBSERVER_URL, OBSERVER_CONTEXT),
                                   OBSERVER_LOG, OBSERVER_URL)
        except BaseException:
            _stop([self.proc])
            raise

    def _post(self, body: dict, url: str = URL):
        body = {"temperature": 0, "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False}, **body}
        req = urllib.request.Request(f"{url}/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=60)

    def _json(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(f"{URL}/{path}", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)

    def prefill(self, msgs: list[dict]) -> None:
        """Compute the dialogue cache for a prompt prefix; the next answer reuses it."""
        with self._post({"messages": msgs, **template(msgs), "max_tokens": 0}) as r:
            r.read()

    def tokens(self, text: str) -> int:
        """How many dialogue tokens `text` takes."""
        return len(self._json("tokenize", {"content": text})["tokens"])

    def rendered(self, msgs: list[dict]) -> int:
        """How many dialogue tokens `msgs` take, as the chat template renders them."""
        prompt = self._json("apply-template", {
            "messages": msgs, **template(msgs)})["prompt"]
        return len(self._json("tokenize", {"content": prompt, "parse_special": True,
                                           "add_special": False})["tokens"])

    def context(self, history: list[dict], now: str = "", memories: list[str] = (),
                facts: list[str] = (), question: str = "", past: bool = False,
                told: list[str] = ()) -> tuple[list[dict], list[dict], dict]:
        """The answer prompt, the history it keeps, and its budget. The current evidence,
        question, and MAX_TOKENS of output are reserved first; then the newest complete
        exchanges that still fit. History is always user and assistant pairs."""
        started, history, calls = time.perf_counter(), list(history), 0
        while True:
            msgs = messages(history, now, memories, facts, question, past, told)
            count, calls = self.rendered(msgs), calls + 1
            if count + MAX_TOKENS <= CONTEXT_TOKENS or not history:
                break
            history = history[2:]  # the oldest complete exchange
        if count + MAX_TOKENS > CONTEXT_TOKENS:
            raise ValueError(f"current evidence takes {count} tokens of {CONTEXT_TOKENS}")
        return msgs, history, {"rendered_tokens": count, "output_token_reserve": MAX_TOKENS,
                               "context_tokens": CONTEXT_TOKENS, "history_turns": len(history) // 2,
                               "budget_calls": 2 * calls,
                               "budget_s": round(time.perf_counter() - started, 4)}

    def answer(self, msgs: list[dict], max_tokens: int = MAX_TOKENS, prior: str = "",
               url: str = URL, max_sentences: int = MAX_SENTENCES) -> Iterator[str]:
        """Stream the answer text, at most `max_sentences` sentences and `max_tokens` tokens.
        Closing the generator early stops generation; `prior` resumes it: the answer so far,
        as an assistant prefill, counts against `max_tokens`."""
        if sentences(prior) >= max_sentences:  # paused right after the last sentence
            return
        if prior:
            msgs = msgs + [{"role": "assistant", "content": prior}]
            if (max_tokens := max_tokens - self.tokens(prior)) <= 0:
                return
        text = prior
        with self._post({"messages": msgs, "max_tokens": max_tokens, "stream": True,
                         "repeat_penalty": 1.0 if url == URL else 1.15,
                         **(template(msgs) if url == URL else {})}, url) as r:
            for delta in unecho(prior, _content(r)):
                yield delta
                text += delta
                if sentences(text) >= max_sentences:
                    return

    def _see(self, image: dict, prompt: str, max_tokens: int, max_sentences: int,
             stop: Callable[[], bool] = lambda: False) -> str | None:
        """The observer's text about one frame; None if `stop` interrupts it."""
        msgs = [{"role": "user", "content": [image, {"type": "text", "text": prompt}]}]
        text = ""
        for delta in self.answer(msgs, max_tokens, url=OBSERVER_URL,
                                 max_sentences=max_sentences):
            if stop():
                return None
            text += delta
        return text.strip()

    def observe(self, image: dict, question: str) -> str:
        """What the frame shows that bears on `question`: current evidence for one turn."""
        return self._see(image, OBSERVE.format(question), OBSERVE_TOKENS, OBSERVE_SENTENCES)

    def caption(self, image: dict, stop: Callable[[], bool]) -> str | None:
        """Describe one stored source frame from the frame alone (no persona, no
        conversation), so a memory is evidence of what was seen; None if `stop` interrupts."""
        return self._see(image, CAPTION, 48, 2, stop)

    def close(self) -> None:
        _stop([self.proc, self.observer])


if __name__ == "__main__":
    if sys.argv[1:2] == ["serve"]:
        args = server_args(sys.argv[2] if len(sys.argv) > 2 else MODEL)
        os.execv(args[0], args)
    assert age(30) == "30 seconds ago" and age(600) == "10 minutes ago"
    assert list(unecho("Hi, I", ["Hi", ", I", " see", " a cup."])) == [" see", " a cup."]
    assert list(unecho("Hi, I", ["Hi, I s", "ee"])) == [" s", "ee"], "echo and text in one"
    assert list(unecho("Hi, I", [" see", " it."])) == [" see", " it."], "no echo: all kept"
    assert list(unecho("Hi, I", ["Hi", " there"])) == ["Hi there"], "a changed echo is kept"
    assert sentences("Of course! Why don't scientists trust atoms?") == 0
    assert sentences("Sure! Here's one: Why don't scientists trust calculators?") == 0
    hello = "Hello there, it is so nice to meet you! I see clothes hanging on a rack."
    assert sentences(hello) == 2
    two = "Because atoms make up everything you see. Two cats sleep on a blanket. And"
    assert sentences(two) == 2
    now = "0 seconds ago: a red mug on a desk"
    m = messages([], now, ["2 minutes ago: a blue cap"], ["Qdrant is written in Rust."], "Hi?")
    text = m[-1]["content"]
    assert text.startswith("Camera now:\n- " + now) and "Memories:" in text and "Facts:" in text
    assert EVIDENCE + "Memories:" in text, "the evidence instruction leads the memories"
    assert not messages([], facts=["x"], question="Hi?")[-1]["content"].startswith(
        EVIDENCE), "facts alone are not memories"
    hist = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
    assert messages(hist)[:-1] == messages(hist, now, question="And now?")[:len(hist) + 1], \
        "the prefill prompt is a prefix"
    assert all(c.get("type") == "text" for m in messages(hist, now, question="Hi?")
               if isinstance(m.get("content"), list) for c in m["content"]), "no image for Granite"

    # Evidence priority: the current observation, memories, and the output reserve are kept;
    # the oldest complete exchanges go first, and only whole exchanges.
    b = Brain.__new__(Brain)
    b.rendered = lambda msgs: sum(len(str(m["content"])) for m in msgs) // 4
    turns = [{"role": r, "content": f"{r} {i} " + "x" * 400}
             for i in range(20) for r in ("user", "assistant")]
    msgs, kept, budget = b.context(turns, now, ["2 minutes ago: a blue cap"], question="Hi?")
    assert budget["rendered_tokens"] + MAX_TOKENS <= CONTEXT_TOKENS < b.rendered(
        messages(turns[-len(kept) - 2:], now, ["2 minutes ago: a blue cap"], question="Hi?")
    ) + MAX_TOKENS, "as many exchanges as fit, no more"
    assert 0 < len(kept) < len(turns) and kept == turns[-len(kept):] and len(kept) % 2 == 0
    assert kept[0]["role"] == "user" and msgs[1:1 + len(kept)] == kept, \
        "the newest complete exchanges"
    assert now in msgs[-1]["content"] and "a blue cap" in msgs[-1]["content"]
    b.rendered = lambda msgs: CONTEXT_TOKENS
    try:
        b.context([], now, question="Hi?")
        raise AssertionError("evidence that cannot fit raises")
    except ValueError:
        pass
    print("selftest ok")
