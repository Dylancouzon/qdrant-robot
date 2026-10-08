"""The brain: a vision-language model in a supervised llama-server child (GPU), prompted with
the current frame, memories, facts, and the conversation. The prompt prefix (system, history,
frame) is prefilled while the visitor is still speaking.

    python -m robot.brain serve qwen3vl-2b     run only the server (benchmarks)
"""
import base64
import json
import os
import subprocess
import sys
import time
import re
import urllib.request
from collections.abc import Callable, Iterator

import cv2
import numpy as np

from robot.config import SHARED

URL = "http://127.0.0.1:8080"
SERVER = SHARED / "src/llama.cpp/build/bin/llama-server"
GGUF = SHARED / "models/gguf"
MODELS = {  # D22: qwen3vl-2b; the others stay for bake-offs
    "qwen3vl-2b": ("Qwen3VL-2B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"),
    "qwen3vl-4b": ("Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"),
    "gemma4-e2b": ("gemma-4-E2B-it-Q4_0.gguf", "mmproj-gemma-4-E2B-it-Q8_0.gguf"),
    "qwen35-2b": ("q35-Qwen3.5-2B-Q4_K_M.gguf", "q35-mmproj-F16.gguf"),
}
MODEL = "qwen3vl-2b"
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
IMAGE_WIDTH = 672   # frames are downscaled before encoding; the server caps tokens anyway
MAX_TOKENS = 64
MAX_SENTENCES = 2   # spoken answers stay short; the rest is cut in code, not left to the model
SYSTEM = (
    "You are Edgy, a small robot at the Qdrant booth. Everything you do runs on the Jetson "
    "board inside you: hearing, seeing, thinking, speaking, and your memory, which is "
    "Qdrant Edge. You see through a wide camera; left and right mean the left and right "
    "parts of the image.\n"
    "Answer in one short spoken sentence, two at most: no lists, no markdown, no emojis. "
    "Answer the question directly; do not describe the whole scene unless asked. "
    "Say only what you can see or know; if unsure, say so.\n"
    "The image is the present: trust it over anything said before, because things move "
    "and people take objects away. Lines under 'Memories' describe what you saw before, "
    "with their age: use them only for questions about the past. Use the listed facts for "
    "questions about Qdrant. Never invent a memory: if no memory answers a question about "
    "the past, say you do not remember."
)
CAPTION = ("In one sentence, name the main things in view, especially anything held up to "
           "the camera, and say where they are: left, center, or right.")


def server_args(model: str) -> list[str]:
    weights, mmproj = MODELS[model]
    return [str(SERVER), "-m", str(GGUF / weights), "-mm", str(GGUF / mmproj), "-ngl", "99",
            "-fa", "on", "-c", "4096", "-np", "1", "--jinja", "--image-max-tokens", "256",
            "--reasoning", "off", "--host", "127.0.0.1", "--port", URL.rsplit(":", 1)[1]]


def jpeg(frame: np.ndarray) -> dict:
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (IMAGE_WIDTH, round(h * IMAGE_WIDTH / w)),
                       interpolation=cv2.INTER_AREA)
    data = base64.b64encode(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 90])[1])
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + data.decode()}}


def age(seconds: float) -> str:
    if seconds < 90:
        return f"{round(seconds)} seconds ago"
    if seconds < 3600:
        return f"{round(seconds / 60)} minutes ago"
    return f"{round(seconds / 3600)} hours ago"


def messages(history: list[dict], now: dict, memories: list[str] = (), facts: list[str] = (),
             question: str | None = None) -> list[dict]:
    """The chat prompt. Without a question it is the prefix that prefill caches: the frame
    comes before everything that depends on the question."""
    content = [now]
    if question is not None:
        text = "".join(f"{title}:\n- " + "\n- ".join(lines) + "\n\n"
                       for title, lines in (("Memories", memories), ("Facts", facts)) if lines)
        content.append({"type": "text", "text": f"{text}Visitor: {question}"})
    return [{"role": "system", "content": SYSTEM}, *history, {"role": "user", "content": content}]


class Brain:
    def __init__(self, model: str = MODEL):
        self.proc = subprocess.Popen(server_args(model), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        for _ in range(600):
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with {self.proc.returncode}")
            try:
                urllib.request.urlopen(f"{URL}/health", timeout=1).read()
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("llama-server did not become healthy")

    def _post(self, body: dict):
        body = {"temperature": 0, "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False}, **body}
        req = urllib.request.Request(f"{URL}/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=60)

    def prefill(self, msgs: list[dict]) -> None:
        """Compute the KV cache for a prompt prefix; the next answer reuses it."""
        with self._post({"messages": msgs, "max_tokens": 0}) as r:
            r.read()

    def answer(self, msgs: list[dict], max_tokens: int = MAX_TOKENS) -> Iterator[str]:
        """Stream the answer text, at most MAX_SENTENCES sentences. Closing the generator
        early stops generation."""
        text = ""
        with self._post({"messages": msgs, "max_tokens": max_tokens, "stream": True,
                         "repeat_penalty": 1.15}) as r:
            for raw in r:
                line = raw.decode().strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    for choice in json.loads(line[6:]).get("choices", []):
                        if delta := choice.get("delta", {}).get("content"):
                            yield delta
                            text += delta
                            if len(_SENTENCE_END.findall(text)) >= MAX_SENTENCES:
                                return

    def caption(self, prefix: list[dict], stop: Callable[[], bool]) -> str | None:
        """One-sentence description of the frame in a turn's prompt prefix (its KV cache is
        reused), or None if `stop` interrupts it."""
        *head, user = prefix
        msgs = [*head, {**user, "content": [*user["content"], {"type": "text", "text": CAPTION}]}]
        text = ""
        for delta in self.answer(msgs, max_tokens=48):
            if stop():
                return None
            text += delta
        return text.strip()

    def close(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=10)


if __name__ == "__main__":
    if sys.argv[1:2] == ["serve"]:
        args = server_args(sys.argv[2] if len(sys.argv) > 2 else MODEL)
        os.execv(args[0], args)
    assert age(30) == "30 seconds ago" and age(600) == "10 minutes ago"
    now = jpeg(np.zeros((720, 1280, 3), np.uint8))
    m = messages([], now, ["2 minutes ago: a red mug"], ["Qdrant is written in Rust."], "Hi?")
    text = m[-1]["content"][-1]["text"]
    assert m[-1]["content"][0] == now and "Memories:" in text and "Facts:" in text
    assert messages([], now)[-1]["content"] == [now], "the prefill prompt is a prefix"
    print("selftest ok")
