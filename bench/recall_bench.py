"""Retrieval-only comparison of exchange-recall arms on planted conversations, no LLM.

    .venv/bin/python -m bench.recall_bench [select|check] [--robot]

Each conversation's turns are stored the way the robot stores them. Exchange queries score the
six delivered exchanges, after the four newest turns (the live window) are dropped as the robot
drops them: hit (a gold one delivered), first (the top one is gold), and reciprocal rank, plus
how often the runtime cue (about_dialogue) would retrieve at all. Statement queries and traps
are scored once on the runtime path (dense said vector, TOLD_MIN, two delivered). `--robot` also
scores the robot's own Memory.exchanges, which must match the arm it implements (dbsf, D210).
"""
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from qdrant_edge import (
    Bm25,
    Bm25Config,
    Direction,
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeSparseVectorParams,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    Fusion,
    MatchValue,
    Modifier,
    OrderBy,
    PayloadSchemaType,
    Point,
    Prefetch,
    Query,
    QueryRequest,
    RangeFloat,
    UpdateOperation,
)

from robot.memory import TOLD_MIN, Memory, about_dialogue, is_statement
from robot.text_embed import DIM, TextEmbedder

DATA = Path(__file__).parent / "data/conversation-retrieval.jsonl"
STATEMENTS, EXCHANGES, LIVE = 2, 6, 4  # robot/main.py: delivered limits and the live window
# bge-small's asymmetric retrieval prefix for queries (BAAI model card).
INSTRUCTION = "Represent this sentence for searching relevant passages: "
BASE = 1_700_000_000.0  # turn and query times are seconds after this
ARMS = ["recent", "dense", "dense-instruct", "rrf", "dbsf", "rrf-instruct", "dbsf-instruct"]


def load(path: Path = DATA) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def live(conv: dict, query: dict) -> set[int]:
    """Indexes of the LIVE newest turns before the query: still in the prompt's history."""
    before = [i for i, t in enumerate(conv["turns"]) if t["t"] < query["t"]]
    return set(before[-LIVE:])


class Store:
    """All conversations in one temporary shard with the candidate schema."""

    def __init__(self, convs: list[dict], embed: TextEmbedder, bm25: Bm25):
        self.embed, self.bm25 = embed, bm25
        path = Path(tempfile.mkdtemp()) / "seen"
        path.mkdir()
        self.shard = EdgeShard.create(str(path), EdgeConfig(vectors={
            "said": EdgeVectorParams(size=DIM, distance=Distance.Cosine),
            "dialog": EdgeVectorParams(size=DIM, distance=Distance.Cosine)},
            sparse_vectors={"words": EdgeSparseVectorParams(modifier=Modifier.Idf)}))
        self.shard.update(UpdateOperation.create_field_index("ts", PayloadSchemaType.Float))
        self.shard.update(UpdateOperation.create_field_index("visitor", PayloadSchemaType.Keyword))
        self.ids: dict[tuple[str, int], int] = {}
        points = []
        for c in convs:
            texts = [f"{t['said']} {t['answer']}" for t in c["turns"]]
            dialog, said = embed(texts), embed([t["said"] for t in c["turns"]])
            for i, t in enumerate(c["turns"]):
                pid = self.ids[c["id"], i] = len(self.ids) + 1
                vectors = {"dialog": dialog[i].tolist(), "words": bm25.embed_document(texts[i])}
                if is_statement(t["said"]):
                    vectors["said"] = said[i].tolist()
                points.append(Point(pid, vectors, {"said": t["said"], "answer": t["answer"],
                                                   "visitor": c["visitor"], "ts": BASE + t["t"]}))
        self.shard.update(UpdateOperation.upsert_points(points))
        self.shard.flush()
        self.shard.optimize()

    def exchanges(self, arm: str, text: str, visitor: str, now: float, k: int) -> list[int]:
        flt = Filter(must=[FieldCondition(key="visitor", match=MatchValue(visitor)),
                           FieldCondition(key="ts", range=RangeFloat(lt=now))])
        if arm == "recent":
            req = QueryRequest(limit=k, query=OrderBy("ts", Direction.Desc), filter=flt)
            return [h.id for h in self.shard.query(req)]
        q = self.embed([INSTRUCTION + text if arm.endswith("instruct") else text])[0].tolist()
        dense = Query.Nearest(q, using="dialog")
        if arm.startswith("dense"):
            return [h.id for h in self.shard.query(QueryRequest(limit=k, query=dense, filter=flt))]
        legs = [Prefetch(limit=4 * k, query=dense, filter=flt),  # as Memory.exchanges
                Prefetch(limit=4 * k, query=Query.Nearest(self.bm25.embed_query(text),
                                                          using="words"), filter=flt)]
        fusion = Fusion.Rrf(k=2) if arm.startswith("rrf") else Fusion.Dbsf()
        return [h.id for h in self.shard.query(QueryRequest(limit=k, prefetches=legs,
                                                            query=fusion))]

    def told(self, text: str, visitor: str, now: float) -> list[int]:
        q = self.embed([text])[0].tolist()
        return [h.id for h in self.shard.query(QueryRequest(
            limit=STATEMENTS, query=Query.Nearest(q, using="said"), score_threshold=TOLD_MIN,
            filter=Filter(must=[FieldCondition(key="visitor", match=MatchValue(visitor)),
                                FieldCondition(key="ts", range=RangeFloat(lt=now))])))]


def score(convs: list[dict], store: Store, split: str, find, kinds: set[str]) -> dict:
    """Metrics per query kind; `find(conv, query, skip)` returns delivered point ids, skipping
    the live-window ids."""
    out = defaultdict(lambda: defaultdict(float))
    for c in convs:
        for q in c["queries"]:
            kind = q["kind"] if q["gold"] else {"statement": "trap"}.get(q["kind"], "skip")
            if q["split"] != split or kind not in kinds:
                continue
            gold = {store.ids[c["id"], i] for i in q["gold"]}
            skip = {store.ids[c["id"], i] for i in live(c, q)}
            if gold and gold <= skip:
                kind = "history"  # every gold turn is still in the prompt's live window
            got = find(c, q, skip)
            m = out[kind]
            m["n"] += 1
            if kind == "history":
                continue
            if not gold:
                m["delivered"] += bool(got)
                continue
            m["hit"] += bool(gold & set(got))
            m["first"] += bool(got) and got[0] in gold
            m["rr"] += next((1 / (r + 1) for r, g in enumerate(got) if g in gold), 0.0)
            m["cue"] += about_dialogue(q["text"])
    return out


def robot_find(convs: list[dict], store: Store):
    """The robot's own Memory.exchanges on a copy of the planted turns."""
    memory = Memory(Path(tempfile.mkdtemp()))
    ids = {}
    for c in convs:
        dialog = store.embed([f"{t['said']} {t['answer']}" for t in c["turns"]])
        for i, t in enumerate(c["turns"]):
            pid = memory.add(None, t["said"], ts=BASE + t["t"], dialog_vec=dialog[i],
                             visitor=c["visitor"], answer=t["answer"])
            ids[pid] = store.ids[c["id"], i]

    def find(c, q, skip):
        rows = memory.exchanges(c["visitor"], BASE + q["t"], EXCHANGES + LIVE,
                                store.embed([q["text"]])[0], q["text"])
        return [ids[r["id"]] for r in rows if ids[r["id"]] not in skip][:EXCHANGES]
    return find


def summary(m: dict) -> dict:
    row = {}
    for kind, v in m.items():
        n = v["n"]
        row[kind] = ({"n": n} if kind == "history" else
                     {"n": n, "delivered": round(v["delivered"] / n, 3)} if kind == "trap" else
                     {"n": n, **{key: round(v[key] / n, 3) for key in ("hit", "first", "rr",
                                                                       "cue")}})
    return row


def main(split: str, robot: bool) -> None:
    convs = load()
    started = time.time()
    store = Store(convs, TextEmbedder(), Bm25(Bm25Config()))
    print(f"stored {len(store.ids)} turns in {time.time() - started:.1f} s")
    rows = []
    finds = {arm: (lambda c, q, skip, arm=arm: [i for i in store.exchanges(
        arm, q["text"], c["visitor"], BASE + q["t"], EXCHANGES + LIVE) if i not in skip][
        :EXCHANGES]) for arm in ARMS}
    if robot:
        finds["robot"] = robot_find(convs, store)
    for name, find in finds.items():
        rows.append({"arm": name, "split": split,
                     **summary(score(convs, store, split, find, {"exchange", "history"}))})
    if robot:  # the runtime implements the fused arm (D210): the same exchanges per query
        for c in convs:
            for q in c["queries"]:
                if q["kind"] == "exchange" and q["split"] == split:
                    skip = {store.ids[c["id"], i] for i in live(c, q)}
                    assert finds["robot"](c, q, skip) == finds["dbsf"](c, q, skip), q["id"]
    statements = score(convs, store, split, lambda c, q, skip: store.told(
        q["text"], c["visitor"], BASE + q["t"]), {"statement", "trap"})
    rows.append({"arm": "runtime-statements", "split": split, **summary(statements)})
    rows.append({"summary": "recall_bench", "split": split,
                 "machine": platform.platform(terse=True),
                 "revision": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                            capture_output=True, text=True).stdout.strip(),
                 "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest()[:16]})
    for row in rows:
        print(json.dumps(row))
    stamp = time.strftime("%Y-%m-%d")
    name = f"{stamp}-recall-bench-{split}-{int(time.time())}.jsonl"
    out = Path(__file__).parent / "results" / name
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "select", "--robot" in sys.argv)
