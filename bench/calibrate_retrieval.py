"""Calibrate the minimum scores of the sighting and named-object searches on dev questions (bge
question vector against a label or a name): relevant pairs (the question names that kind, or
"my <name>") against every other pair, including questions about absent things.

    python -m bench.calibrate_retrieval
"""
import json
import time
from pathlib import Path

import numpy as np

from robot.memory import kinds
from robot.text_embed import TextEmbedder

ROOT = Path(__file__).resolve().parent.parent
VOCAB = ['apple', 'backpack', 'badge', 'bag', 'ball', 'banana', 'bicycle', 'book', 'bottle', 'box',
         'camera', 'car', 'cat', 'chair', 'clock', 'computer mouse', 'cup', 'dog', 'face',
         'glasses', 'hat', 'headphones', 'keyboard', 'keys', 'lamp', 'lanyard', 'laptop',
         'microphone', 'monitor', 'motorcycle', 'mug', 'orange', 'pen', 'person', 'phone', 'photo',
         'plush toy', 'poster', 'potted plant', 'remote control', 'scissors', 'sign', 'sticker',
         'stop sign', 't-shirt', 'teddy bear', 'toy', 'umbrella', 'wallet', 'watch']
NAMES = ["phone", "teddy bear", "laptop", "cup", "lucky charm", "wallet", "keys"]


def questions() -> list[str]:
    out = []
    for f in sorted((ROOT / "eval/dev").glob("*.jsonl")):
        for r in map(json.loads, f.read_text().splitlines()):
            out += [s["say"] for s in r.get("steps", [r]) if "say" in s]
    return sorted(set(out))


def report(name: str, sims: np.ndarray, relevant: np.ndarray) -> dict:
    pos, neg = sims[relevant], sims[~relevant]
    row = {"shard": name, "relevant": len(pos), "other": len(neg),
           "relevant_min": round(float(pos.min()), 3), "relevant_p10": round(float(
               np.percentile(pos, 10)), 3), "other_max": round(float(neg.max()), 3),
           "other_p99": round(float(np.percentile(neg, 99)), 3)}
    print(row)
    return row


def main() -> None:
    embed, qs = TextEmbedder(), questions()
    q = embed(qs)
    labels = embed(VOCAB)
    sims = q @ labels.T
    named = np.array([[v in kinds(x, VOCAB) for v in VOCAB] for x in qs])
    rows = [report("sightings", sims, named)]
    for k in np.argsort(-(sims * ~named).max(1))[:8]:
        j = int(np.argmax(sims[k] * ~named[k]))
        print(f"  other {sims[k, j]:.3f} {VOCAB[j]!r} <- {qs[k]!r}")
    for k in np.argsort((sims + 9 * ~named).min(1))[:5]:
        j = int(np.argmin(sims[k] + 9 * ~named[k]))
        print(f"  relevant {sims[k, j]:.3f} {VOCAB[j]!r} <- {qs[k]!r}")
    names = embed(NAMES)
    sims = q @ names.T
    mine = np.array([[f"my {n}" in x.lower() for n in NAMES] for x in qs])
    rows.append(report("named", sims, mine))
    for k in np.argsort(-(sims * ~mine).max(1))[:8]:
        j = int(np.argmax(sims[k] * ~mine[k]))
        print(f"  other {sims[k, j]:.3f} {NAMES[j]!r} <- {qs[k]!r}")
    stamp = f"{time.strftime('%Y-%m-%d')}-retrieval-min-{int(time.time())}"
    out = ROOT / "bench/results" / f"{stamp}.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in rows + [{
        "summary": "retrieval-min", "questions": len(qs), "model": "bge-small-en-v1.5",
        "machine": "mac", "command": "python -m bench.calibrate_retrieval"}]))
    print(out)


if __name__ == "__main__":
    main()
