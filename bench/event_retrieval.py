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

from robot.config import MODELS
from robot.memory import FIRST_PERSON, RETAIN_S, Memory, is_question
from robot.text_embed import DIM, TextEmbedder
from robot.things import mentions

CAL = Path("eval/dev/event-calibration-2.jsonl")
DEV = Path("eval/dev/event-retrieval-2.jsonl")
MANIFEST = Path("eval/dev/event-selection-2.freeze.json")
MANIFEST_HASH = "3d05e69306bb475299c105aaeac5e0be519b30cb37f7ed7a6873971a4120f288"
KINDS = ("observation", "utterance")
POLICY = "highest 0.01 grid floor retaining at least 95% of all relevant eligible pairs"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def manifest():
    if digest(MANIFEST) != MANIFEST_HASH:
        raise ValueError("Frozen manifest changed")
    data = json.loads(MANIFEST.read_text())
    checks = {data["protocol_file"]: data["protocol_sha256"],
              data["tokenizer"]["path"]: data["tokenizer"]["sha256"],
              data["validation_file"]["path"]: data["validation_file"]["sha256"]}
    checks.update({path: info["sha256"] for path, info in data["files"].items()})
    for path, expected in checks.items():
        if digest(path) != expected:
            raise ValueError(f"Frozen input changed: {path}")
    return data


def frozen(path):
    info = manifest()["files"][str(path)]
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    if len(rows) != info["questions"]:
        raise ValueError("Frozen question count changed")
    return rows


def bindings():
    data = manifest()
    return {"manifest_sha256": MANIFEST_HASH,
            "fixture_hashes": {p: i["sha256"] for p, i in data["files"].items()},
            "protocol_sha256": data["protocol_sha256"],
            "implementation_hashes": {str(p): digest(p) for p in
                                      (Path(__file__), Path("robot/memory.py"),
                                       Path("robot/text_embed.py"))},
            "model_hashes": {str(p): digest(p) for p in
                             sorted((MODELS / "bge-small").iterdir()) if p.is_file()}}


def provenance():
    return {**bindings(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD"])).hexdigest(),
        "software": {p: importlib.metadata.version(p) for p in
                     ("numpy", "qdrant-edge-py", "onnxruntime", "tokenizers")},
        "python": sys.version, "command": sys.argv, "machine": platform.node(),
        "measurement": "J" if platform.machine() == "aarch64" else "E",
        "precision": "float32 BGE and Edge vectors", "context_tokens": None,
        "image_tokens": None, "model": "bge-small-en-v1.5; no answer generation",
        "onnx_telemetry_disabled": os.environ.get("ORT_DISABLE_TELEMETRY") == "1",
        "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


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


def production(memory, query, case):
    before, since = case["query_at"], case["visitor_since"]
    ignored = case.get("ignored_kinds", [])
    entries = [(r, "observation", r["caption"]) for r in memory.recent(before)
               if not mentions(r["caption"], ignored)]
    entries += [(r, "utterance", r["said"]) for r in memory.told(query, before, 4)
                if not mentions(r["said"], ignored)
                and (not FIRST_PERSON.search(r["said"]) or r["id"] > since)][:2]
    result = []
    for row, kind, text in entries[:5]:
        source = memory.source_event(row["id"], kind)
        result.append({"source_id": row["id"], "kind": kind, "text": text,
                       "source_hash": source["source_hash"],
                       "spans": [{"start": 0, "end": len(text), "text": text}]})
    return result


def exclusions(source, payload, slot, case):
    if source is None:
        return ["missing-authority"]
    reasons = []
    if source["source_hash"] != payload.get(slot + "_hash"):
        reasons.append("stale-hash")
    before = case["query_at"]
    if not before - RETAIN_S <= source["capture_ts"] < before:
        reasons.append("capture-time-or-expiry")
    if source["scope"] == "visitor" and source["source_id"] <= case["visitor_since"]:
        reasons.append("visitor-boundary")
    if source["kind"] == "utterance" and source["speech_end"] is not None and (
            source["speech_end"] >= before):
        reasons.append("future-speech")
    if mentions(source["text"], case.get("ignored_kinds", [])):
        reasons.append("ignored-kind")
    return reasons


def best_span(source, payload, vector, slot, query):
    units = payload.get(slot + "_units", [])
    vectors = np.asarray(vector.get(slot, []))
    if not units or vectors.shape != (len(units), DIM) or not np.isfinite(vectors).all():
        return None
    unit = units[int(np.argmax(vectors @ query))]
    return {**unit, "text": source["text"][unit["start"]:unit["end"]]}


def inspect_pairs(memory, query, case, ids):
    """Score every native pair before gold labels or bounded selection are consulted."""
    candidates, ranks = [], []
    for kind, slot in zip(KINDS, ("observed", "dialogue"), strict=True):
        hits = memory.shard.query(QueryRequest(
            limit=len(ids), query=Query.Nearest(query.tolist(), using=slot),
            with_payload=True, with_vector=[slot]))
        seen = set()
        for rank, hit in enumerate(hits, 1):
            seen.add(hit.id)
            source = memory.source_event(hit.id, kind)
            reasons = exclusions(source, hit.payload, slot, case)
            span = best_span(source, hit.payload, hit.vector, slot, query) if source else None
            if span is None:
                reasons.append("missing-unit-vectors")
            ranks.append({"source_id": ids[hit.id], "kind": kind, "rank_in_kind": rank,
                          "score": hit.score, "eligible": not reasons, "exclusions": reasons,
                          "best_spans": [span] if span else []})
            if not reasons:
                candidates.append({k: v for k, v in source.items() if k != "text"} | {
                    "score": hit.score, "text": span["text"], "spans": [span],
                    "expiry": source["capture_ts"] + RETAIN_S})
        for pid in ids.keys() - seen:
            if memory.source_event(pid, kind):
                raise ValueError(f"Native query omitted populated pair {pid}/{kind}")
    return candidates, ranks


def select(candidates, thresholds):
    return sorted((e for e in candidates if e["score"] >= thresholds[e["kind"]]),
                  key=lambda e: (-e["score"], KINDS.index(e["kind"]), e["source_id"]))[:5]


def labels(case):
    return {(label["source_id"], label["kind"]): label
            for label in case["source_kind_labels"]}


def span_delivered(gold, entries, ids):
    for entry in entries:
        if (ids[entry["source_id"]], entry["kind"]) != (gold["source_id"], gold["kind"]):
            continue
        for span in entry["spans"]:
            if span["start"] <= gold["start"] and span["end"] >= gold["end"]:
                offset = gold["start"] - span["start"]
                if span["text"][offset:offset + gold["end"] - gold["start"]] == gold["text"]:
                    return True
    return False


def evaluate(case, ids, entries):
    truth = labels(case)
    returned = {(ids[e["source_id"]], e["kind"]) for e in entries}
    supporting = {pair for pair, label in truth.items() if label["sufficient"]}
    relevant = {pair for pair, label in truth.items() if label["relevant"]}
    decisive = case["decisive_spans"]
    delivered = sum(span_delivered(span, entries, ids) for span in decisive)
    return {"supporting_pair_count": len(supporting),
            "supporting_pairs_returned": len(returned & supporting),
            "supporting_source_recall": len(returned & supporting) / len(supporting)
            if supporting else None,
            "decisive_span_count": len(decisive), "decisive_spans_delivered": delivered,
            "decisive_span_coverage": delivered / len(decisive) if decisive else None,
            "returned_pairs": [list(pair) for pair in sorted(returned)],
            "related_returns": len(returned & relevant),
            "unrelated_returns": len(returned - relevant),
            "relevant_precision": len(returned & relevant) / len(returned) if returned else None,
            "absence_case": not supporting,
            "absence_unrelated_returns": len(returned - relevant) if not supporting else None,
            "absence_empty_packet": not returned if not supporting else None,
            "answer_sufficiency": "unjudged; retrieval does not establish answer correctness"}


def calibration_pairs(case, ranks):
    truth = labels(case)
    if set(truth) != {(r["source_id"], r["kind"]) for r in ranks}:
        raise ValueError("Calibration labels must cover every scored pair")
    return [{**row, "case_id": case["id"],
             "relevant": truth[(row["source_id"], row["kind"])]["relevant"],
             "sufficient": truth[(row["source_id"], row["kind"])]["sufficient"]}
            for row in ranks]


def calibrate(pairs):
    thresholds, counts = {}, {}
    for kind in KINDS:
        eligible = [p for p in pairs if p["kind"] == kind and p["eligible"]]
        relevant = [p for p in eligible if p["relevant"]]
        if not relevant:
            raise ValueError(f"No relevant eligible calibration pairs: {kind}")
        floor = max(i for i in range(-100, 101)
                    if sum(p["score"] >= i / 100 for p in relevant) * 100 >= 95 * len(relevant))
        thresholds[kind] = floor / 100
        retained = [p for p in eligible if p["score"] >= thresholds[kind]]
        relevant_count = sum(p["relevant"] for p in retained)
        counts[kind] = {"eligible": len(eligible), "relevant": len(relevant),
                        "retained": len(retained), "retained_relevant": relevant_count,
                        "retained_irrelevant": len(retained) - relevant_count,
                        "recall": relevant_count / len(relevant),
                        "precision": relevant_count / len(retained)}
    return thresholds, counts


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
                "purpose": "single-unit synthetic diagnostic; no representative cost claim",
                "points": args.points,
                "queries": args.queries,
                "units": total,
                "p99_s": float(np.percentile(times, 99)),
                "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )


def verify_calibration_pairs(case_rows, pairs):
    truth = {case["id"]: case for case in frozen(CAL)}
    if {row["id"] for row in case_rows} != set(truth):
        raise ValueError("Calibration cases differ from frozen fixture")
    expected = [pair for row in case_rows
                for pair in calibration_pairs(truth[row["id"]], row["ranks"])]
    recorded = [{k: v for k, v in pair.items() if k not in ("type", "retained")}
                for pair in pairs]
    if recorded != expected:
        raise ValueError("Calibration pair coverage or labels differ from recorded ranks")


def load_thresholds(path, expected_bindings):
    raw = path.read_bytes().splitlines(keepends=True)
    rows = [json.loads(line) for line in raw]
    if not rows or rows[-1].get("type") != "complete":
        raise ValueError("Calibration is incomplete")
    receipt = rows[-1]
    if (receipt.get("mode") != "calibrate" or receipt.get("bindings") != expected_bindings
            or receipt.get("records_sha256") != hashlib.sha256(b"".join(raw[:-1])).hexdigest()
            or receipt.get("threshold_policy") != POLICY):
        raise ValueError("Calibration provenance or receipt mismatch")
    pairs = [row for row in rows if row.get("type") == "calibration_pair"]
    thresholds, counts = calibrate(pairs)
    expected_count = manifest()["files"][str(CAL)]["questions"]
    case_rows = [row for row in rows if row.get("type") == "case"]
    verify_calibration_pairs(case_rows, pairs)
    if (receipt.get("case_count") != expected_count or len(case_rows) != expected_count
            or len({row["id"] for row in case_rows}) != expected_count
            or receipt.get("thresholds") != thresholds or receipt.get("counts") != counts
            or any(p.get("retained") != (p["eligible"] and
                   p["score"] >= thresholds[p["kind"]]) for p in pairs)):
        raise ValueError("Calibration threshold or completion mismatch")
    return thresholds


def run_cases(args, embedder, emit, thresholds):
    cases = frozen(CAL if args.mode == "calibrate" else DEV)
    pairs = []
    for case in cases:
        with tempfile.TemporaryDirectory() as tmp:
            memory = Memory(Path(tmp))
            try:
                ids, units, timings = prepare(memory, embedder, case["sources"])
                query = embedder([case["question"]])[0]
                candidates, ranks = inspect_pairs(memory, query, case, ids)
                row = {"type": "case", "id": case["id"], "category": case.get("category"),
                       "source_id_map": ids, "unit_count": units, "updates": timings,
                       "source_payload_sha256": hashlib.sha256(
                           json.dumps(case["sources"], sort_keys=True).encode()).hexdigest(),
                       "ranks": ranks, "instance_resolution_claim": False}
                if args.mode == "calibrate":
                    pairs.extend(calibration_pairs(case, ranks))
                else:
                    arms = {"production": production(memory, query, case),
                            "calibrated": select(candidates, thresholds),
                            "ranked": select(candidates, dict.fromkeys(KINDS, -1.0)),
                            "0.5-control": select(candidates, dict.fromkeys(KINDS, 0.5))}
                    row.update({"arms": arms, "results": {
                        name: evaluate(case, ids, entries) for name, entries in arms.items()}})
                emit(row)
            finally:
                memory.shard.close()
    counts = None
    if args.mode == "calibrate":
        thresholds, counts = calibrate(pairs)
        for pair in pairs:
            emit({"type": "calibration_pair", **pair, "retained": pair["eligible"] and
                  pair["score"] >= thresholds[pair["kind"]]})
    return {"case_count": len(cases), "thresholds": thresholds, "counts": counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["calibrate", "compare", "volume"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--points", type=int, default=4500)
    parser.add_argument("--queries", type=int, default=1000)
    args = parser.parse_args()
    pinned = bindings()
    thresholds = None
    if args.mode == "compare":
        if not args.calibration:
            raise ValueError("compare requires frozen --calibration")
        thresholds = load_thresholds(args.calibration, pinned)
    embedder = TextEmbedder()
    records = hashlib.sha256()
    with args.output.open("x") as output:
        def emit(row):
            line = json.dumps(row) + "\n"
            output.write(line)
            output.flush()
            records.update(line.encode())
        emit({"type": "provenance", **provenance()})
        if args.mode == "volume":
            volume(args, embedder, emit)
            return
        summary = run_cases(args, embedder, emit, thresholds)
        emit({"type": "complete", "mode": args.mode, **summary, "bindings": pinned,
              "records_sha256": records.hexdigest(), "threshold_policy": POLICY,
              "completion": "Python workload complete; external native zero-exit receipt required",
              "rss_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


if __name__ == "__main__":
    main()
