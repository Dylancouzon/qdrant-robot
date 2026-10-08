#!/usr/bin/env python3
"""Does llama-server reuse a cached system prompt plus image? Time a cold turn, a warm-up that
prefills only the shared prefix, then a turn with a new question on the same image.

    python bench/prefix_cache.py [--url http://127.0.0.1:8080] [--audio]
"""
import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "eval/dev/images/coco-000000039769.jpg"
SYSTEM = "You are Edgy, a small desktop robot. Answer in one short spoken sentence."


def ask(url: str, parts: list, max_tokens: int) -> tuple[float, dict]:
    body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": parts}],
            "max_tokens": max_tokens, "temperature": 0, "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(f"{url}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    return time.perf_counter() - t, out.get("timings", {})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8080")
    a = p.parse_args()
    img = {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64," + base64.b64encode(IMAGE.read_bytes()).decode()}}
    for label, parts, n in [
        ("cold, new image + question", [img, {"type": "text", "text": "How many cats?"}], 1),
        ("prefix only (speech start)", [img], 0),
        ("same image, new question", [img, {"type": "text", "text": "What color is it?"}], 1),
        ("same image, another question", [img, {"type": "text", "text": "Any remotes?"}], 1),
    ]:
        dt, t = ask(a.url, parts, n)
        print(f"{dt * 1000:6.0f} ms  prompt_n={t.get('prompt_n')} cache_n={t.get('cache_n')} "
              f"prompt_ms={t.get('prompt_ms', 0):.0f}  {label}")


if __name__ == "__main__":
    main()
