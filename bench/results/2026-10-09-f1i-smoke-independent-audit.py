"""Offline smoke binding and overlap audit; no runtime or model imports."""

import contextlib
import hashlib
import io
import json
from pathlib import Path

base = Path("bench/results")


def rows(p):
    return [json.loads(x) for x in p.read_text().splitlines()]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    exec(
        compile(
            (base / "2026-10-09-f1i-smoke-audit.py.txt").read_text(),
            "archived_stdlib_audit",
            "exec",
        ),
        {},
    )
reproduced = json.loads(captured.getvalue())
assert reproduced == json.loads((base / "2026-10-09-f1i-smoke-audit.json").read_text())
raw = rows(base / "2026-10-09-f1i-smoke-candidate-a.jsonl")
timing = rows(base / "2026-10-09-f1i-smoke-candidate-a.timing.jsonl")
finish = raw[-1]
assert finish["completed"] and finish["worker_exit"] == 0
assert finish["counts"] == reproduced["expected"]
assert finish["chunks"] == 1128 and finish["samples"] == 1440000
assert len(finish["utterance_ids"]) == 4 and len(set(finish["utterance_ids"])) == 4
old = rows(base / "2026-10-09-f1g-smoke-baseline-a.jsonl")
oldmeta = next(r for r in old if r["type"] == "metadata")
meta = next(r for r in raw if r["type"] == "metadata")
assert oldmeta["sha256"] == meta["sha256"] and oldmeta["lateness_s"] == meta["lateness_s"] == 0.5
starts = {r["call"]: r for r in timing if r["type"] == "call_start"}
calls = []
for end in timing:
    if end["type"] != "call_end":
        continue
    start = starts[end["call"]]
    assert start["name"] == end["name"] and start["thread"] == end["thread"]
    assert start["monotonic"] <= end["monotonic"]
    calls.append(
        {
            "name": end["name"],
            "thread": end["thread"],
            "start_wall": start["wall_time"],
            "end_wall": end["wall_time"],
            "elapsed_s": end["elapsed_s"],
            "call": end["call"],
        }
    )
report = max((c for c in calls if c["name"] == "scheduler_report"), key=lambda c: c["elapsed_s"])
resources = [
    c
    for c in calls
    if c["name"] == "evaluator_resources"
    and report["start_wall"] <= c["start_wall"] <= c["end_wall"] <= report["end_wall"]
]
assert len(resources) == 1 and resources[0]["thread"] == report["thread"]
audio = [r for r in raw if r["type"] == "audio"]
late = max(audio, key=lambda r: r["lateness_s"])
origin = next(r for r in raw if r["type"] == "source_probe")
origin_wall = origin["capture_wall"] - origin["elapsed_s"]
delayed_wall = origin_wall + late["actual_end_s"]
overlaps = [
    c
    for c in calls
    if c["start_wall"] < report["end_wall"] and c["end_wall"] > report["start_wall"]
]
nextfeed = min(
    (c for c in calls if c["name"] == "scheduler_feed" and c["start_wall"] >= report["end_wall"]),
    key=lambda c: c["start_wall"],
)
observed = next(r for r in timing if r["type"] == "observer_finished")
assert observed["returned_exit"] == 0
assert reproduced["max_recorded_audio_lateness_s"] < 0.5
inputs = {"visits": sha(Path(meta["cases"]))}
result = {
    "reproduced_archived_audit_exactly": True,
    "audit": reproduced,
    "input_bindings": inputs,
    "largest_report": report,
    "nested_resources": resources[0],
    "delayed_audio_chunk": late,
    "report_to_delayed_chunk_s": delayed_wall - report["end_wall"],
    "next_scheduler_feed": nextfeed,
    "overlapping_calls": overlaps,
    "interpretation": (
        "The scheduler thread spent almost all of its longest report inside synchronous "
        "resource collection before the most delayed audio chunk. Other threads executed "
        "during that interval. This supports a scheduler-path telemetry stall, but does not "
        "identify why resources took longer or prove a GIL/native root cause."
    ),
    "binding_limit": (
        "The original smoke metadata binds visits and recorded pixel probes; "
        "it does not contain a complete per-input WAV/AVI byte manifest."
    ),
    "alternatives": [
        "Move evaluator resource sampling outside the audio scheduling thread, "
        "preserving timestamps and watchdog decisions.",
        "Reduce synchronous resource collection work while preserving measured counters.",
        "Consider runtime/process isolation only if timing after separating evaluator work "
        "still demonstrates native scheduling interference.",
    ],
    "scope": (
        "One strict development smoke passes timing and native teardown. No causal root fix, "
        "physical audible timing, answer-quality, sustained, or paging-free acceptance."
    ),
}
print(json.dumps(result, indent=2))
