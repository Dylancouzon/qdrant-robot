"""Score completed continuous runs against separate frozen rubrics, without changing inputs.

Answer judgments use the existing three-vote cache; retrieval measures source presence only.
"""

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

from eval import judge
from eval.continuous import RATE, counts, digest


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inputs(result, cases, rubrics):
    rows, visits, rules = read(result), read(cases), read(rubrics)
    if not rows or rows[-1].get("type") != "completion":
        raise ValueError("continuous run lacks post-exit completion")
    footer = rows[-1]
    steps = [step for visit in visits for step in visit["steps"]]
    duration = max(visit["start_at_s"] + visit["duration_s"] for visit in visits)
    spoken = [step for step in steps if "say" in step]
    expected = [step["id"] for step in spoken]
    utterances = [row for row in rows if row.get("type") == "utterance"]
    if (
        footer.get("completed") is not True
        or footer.get("worker_exit") != 0
        or footer.get("counts") != counts(visits, steps)
        or footer.get("elapsed_s", 0) < duration
        or footer.get("samples") != round(duration * RATE)
        or [row["id"] for row in rows if row.get("type") == "event"]
        != [step["id"] for step in steps]
        or footer.get("utterance_ids") != expected
        or footer.get("event_ids") != [step["id"] for step in steps]
        or footer.get("visit_ids") != [visit["id"] for visit in visits]
        or [row["id"] for row in utterances] != expected
        or any(row.get("type") == "error" for row in rows)
        or rows[0].get("sha256") != digest(cases)
    ):
        raise ValueError("invalid completion, coverage, or source schedule")
    by_id = {rule["id"]: rule for rule in rules}
    scored = [step for step in spoken if step["scored"]]
    if len(by_id) != len(rules) or set(by_id) != {step["id"] for step in scored}:
        raise ValueError("rubrics must cover every scored question exactly once")
    if any(by_id[step["id"]]["category"] != step.get("category") for step in scored):
        raise ValueError("rubric categories differ from frozen schedule")
    turns = {row["id"]: row for row in utterances}
    for step in spoken:
        row = turns[step["id"]]
        if row["scored"] != step["scored"] or row["category"] != step.get("category"):
            raise ValueError("utterance labels differ from frozen schedule")
        if row["ok"] and (
            row["split"] != 1 or len(row["turns"]) != 1 or not row["heard"] or not row["answer"]
        ):
            raise ValueError("invalid successful utterance")
    return scored, turns, by_id, footer


def retrieval(row, rule):
    """Count source presence in delivered evidence; current-frame storage is excluded."""
    category = rule["category"]
    if category not in ("older_observation", "topic_reference", "correction"):
        return {"applicable": False, "reason": "current sight or no required stored evidence"}
    expected, found, unknown = set(rule["source_ids"]), set(), set()
    for turn in row["turns"]:
        if category == "older_observation":
            ids, uncertain = retained_captions(turn)
            unknown.update(uncertain)
            for mapping in turn["source_mappings"]:
                if mapping["runtime_id"] in ids and mapping["mapping"] == "matched":
                    found.update(mapping["source_ids"])
                elif mapping["runtime_id"] in ids:
                    unknown.add(mapping["runtime_id"])
        else:
            for statement in turn["retrieved_statements"][:5]:
                # Repeated identical ASR strings cannot identify a unique source statement.
                if len(statement["step_ids"]) == 1:
                    found.update(statement["step_ids"])
    return {
        "applicable": True,
        "expected": sorted(expected),
        "returned": sorted(found),
        "matched": sorted(expected & found),
        "recall": len(expected & found) / len(expected) if expected else None,
        "all_present": bool(expected) and expected <= found,
        "limit": 5,
        "unknown_runtime_ids": sorted(unknown),
        "note": "Confirmed prompt sources; unknown delivery makes recall a lower bound",
    }


def retained_captions(turn):
    """Resolve caption deduplication from final prompt text and authoritative payloads."""
    ids = turn["memories"]
    payloads = {payload["id"]: payload for payload in turn["payloads"]}
    prompt = turn.get("prompt", [])
    content = prompt[-1].get("content", []) if prompt else []
    text = "\n".join(part["text"] for part in content if part.get("type") == "text")
    block = text.split("Memories:\n", 1)[1].split("\n\n", 1)[0] if "Memories:\n" in text else ""
    lines = [line[2:] for line in block.splitlines() if line.startswith("- ")]
    newest, uncertain = {}, set()
    for pid in ids:
        payload = payloads.get(pid, {})
        caption = " ".join((payload.get("caption") or "").split())
        stamp = payload.get("ts")
        if not caption or not isinstance(stamp, (int, float)):
            uncertain.add(pid)
            continue
        if caption not in newest or stamp > newest[caption][0]:
            newest[caption] = (stamp, pid)
    retained = set()
    for caption, (_, pid) in newest.items():
        if any(line.partition(": ")[2] == caption for line in lines):
            retained.add(pid)
        else:
            # Ignored-kind rewriting or another route may change the rendered text.
            uncertain.add(pid)
    return retained & set(ids[:5]), uncertain & set(ids[:5])


def score(result, cases, rubrics):
    steps, rows, rules, footer = inputs(result, cases, rubrics)
    items = [
        {
            "id": step["id"],
            "visitor": step["say"] + "\nASR transcript: " + rows[step["id"]]["heard"],
            "robot": rows[step["id"]]["answer"],
            "rubric": rules[step["id"]]["rubric"],
        }
        for step in steps
        if rows[step["id"]]["ok"]
    ]
    verdict_rows, new_count = judge.score_items(items)
    verdicts = {row["id"]: row for row in verdict_rows}
    output = result.with_suffix(".judged.jsonl")
    records = []
    for step in steps:
        sid = step["id"]
        verdict = verdicts.get(sid, {"pass": False, "why": rows[sid]["failure"], "votes": []})
        records.append(
            {
                "id": sid,
                "category": rules[sid]["category"],
                "structural_ok": rows[sid]["ok"],
                "heard": rows[sid]["heard"],
                "answer": rows[sid]["answer"],
                **{k: verdict[k] for k in ("pass", "why", "votes")},
                "retrieval": retrieval(rows[sid], rules[sid]),
            }
        )
    output.write_text("".join(json.dumps(row) + "\n" for row in records))
    categories = {}
    for category in sorted({row["category"] for row in records}):
        group = [row for row in records if row["category"] == category]
        evidence = [row["retrieval"] for row in group if row["retrieval"]["applicable"]]
        categories[category] = {
            "answers_pass": sum(row["pass"] for row in group),
            "n": len(group),
            "retrieval_questions": len(evidence),
            "all_sources_present": sum(row["all_present"] for row in evidence),
            "matched_sources": sum(len(row["matched"]) for row in evidence),
            "expected_sources": sum(len(row["expected"]) for row in evidence),
            "delivery_unknown_questions": sum(bool(row["unknown_runtime_ids"]) for row in evidence),
        }
    summary = {
        "summary": "continuous_scoring",
        "completed": True,
        "result_sha256": digest(result),
        "cases_sha256": digest(cases),
        "rubrics_sha256": digest(rubrics),
        "judged_sha256": digest(output),
        "judge_model": judge.MODEL,
        "votes": judge.VOTES,
        "judge_prompt_sha256": hashlib.sha256(judge.PROMPT.encode()).hexdigest(),
        "machine": platform.node(),
        "python": platform.python_version(),
        "command": sys.argv,
        "code_sha256": digest(Path(__file__)),
        "new_judgments": new_count,
        "scored": len(records),
        "answers_pass": sum(row["pass"] for row in records),
        "run_failed_steps": footer["failed_steps"],
        "categories": categories,
        "speech_output_verified": False,
        "note": "Synthetic baseline; no physical audio or full milestone acceptance",
    }
    target = result.with_suffix(".scoring.jsonl")
    target.write_text(json.dumps(summary) + "\n")
    print(json.dumps(summary, indent=2))
    return int(summary["answers_pass"] != summary["scored"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("cases", type=Path)
    parser.add_argument("rubrics", type=Path)
    args = parser.parse_args()
    raise SystemExit(score(args.result, args.cases, args.rubrics))
