#!/usr/bin/env python3
"""Qdrant Edge query latency on the robot's two shards, against the 10 ms p99 target: a memory
shard filled with a booth day of turns (recency and statement queries) and the knowledge shard
(MaxSim over fact phrasings). 1,000 queries per kind, issued as the robot issues them (its
default limits), as the acceptance protocol asks.

    python -m bench.edge_bench [--points 1000]
"""
import argparse
import json
import os
import platform
import shlex
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np

from robot.config import ROOT, SHARED
from robot.knowledge import Knowledge
from robot.memory import Memory
from robot.text_embed import DIM, TextEmbedder

FACTS = ROOT / "knowledge/facts.jsonl"

QUERIES = 1000


def timed(fn, args: list) -> dict:
    """p50 and p99 in ms over one call per element of `args`."""
    ms = []
    for a in args:
        t = time.perf_counter()
        fn(*a)
        ms.append((time.perf_counter() - t) * 1000)
    return {"p50_ms": round(float(np.percentile(ms, 50)), 3),
            "p99_ms": round(float(np.percentile(ms, 99)), 3), "n": len(ms)}


def main(points: int) -> None:
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(points, DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    frame = np.zeros((36, 64, 3), np.uint8)
    with tempfile.TemporaryDirectory() as tmp:
        memory = Memory(Path(tmp))
        for k in range(points):  # every other turn is a statement with a vector
            pid = memory.add(frame, f"turn {k}", vecs[k] if k % 2 else None, ts=1000.0 + k)
            memory.set(pid, caption=f"Main object: thing {k}. Around it: a table.")
        now = 1000.0 + points
        picks = rng.integers(0, points, QUERIES)
        rows = [{"query": "memory.recent", "points": points,
                 **timed(memory.recent, [(now,)] * QUERIES)},
                {"query": "memory.told", "points": points,
                 **timed(memory.told, [(vecs[i], now) for i in picks])}]
        memory.shard.close()
        # Real visitor questions (the facts' own phrasings), so every search matches by MaxSim.
        questions = [q for line in FACTS.read_text().splitlines()
                     for q in json.loads(line)["questions"]]
        asked = TextEmbedder()(questions)
        knowledge = Knowledge(Path(tmp) / "knowledge")
        rows.append({"query": "knowledge.search", "points": knowledge.shard.info().points_count,
                     **timed(knowledge.search, [(asked[i % len(asked)],) for i in range(QUERIES)])})
        knowledge.shard.close()
    for r in rows:  # what reproduces the numbers: command, release (ENV.txt), Edge version
        r.update(machine=platform.node(), release=os.environ.get("ROBOT_RELEASE"),
                 command=shlex.join(sys.argv), qdrant_edge=version("qdrant-edge-py"))
        print(r, flush=True)
    out = SHARED / "results" / f"{time.strftime('%Y-%m-%d')}-edge-{int(time.time())}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert all(r["p99_ms"] <= 10 for r in rows), "Edge query target missed (10 ms p99)"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--points", type=int, default=1000, help="turns in the memory shard")
    main(p.parse_args().points)
