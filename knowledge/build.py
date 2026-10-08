#!/usr/bin/env python3
"""Build the knowledge shard snapshot on the Mac with a real Qdrant server, the documented way
to seed Qdrant Edge: one point per fact, its question phrasings as a MaxSim multivector.

    .venv/bin/python -m knowledge.build      writes knowledge/knowledge.snapshot (needs Docker)
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from robot.text_embed import DIM, TextEmbedder

HERE = Path(__file__).resolve().parent
# The server release that shipped with qdrant-edge-py 0.8.0 (both 2026-08-05).
IMAGE = "qdrant/qdrant:v1.19.0"
URL = "http://127.0.0.1:6339"
COLLECTION = "knowledge"


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(URL + path, json.dumps(body).encode() if body else None,
                                 {"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main() -> None:
    facts = [json.loads(line) for line in (HERE / "facts.jsonl").read_text().splitlines()]
    embed = TextEmbedder()
    name = f"knowledge-build-{int(time.time())}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", "6339:6333", IMAGE],
                   check=True, capture_output=True)
    try:
        for _ in range(60):
            try:
                api("GET", "/collections")
                break
            except OSError:
                time.sleep(0.5)
        api("PUT", f"/collections/{COLLECTION}", {"vectors": {"questions": {
            "size": DIM, "distance": "Cosine",
            "multivector_config": {"comparator": "max_sim"}}}})
        points = [{"id": i, "vector": {"questions": embed(f["questions"]).tolist()},
                   "payload": {"fact": f["fact"], "questions": f["questions"]}}
                  for i, f in enumerate(facts)]
        api("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": points})
        snap = api("POST", f"/collections/{COLLECTION}/shards/0/snapshots?wait=true")["result"]
        urllib.request.urlretrieve(
            f"{URL}/collections/{COLLECTION}/shards/0/snapshots/{snap['name']}",
            HERE / "knowledge.snapshot")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    print(f"{len(points)} facts -> knowledge/knowledge.snapshot "
          f"({(HERE / 'knowledge.snapshot').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
