#!/usr/bin/env python3
"""Brain bake-off: score one llama-server model on eval/dev/brain.jsonl and time each turn.

    python bench/brain_bakeoff.py --label gemma-audio --input audio [--url http://127.0.0.1:8080]

--input audio sends the question WAV (omni brain); --input text sends the fixture text
(the ASR candidate's brain, scored on a perfect transcript; ASR is benchmarked separately).
Writes one JSON line per case plus a summary line to $ROBOT_SHARED/results/.
"""
import argparse
import base64
import json
import os
import platform
import statistics
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval/dev/brain.jsonl"
SYSTEM = (
    "You are Edgy, a small desktop robot at a conference booth. You see through a wide "
    "camera; 'left' and 'right' mean the left and right parts of your camera image. "
    "Answer in one or two short spoken sentences, no lists, no markdown. "
    "The image is what you see right now. Your memories are what you saw or heard before; "
    "use them only for questions about the past, and say so when you do not remember."
)


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def messages(case: dict, audio: bool) -> list:
    system = SYSTEM
    if case.get("context"):
        system += "\nFacts you know:\n- " + "\n- ".join(case["context"])
    if "memory" in case:
        system += "\nYour memories:\n- " + ("\n- ".join(case["memory"]) or "(none)")
    parts = [{"type": "image_url",
              "image_url": {"url": "data:image/jpeg;base64," + b64(CASES.parent / case["image"])}}]
    if audio:
        parts.append({"type": "input_audio", "input_audio": {
            "data": b64(CASES.parent / "audio" / f"{case['id']}.wav"), "format": "wav"}})
    else:
        parts.append({"type": "text", "text": case["say"]})
    return [{"role": "system", "content": system}, {"role": "user", "content": parts}]


def turn(url: str, case: dict, audio: bool) -> dict:
    body = {"messages": messages(case, audio), "stream": True,
            "max_tokens": 64, "temperature": 0, "timings_per_token": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(f"{url}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    first, text, timings = None, "", {}
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            timings = chunk.get("timings", timings)
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                if delta.get("content") and first is None:
                    first = time.perf_counter() - t0
                text += delta.get("content") or ""
    return {"first_s": first, "total_s": time.perf_counter() - t0, "text": text.strip(),
            "timings": timings}


def score(case: dict, out: dict) -> bool:
    text = out["text"].lower()
    return any(w in text for w in case["expect_any"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--input", choices=["audio", "text"], required=True)
    p.add_argument("--url", default="http://127.0.0.1:8080")
    p.add_argument("--repeat", type=int, default=1, help="passes over the cases (warm turns)")
    a = p.parse_args()
    cases = [json.loads(line) for line in CASES.read_text().splitlines()]
    turn(a.url, cases[0], a.input == "audio")  # warm-up, not scored
    out_dir = Path(os.environ.get("ROBOT_SHARED", ROOT / "bench")) / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{time.strftime('%Y-%m-%d')}-brain-{a.label}-{int(time.time())}.jsonl"
    rows = []
    with path.open("w") as f:
        for _ in range(a.repeat):
            for case in cases:
                out = turn(a.url, case, a.input == "audio")
                row = {"id": case["id"], "capability": case["capability"],
                       "ok": score(case, out), **out}
                rows.append(row)
                f.write(json.dumps(row) + "\n")
                print(f"{'ok ' if row['ok'] else 'BAD'} {row['first_s']:.2f}s {case['id']}: "
                      f"{row['text']}", flush=True)
        firsts = sorted(r["first_s"] for r in rows if r["first_s"])
        decode = [r["timings"].get("predicted_per_second") for r in rows if r["timings"]]
        summary = {"summary": a.label, "input": a.input, "machine": platform.node(),
                   "release": os.environ.get("ROBOT_RELEASE"),
                   "cases": str(CASES.relative_to(ROOT)), "n": len(rows),
                   "correct": sum(r["ok"] for r in rows),
                   "by_capability": {c: f"{sum(r['ok'] for r in rows if r['capability'] == c)}/"
                                        f"{sum(r['capability'] == c for r in rows)}"
                                     for c in sorted({r['capability'] for r in rows})},
                   "first_token_p50_s": statistics.median(firsts),
                   "first_token_p95_s": firsts[int(0.95 * (len(firsts) - 1))],
                   "decode_tok_s_median": statistics.median([d for d in decode if d] or [0])}
        f.write(json.dumps(summary) + "\n")
    print(json.dumps(summary, indent=1))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
