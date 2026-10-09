"""Offline F1h audit. Run with receipt, all-turn archive, and WAV directory arguments."""

import argparse
import collections
import hashlib
import json
from pathlib import Path

CATEGORIES = (
    "removed",
    "region",
    "similar",
    "naming",
    "forget",
    "ignore",
    "evict",
    "restart",
    "absent",
)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def validate_events(turn, authority, identity):
    events_count = collections.Counter()
    for event in turn.get("events", []):
        matches = [
            r
            for r in authority
            if r["wall_time"] <= turn["retrieved"]
            and all(
                r["source"].get(k) == event.get(k)
                for k in (
                    "source_id",
                    "kind",
                    "source_hash",
                    "capture_ts",
                    "speech_start",
                    "speech_end",
                )
            )
        ]
        assert matches, (identity, event)
        source = matches[-1]["source"]
        assert source["scope"] == event["scope"]
        assert source["source_id"] in turn["memories"]
        assert (
            hashlib.sha256(
                f"{source['source_id']}\0{source['kind']}\0{source['text']}".encode()
            ).hexdigest()
            == source["source_hash"]
        )
        assert source["capture_ts"] < turn["speech_start"]
        if source["speech_end"] is not None:
            assert source["speech_start"] <= source["speech_end"] < turn["speech_start"]
        for span in event["spans"]:
            assert source["text"][span["start"] : span["end"]] == span["text"] == event["text"]
            assert span["tokens"] <= 128
            final_content = turn["prompt"][-1]["content"]
            final_text = (
                final_content
                if isinstance(final_content, str)
                else "\n".join(c["text"] for c in final_content if c.get("type") == "text")
            )
            assert span["text"] in final_text
        assert not turn["verbatim"]
        events_count[event["kind"]] += 1

    return events_count


def cold_ids(sessions):
    cold, pending = [], True
    for session in sessions:
        for step in session["steps"]:
            if "restart" in step:
                pending = True
            if "say" in step and pending:
                cold.append(step["id"])
                pending = False
    return cold


def audit(receipt, turns_path, audio):
    receipt = Path(receipt)
    metadata, completion = rows(receipt)
    assert completion["completed"] and completion["native_exit"] in (0, 1)
    for suffix, key in (
        (".console.log", "console_sha256"),
        (".telemetry.jsonl", "telemetry_sha256"),
        (".timing.jsonl", "timing_sha256"),
    ):
        assert sha(receipt.with_suffix(suffix)) == completion[key], key
    worker = metadata["command"][metadata["command"].index("-c") + 1]
    assert hashlib.sha256(worker.encode()).hexdigest() == metadata["timed_worker_sha256"]
    archive = receipt.parent / (
        "2026-10-09-f1h-source-replay-supervisor.py.txt"
        if "source_authority" in worker
        else "2026-10-09-f1h-replay-supervisor.py.txt"
    )
    assert sha(archive) == metadata["supervisor_sha256"]
    raw = receipt.parent / Path(completion["result"]).name
    assert sha(raw) == completion["result_sha256"]
    records = rows(raw)
    summary, records = records[-1], records[:-1]
    fixture = Path(metadata["cases"])
    sessions = rows(fixture)
    steps = [
        (session["id"], step) for session in sessions for step in session["steps"] if "say" in step
    ]
    assert (
        len(records)
        == len(steps)
        == completion["expected"]
        == completion["observed"]
        == summary["n_expected"]
    )
    assert summary["release"] == metadata["release"] and summary["cases"] == metadata["cases"]
    for path, digest in metadata["input_hashes"].items():
        assert sha(path) == digest, path
    assert (
        metadata["context_tokens"] == 2048
        and metadata["image_tokens"] == 256
        and metadata["output_tokens"] == 64
    )
    turns = rows(turns_path)
    assert len(turns) == len(records)
    judged = {r["id"]: r for r in rows(raw.with_suffix(".judged.jsonl"))}
    speech_rows = rows(raw.with_suffix(".speech.jsonl"))
    assert speech_rows[-1]["completed"] and speech_rows[-1]["result_sha256"] == sha(raw)
    assert speech_rows[-1]["n"] == len(records)
    speech = {r["id"]: r for r in speech_rows[:-1]}
    cold = cold_ids(sessions)
    by_session, by_category = collections.defaultdict(list), collections.defaultdict(list)
    authority_path = receipt.with_suffix(".timing.jsonl")
    authority = [r for r in rows(authority_path) if r["type"] == "source_authority"]
    events_count = collections.Counter()
    for (session, step), record, turn in zip(steps, records, turns, strict=True):
        identity = step["id"]
        assert record["id"] == identity and record["answer"] == turn["answer"]
        for key in ("events", "prompt", "prompt_budget"):
            assert record.get(key) == turn.get(key), (identity, key)
        assert (
            judged[identity]["robot"] == record["answer"]
            and judged[identity]["visitor"] == step["say"]
        )
        assert (
            speech[identity]["answer"] == record["answer"]
            and speech[identity]["wav"] == turn["wav"]
        )
        assert sha(Path(audio) / turn["wav"]) == speech[identity]["wav_sha256"]
        result = {
            "id": identity,
            "judged": judged[identity]["pass"],
            "singleturn": record["split"] == 1,
            "speech": speech[identity]["pass"],
        }
        result["joint"] = all(result[k] for k in ("judged", "singleturn", "speech"))
        by_session[session].append(result)
        category = (
            "visitor" if fixture.stem == "visitor" else session.removeprefix("m2-").split("-")[0]
        )
        assert category in CATEGORIES or category == "visitor", category
        by_category[category].append(result)
        events_count.update(validate_events(turn, authority, identity))
        budget = turn.get("prompt_budget")
        if "source_authority" in worker and not turn["verbatim"]:
            assert budget, (identity, "missing generated-turn budget")
        if budget:
            assert budget["prompt_token_bound"] + budget["output_token_reserve"] <= 2048

    def score(group):
        return {
            "n": len(group),
            **{k: sum(r[k] for r in group) for k in ("judged", "singleturn", "speech", "joint")},
        }

    warm = [(r, t) for r, t in zip(records, turns, strict=True) if r["id"] not in cold]
    first = [t["first_audio"] - t["speech_end"] for r, t in warm]
    post_transcript = [t["first_audio"] - t["transcribed"] for r, t in warm]
    synthesis_done = [t["done"] - t["speech_end"] for r, t in warm]
    playback_end = [
        max(t["done"], t["first_audio"] + t["audio_s"]) - t["speech_end"] for r, t in warm
    ]
    loaded_start, loaded_end = turns[0]["speech_start"], turns[-1]["done"]
    telemetry = [
        r
        for r in rows(receipt.with_suffix(".telemetry.jsonl"))
        if loaded_start <= r["wall_time"] <= loaded_end
    ]
    return {
        "receipt": str(receipt),
        "receipt_sha256": sha(receipt),
        "raw_sha256": sha(raw),
        "all_turns_sha256": sha(turns_path),
        "release": metadata["release"],
        "implementation_hashes": metadata["implementation_hashes"],
        "model": summary["model"],
        "n": len(records),
        "cold_ids": cold,
        "scores": score([r for group in by_session.values() for r in group]),
        "sessions": {k: score(v) for k, v in by_session.items()},
        "categories": {k: score(v) for k, v in by_category.items()},
        "turn_scores": [r for group in by_session.values() for r in group],
        "delivered_events": dict(events_count),
        "authority_records": len(authority),
        "warm_first_synth": {
            "n": len(first),
            "p50": percentile(first, 0.5),
            "p95": percentile(first, 0.95),
        },
        "warm_post_transcript_first_synth": {
            "p50": percentile(post_transcript, 0.5),
            "p95": percentile(post_transcript, 0.95),
        },
        "warm_answer_synthesis_completion": {
            "p50": percentile(synthesis_done, 0.5),
            "p95": percentile(synthesis_done, 0.95),
        },
        "warm_estimated_synthesized_playback_end": {
            "p50": percentile(playback_end, 0.5),
            "p95": percentile(playback_end, 0.95),
        },
        "loaded_min_mem_available_mib": min(r["resources"]["mem_available_kb"] for r in telemetry)
        / 1024,
        "loaded_system_paging": {
            k: telemetry[-1]["resources"][k] - telemetry[0]["resources"][k]
            for k in ("pswpin", "pswpout")
        },
        "limits": [
            (
                "Oracle timestamps measure text-to-synthesized-audio; no speaker or "
                "physical audible measurement."
            ),
            (
                "Estimated playback end uses first_audio plus WAV duration, not a "
                "measured playback end."
            ),
            "System paging is unattributed.",
            "Instrumentation differs between baseline and candidate.",
            "Code/model bytes require archived release bindings; local tree can differ.",
            "Strict smoke, native-6, retained-volume costs, and safety gates remain pending.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt")
    parser.add_argument("turns")
    parser.add_argument("audio")
    args = parser.parse_args()
    print(json.dumps(audit(args.receipt, args.turns, args.audio), indent=2))
