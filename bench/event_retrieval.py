"""Frozen development retrieval comparison. Generation and acceptance stay lead-owned.

python -m bench.event_retrieval calibrate --output /tmp/event-cal.jsonl
Compare uses --calibration /tmp/event-cal.jsonl and a separate --output path.
python -m bench.event_retrieval volume --points 4500 --queries 1000 --output /tmp/event-volume.jsonl
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import resource
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from qdrant_edge import Point, Query, QueryRequest, UpdateOperation

from robot.memory import FIRST_PERSON, RETAIN_S, Memory, is_question
from robot.text_embed import DIM, TextEmbedder
from robot.things import mentions

CAL = Path("eval/dev/event-calibration.jsonl")
DEV = Path("eval/dev/event-retrieval.jsonl")
HASHES = {
    str(CAL): "409c8e9b8ae343ed9824f9e39a6969884b431b884f7344b675ce0a4b66b98507",
    str(DEV): "7f2041d898c4f0fea87b1b7a9d1386fc58790a0b97bccbcf291f30a467803ee8",
}


def frozen(path):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != HASHES[str(path)]:
        raise ValueError(f"Frozen fixture changed: {path}")
    return [json.loads(line) for line in data.splitlines()]


def provenance():
    return {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD"])).hexdigest(),
        "software": {
            p: importlib.metadata.version(p)
            for p in ("numpy", "qdrant-edge-py", "onnxruntime", "tokenizers")
        },
        "implementation_hashes": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path("robot/memory.py"), Path("robot/text_embed.py"))
        },
        "python": sys.version,
        "command": sys.argv,
        "fixture_hashes": HASHES,
        "machine": platform.node(),
        "measurement": "J" if platform.machine() == "aarch64" else "E",
        "precision": "float32 BGE and Edge vectors",
        "context_tokens": None,
        "image_tokens": None,
        "model": "bge-small-en-v1.5; no answer generation",
        "onnx_telemetry_disabled": os.environ.get("ORT_DISABLE_TELEMETRY") == "1",
        "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def prepare(memory, embedder, sources):
    """Identical authoritative payloads for baseline and candidate; stable fixture-ID map."""
    ids, count, timings = {}, 0, []
    for i, source in enumerate(sources, 1):
        ids[i] = source["id"]
        payload = {
            "ts": source.get("ts", 100.0 + i),
            "said": source.get("said", ""),
            "thumb": bytes(64 * 36).hex(),
            **({"caption": source["caption"]} if source.get("caption") else {}),
        }
        vectors = {}
        if payload["said"] and not is_question(payload["said"]):
            vectors["said"] = embedder([payload["said"]])[0].tolist()
        memory.shard.update(UpdateOperation.upsert_points([Point(i, vectors, payload)]))
        for kind in ("observation", "utterance"):
            event = memory.source_event(i, kind)
            if not event:
                continue
            started = time.monotonic()
            units, vecs = embedder.embed_units(event["text"])
            embedded = time.monotonic()
            assert memory.index_event(
                i,
                kind,
                event["source_hash"],
                units,
                vecs,
                speech_start=source.get("utterance_start") if kind == "utterance" else None,
                speech_end=source.get("utterance_end") if kind == "utterance" else None,
            )
            timings.append(
                {
                    "source_id": source["id"],
                    "kind": kind,
                    "units": len(units),
                    "embedding_s": embedded - started,
                    "update_s": time.monotonic() - embedded,
                    "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                }
            )
            count += len(units)
    memory.shard.flush()
    return ids, count, timings


def packets(memory, embedder, case, thresholds):
    query = embedder([case["question"]])[0]
    before, since = case.get("query_at", 2000.0), case.get("visitor_since", 0)
    ignored = case.get("ignored_kinds", [])
    baseline = [
        {"source_id": r["id"], "kind": "observation", "text": r["caption"]}
        for r in memory.recent(before)
        if not mentions(r["caption"], ignored)
    ]
    baseline += [
        {"source_id": r["id"], "kind": "utterance", "text": r["said"]}
        for r in memory.told(query, before, 4)
        if not mentions(r["said"], ignored)
        and (not FIRST_PERSON.search(r["said"]) or r["id"] > since)
    ][:2]
    candidate = []
    for kind in ("observation", "utterance"):
        candidate += memory.events(
            query, before, since, thresholds[kind], kind, skip=lambda text: mentions(text, ignored)
        )
    return baseline[:5], sorted(candidate, key=lambda e: e["score"], reverse=True)[:5]


def evaluate(case, ids, entries):
    returned = {ids[e["source_id"]] for e in entries}
    expected = set(case["expected_source_ids"])
    required = {
        source["id"]: (
            "observation"
            if source.get("kind") == "observed"
            else "utterance"
            if source.get("kind") == "dialogue"
            else source.get("kind")
        )
        for source in case.get("sources", [])
    }
    supported = {
        ids[e["source_id"]] for e in entries if required.get(ids[e["source_id"]]) == e.get("kind")
    }
    return {
        "supporting_source_recall": len(expected & supported) / len(expected) if expected else None,
        "returned_source_ids": sorted(returned),
        "expected_source_ids": sorted(expected),
        "partial_source_returns": sorted(returned - (expected & supported)),
        "source_id_recall": len(expected & returned) / len(expected) if expected else None,
        "answer_sufficiency": "unjudged; source IDs and cosine scores do not prove facts",
        "absence_case": not bool(expected),
    }


def diagnose(memory, embedder, case, ids):
    """Inspect rank and eligibility without using expected answers for selection."""
    query = embedder([case["question"]])[0]
    before, since = case["query_at"], case["visitor_since"]
    ignored = case.get("ignored_kinds", [])
    candidates, ranks = [], []
    for kind, slot in (("observation", "observed"), ("utterance", "dialogue")):
        candidates += memory.events(query, before, since, -1.0, kind,
                                    skip=lambda text: mentions(text, ignored))
        hits = memory.shard.query(QueryRequest(
            limit=len(ids), query=Query.Nearest(query.tolist(), using=slot),
            with_payload=True, with_vector=[slot]))
        for rank, hit in enumerate(hits, 1):
            source, reasons, spans = memory.source_event(hit.id, kind), [], []
            if source is None:
                reasons.append("missing-authority")
            else:
                if source["source_hash"] != hit.payload.get(slot + "_hash"):
                    reasons.append("stale-hash")
                if not before - RETAIN_S <= source["capture_ts"] < before:
                    reasons.append("capture-time-or-expiry")
                if source["scope"] == "visitor" and hit.id <= since:
                    reasons.append("visitor-boundary")
                if kind == "utterance" and source["speech_end"] is not None and (
                        source["speech_end"] >= before):
                    reasons.append("future-speech")
                if mentions(source["text"], ignored):
                    reasons.append("ignored-kind")
                units = hit.payload.get(slot + "_units", [])
                vectors = np.asarray(hit.vector[slot])
                if units and vectors.shape == (len(units), DIM):
                    unit = units[int(np.argmax(vectors @ query))]
                    spans = [{**unit, "text": source["text"][unit["start"]:unit["end"]]}]
                else:
                    reasons.append("missing-unit-vectors")
            ranks.append({"source_id": ids[hit.id], "kind": kind, "rank_in_kind": rank,
                          "score": hit.score, "exclusions": reasons, "best_spans": spans})
    selected = sorted(candidates, key=lambda event: event["score"], reverse=True)[:5]
    return {"unfiltered_ranks": ranks, "eligible_before_selection": candidates,
            "selected": selected, "before_selection_result": evaluate(case, ids, candidates),
            "after_selection_result": evaluate(case, ids, selected),
            "merge_policy": "descending raw cosine; observation-first stable tie order",
            "score_rejection": False, "purpose": "diagnostic only; no adoption claim"}


def volume(args, embedder, emit):
    if args.points not in (4500, 20000) or args.queries < 1000:
        raise ValueError("Volume requires 4500 or 20000 points, at least 1000 queries")
    with tempfile.TemporaryDirectory() as tmp:
        memory = Memory(Path(tmp))
        sources = [
            {
                "id": f"volume-{i}",
                "ts": 100.0 + i / args.points,
                "caption": f"A green case with silver hinges, number {i}.",
            }
            for i in range(args.points)
        ]
        # Incremental preparation records preserve native failures.
        total = 0
        for offset in range(0, args.points, 100):
            # prepare allocates local IDs, so batch points through a single accumulating list.
            batch = sources[offset : offset + 100]
            for source in batch:
                pid = offset + batch.index(source) + 1
                memory.shard.update(
                    UpdateOperation.upsert_points(
                        [Point(pid, {}, {"ts": source["ts"], "caption": source["caption"]})]
                    )
                )
                event = memory.source_event(pid, "observation")
                start = time.monotonic()
                units, vectors = embedder.embed_units(event["text"])
                embedded = time.monotonic()
                assert memory.index_event(pid, "observation", event["source_hash"], units, vectors)
                total += len(units)
                emit(
                    {
                        "type": "update",
                        "source_id": pid,
                        "unit_count": len(units),
                        "embedding_s": embedded - start,
                        "update_s": time.monotonic() - embedded,
                        "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    }
                )
        query = embedder(["What hinges did the green case have?"])[0]
        times = []
        for i in range(args.queries):
            start = time.monotonic()
            events = memory.events(query, 2000.0, 0, -1.0, "observation")
            elapsed = time.monotonic() - start
            times.append(elapsed)
            emit(
                {
                    "type": "query",
                    "index": i,
                    "seconds": elapsed,
                    "source_ids": [e["source_id"] for e in events],
                }
            )
        memory.shard.close()
        emit(
            {
                "type": "complete",
                "points": args.points,
                "queries": args.queries,
                "units": total,
                "p99_s": float(np.percentile(times, 99)),
                "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )


def load_thresholds(args):
    thresholds = {"observation": -1.0, "utterance": -1.0}
    if args.mode in ("compare", "diagnose"):
        if not args.calibration:
            raise ValueError("compare requires frozen --calibration")
        rows = [json.loads(line) for line in args.calibration.read_text().splitlines()]
        completion = rows[-1]
        if (
            completion.get("type") != "complete"
            or completion.get("fixture_hash") != HASHES[str(CAL)]
        ):
            raise ValueError("Calibration must have successful completion and pinned source hash")
        thresholds = completion["thresholds"]
    return thresholds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["calibrate", "compare", "diagnose", "volume"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--points", type=int, default=4500)
    parser.add_argument("--queries", type=int, default=1000)
    args = parser.parse_args()
    cases = frozen(CAL if args.mode == "calibrate" else DEV) if args.mode != "volume" else []
    thresholds = load_thresholds(args)
    embedder = TextEmbedder()
    positive_scores = {"observation": [], "utterance": []}
    with args.output.open("x") as output:

        def emit(row):
            output.write(json.dumps(row) + "\n")
            output.flush()

        emit({"type": "provenance", **provenance()})
        if args.mode == "volume":
            volume(args, embedder, emit)
            return
        for case in cases:
            sources = case["sources"]
            if args.mode == "calibrate":
                sources = [
                    {
                        "id": s["id"],
                        "ts": 100.0 + i,
                        "caption" if s["kind"] == "observed" else "said": s["text"],
                    }
                    for i, s in enumerate(sources)
                ]
            with tempfile.TemporaryDirectory() as tmp:
                memory = Memory(Path(tmp))
                ids, units, timings = prepare(memory, embedder, sources)
                baseline, candidate = packets(memory, embedder, case, thresholds)
                diagnostic = (diagnose(memory, embedder, case, ids)
                              if args.mode == "diagnose" else {})
                for event in candidate:
                    if ids[event["source_id"]] in case["expected_source_ids"]:
                        positive_scores[event["kind"]].append(event["score"])
                emit(
                    {
                        "type": "case",
                        "id": case["id"],
                        "category": case.get("category"),
                        "source_id_map": ids,
                        "source_payload_sha256": hashlib.sha256(
                            json.dumps(sources, sort_keys=True).encode()
                        ).hexdigest(),
                        "unit_count": units,
                        "updates": timings,
                        "baseline": baseline,
                        "candidate": candidate,
                        "baseline_result": evaluate(case, ids, baseline),
                        "candidate_result": evaluate(case, ids, candidate),
                        "instance_resolution_claim": False,
                        "diagnostic": diagnostic,
                    }
                )
                memory.shard.close()
        if args.mode == "calibrate":
            # A recall-oriented floor; related absent-case returns remain explicit.
            thresholds = {
                kind: min(scores) if scores else 0.5 for kind, scores in positive_scores.items()
            }
        emit(
            {
                "type": "complete",
                "case_count": len(cases),
                "thresholds": thresholds,
                "fixture_hash": HASHES[str(CAL if args.mode == "calibrate" else DEV)],
                "threshold_policy": "minimum supporting calibration score; no fact-existence claim",
                "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )


if __name__ == "__main__":
    main()
