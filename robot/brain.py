"""Source-grounded prompts and the native compiled Gemma E2B/MTP brain.

Legacy llama-server argument helpers remain for frozen bake-off tools. Product answers
stream uninterrupted from one serialized native runtime; closing a stream cancels it.
"""
import base64
import json
import os
import sys
import re
import threading
from collections.abc import Callable, Iterable, Iterator

import cv2
import numpy as np

from robot.config import SHARED

URL = "http://127.0.0.1:8080"
SERVER = SHARED / "src/llama.cpp/build/bin/llama-server"
GGUF = SHARED / "models/gguf"
LOG = SHARED / "logs/llama-server.log"
MODELS = {  # D27: qwen3vl-2b; the others stay for bake-offs. (weights, projector, extra args)
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
MODEL = "gemma4-e2b"
_SENTENCE = re.compile(r"[^.!?]+[.!?](?=\s|$)")
IMAGE_WIDTH = 672   # frames are downscaled before encoding; the server caps tokens anyway
MAX_TOKENS = 64
MAX_SENTENCES = 1   # one sentence: second sentences were where hedges and stale details crept in
MIN_WORDS = 6       # shorter sentences ("Of course!", "I see it now.") do not count
SYSTEM = (
    "You are Edgy, a small robot at the Qdrant booth. Everything you do runs on the Jetson "
    "board inside you: hearing, seeing, thinking, speaking, and your memory, which is "
    "Qdrant Edge. You see through a wide camera; left and right mean the left and right "
    "parts of the image.\n"
    "Answer in one short spoken sentence: no lists, no markdown, no emojis. "
    "Answer the question directly, starting with the answer itself, never with filler such "
    "as 'great question'; do not describe the whole scene unless asked. "
    "When the visitor tells you something about themselves, reply to that, warmly, "
    "and do not describe the image. You enjoy small talk and tell short, clean jokes "
    "when asked, and you may use general knowledge. Never claim to see what is not in the "
    "image; if unsure, say so.\n"
    "The image is the present: trust it over anything said before, because things move "
    "and people take objects away. Lines under 'Memories' describe what you saw before, "
    "oldest first, with their age: use them only for questions about the past. For questions about "
    "Qdrant, answer from the listed facts, close to their wording; Qdrant is a vector search "
    "engine. Your memories and what the visitor told you are real: answer from them; "
    "'do you remember X?' asks for X, so say X. Only when none of them answers a question "
    "about the past, say you do not remember."
)
CHANGED = "The view has changed since your last answer.\n"
# "your memories" alone made the 2B ignore what the visitor told it (small-talk-3).
PAST = "The visitor asks about the past: answer from the lines above.\n"
# Before the evidence, after the image, so the prefilled prefix holds (shape I, D74).
EVIDENCE = "Answer from these memories; if one answers the question, use it.\n\n"
# Main object first: recall answers with the first thing a caption names (prompt probes, D29).
CAPTION = ("Answer in this form: 'Main object: <the most prominent object>. Around it: "
           "<other things, with left, center, or right>.'")


def server_args(model: str) -> list[str]:
    weights, mmproj, extra = MODELS[model]
    # Memory (bench/memory_budget.py): prompts stay under about 1,000 tokens, so 2,048 of
    # context; no host-RAM prompt cache (8 GiB by default, it pushed the robot into swap).
    return [str(SERVER), "-m", str(GGUF / weights), "-mm", str(GGUF / mmproj), "-ngl", "99",
            "-fa", "on", "-c", "2048", "-ub", "256", "--cache-ram", "0", "-np", "1", "--jinja",
            "--image-max-tokens", "256", "--reasoning", "off", "--host", "127.0.0.1",
            "--port", URL.rsplit(":", 1)[1], *extra]


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


def messages(history: list[dict], now: dict | None, memories: list[str] = (), facts: list[str] = (),
             question: str | None = None, changed: bool = False,
             past: bool = False, told: list[str] = ()) -> list[dict]:
    """The chat prompt. Without a question it is the prefix that prefill caches: the frame
    comes before everything that depends on the question. `changed`: the view differs from
    the previous turn's, so earlier answers no longer describe it. `past`: the question is
    about the past, so the answer comes from memories, not from the image. `now` None: no
    image, for questions about the past (a 2B brain describes the image whatever it is told)."""
    content = [now] if now else []
    if question is not None:
        blocks = (("Memories", memories), ("The visitor told you", told), ("Facts", facts))
        text = "".join(f"{title}:\n- " + "\n- ".join(lines) + "\n\n"
                       for title, lines in blocks if lines)
        note = (CHANGED if changed and history else "") + (PAST if past else "")
        lead = EVIDENCE if memories or told else ""
        content.append({"type": "text", "text": f"{lead}{text}{note}Visitor: {question}"})
    return [{"role": "system", "content": SYSTEM}, *history, {"role": "user", "content": content}]


TRT_ROOT = SHARED / "experiments/p2-trt-edge"


def native_request(rt, msgs: list[dict], max_tokens: int):
    """Keep ordered evidence and decode source-owned image bytes for native rendering."""
    rows, images = [], []
    for msg in msgs:
        content = msg["content"]
        parts = [{"type": "text", "text": content}] if isinstance(content, str) else content
        contents = []
        for part in parts:
            if part["type"] == "text":
                contents.append(rt.MessageContent("text", part["text"]))
            elif part["type"] == "image_url":
                url = part["image_url"]["url"]
                prefix = "data:image/jpeg;base64,"
                if not url.startswith(prefix):
                    raise ValueError("The brain requires a source-owned JPEG data URI")
                data = base64.b64decode(url[len(prefix):], validate=True)
                images.append(rt.load_image_from_bytes(data))
                contents.append(rt.MessageContent("image", ""))
            else:
                raise ValueError(f"Unsupported robot content: {part['type']}")
        row = rt.Message(msg["role"], contents)
        row.has_content = True
        row.content_is_array = isinstance(content, list)
        rows.append(row)
    row = rt.Request(messages=rows)
    row.image_buffers = images
    request = rt.LLMGenerationRequest()
    request.requests = [row]
    request.temperature, request.top_k = 0, 1
    request.max_generate_length = max_tokens
    request.apply_chat_template = True
    request.add_generation_prompt = True
    request.enable_thinking = False
    request.skip_special_tokens = True
    return request


class Brain:
    """One native Gemma INT4/MTP runtime, with generation serialized through cancellation."""

    def __init__(self, model: str = "gemma4-e2b"):
        if model != "gemma4-e2b":
            raise ValueError("This branch runs the compiled Gemma E2B pair")
        base = json.loads((TRT_ROOT / "engines/llm/base_config.json").read_text())["builder_config"]
        draft_path = TRT_ROOT / "engines/llm/draft_config.json"
        draft = json.loads(draft_path.read_text())["builder_config"]
        visual = json.loads((TRT_ROOT / "engines/visual/config.json").read_text())["builder_config"]
        self.input_tokens = int(base["max_input_len"])
        self.image_tokens = int(visual["max_image_tokens_per_image"])
        if (self.input_tokens != 2048 or int(base["max_kv_cache_capacity"]) != 4096
                or int(base["max_batch_size"]) != 1 or int(base["max_verify_tree_size"]) != 4
                or int(draft["max_draft_tree_size"]) != 4
                or self.image_tokens != 512 or int(visual["max_image_tokens"]) != 512):
            raise ValueError("The compiled engines do not match the selected robot profile")
        from tensorrt_edgellm import runtime
        self.rt = runtime.load()
        self.lock = threading.Lock()
        self.channel, self.worker, self.closed = None, None, False
        self.runtime = self.rt.LLMRuntime(
            engine_dir=str(TRT_ROOT / "engines/llm"),
            multimodal_engine_dir=str(TRT_ROOT / "engines"),
            lora_weights_map={}, draft_top_k=1, draft_step=3, verify_tree_size=4,
            checkpoint_dir=str(TRT_ROOT / "checkpoints/int4-awq"),
            draft_checkpoint_dir=str(TRT_ROOT / "checkpoints/assistant"),
        )

    def context(self, msgs: list[dict], max_tokens: int = MAX_TOKENS) -> list[dict]:
        """Fit complete exchanges with native template counts and the compiled image bound.

        Gemma4ViTRunner.cpp:118,383,485 expands each image to at most the engine's
        soft-token limit plus two delimiters. The counted placeholder stays in place.
        Its cardinality remains reserved until target inference verifies that count.
        """
        msgs = list(msgs)
        while True:
            text = [{**m, "content": [
                {"type": "text", "text": "<|image|>"} if p["type"] == "image_url" else p
                for p in m["content"]]} if isinstance(m["content"], list) else m for m in msgs]
            images = sum(p["type"] == "image_url" for m in msgs
                         if isinstance(m["content"], list) for p in m["content"])
            count = self.runtime.count_prompt_tokens(native_request(self.rt, text, 0))[0]
            if count + images * (self.image_tokens + 2) + max_tokens <= self.input_tokens:
                return msgs
            if len(msgs) < 4 or [m["role"] for m in msgs[1:3]] != ["user", "assistant"]:
                raise ValueError("Current evidence exceeds the compiled brain context budget")
            del msgs[1:3]

    def _start(self, msgs: list[dict], max_tokens: int):
        """Reserve the GPU generation slot until its native worker retires."""
        self.lock.acquire()
        try:
            if self.closed or self.runtime is None:
                raise RuntimeError("The brain is closed")
            request = native_request(self.rt, self.context(msgs, max_tokens), max_tokens)
            channel = self.rt.StreamChannel.create()
            channel.set_skip_special_tokens(True)
            request.stream_channels = [channel]
            self.channel = channel
            engine, errors = self.runtime, []

            def generate():
                try:
                    engine.handle_request(request)
                except BaseException as error:
                    errors.append(error)
                    channel.cancel()
                finally:
                    self.lock.release()

            worker = threading.Thread(target=generate, name="trt-generate")
            self.worker = worker
            worker.start()
        except BaseException:
            self.channel, self.worker = None, None
            self.lock.release()
            raise
        return channel, worker, errors

    def answer(self, msgs: list[dict], max_tokens: int = MAX_TOKENS) -> Iterator[str]:
        """Stream one uninterrupted answer; closing it cancels and joins native generation."""
        channel, worker, errors = self._start(msgs, max_tokens)
        text, finished, early_stop = "", False, False
        try:
            while True:
                chunk = channel.wait_pop(timeout_ms=200)
                if chunk is None:
                    if channel.is_finished() or channel.is_cancelled():
                        break
                    continue
                finished = chunk.finished
                if chunk.text:
                    text += chunk.text
                    yield chunk.text
                    if sentences(text) >= MAX_SENTENCES:
                        early_stop = True
                        break
                if chunk.finished:
                    break
        finally:
            self._retire(channel, worker, finished)
        if errors and not early_stop:
            raise errors[0]

    def _retire(self, channel, worker, finished: bool) -> None:
        if not (finished or channel.is_finished()):
            channel.cancel()
        worker.join()
        if self.channel is channel:
            self.channel = None
        if self.worker is worker:
            self.worker = None

    def caption(self, image: dict, stop: Callable[[], bool]) -> str | None:
        msgs = [{"role": "user", "content": [image, {"type": "text", "text": CAPTION}]}]
        text = ""
        stream = self.answer(msgs, max_tokens=48)
        try:
            for delta in stream:
                if stop():
                    return None
                text += delta
        finally:
            stream.close()
        return text.strip()

    def close(self) -> None:
        self.closed = True
        if self.channel is not None:
            self.channel.cancel()
        with self.lock:
            self.runtime = None
        if self.worker is not None:
            self.worker.join()


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
    now = jpeg(np.zeros((720, 1280, 3), np.uint8))
    m = messages([], now, ["2 minutes ago: a red mug"], ["Qdrant is written in Rust."], "Hi?")
    text = m[-1]["content"][-1]["text"]
    assert m[-1]["content"][0] == now and "Memories:" in text and "Facts:" in text
    assert text.startswith(EVIDENCE), "the evidence instruction follows the image"
    assert not messages([], now, facts=["x"], question="Hi?")[-1]["content"][-1]["text"].startswith(
        EVIDENCE), "facts alone are not memories"
    assert messages([], now)[-1]["content"] == [now], "the prefill prompt is a prefix"
    hist = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
    note = messages(hist, now, question="And now?", changed=True)[-1]["content"][-1]["text"]
    assert note.startswith(CHANGED)
    print("selftest ok")
