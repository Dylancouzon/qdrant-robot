"""Judged counts per capability, where a turn whose answer equals the reference run's answer
keeps the reference verdict: the contextual judge can flip an identical answer when the
preceding dialogue differs (research/conversation.md, 2026-10-17).

    python -m bench.paired FIXTURE.jsonl REFERENCE.judged.jsonl RUN.judged.jsonl ...
"""
import json
import sys
from collections import Counter
from pathlib import Path


def adjusted(caps: dict[str, str], ref: dict[str, dict], run: dict[str, dict]) -> Counter:
    passed = Counter()
    for i, cap in caps.items():
        same = run.get(i, {}).get("robot") == ref.get(i, {}).get("robot")
        ok = bool((ref if same else run).get(i, {}).get("pass"))
        passed[cap] += ok
        passed["ALL"] += ok
    return passed


def main(fixture: str, ref: str, runs: list[str]) -> None:
    caps = {st["id"]: st.get("capability", "-") for line in Path(fixture).read_text().splitlines()
            for st in json.loads(line)["steps"] if "say" in st}
    load = lambda p: {r["id"]: r for r in map(json.loads, Path(p).read_text().splitlines())  # noqa: E731
                      if "id" in r}
    n = Counter(caps.values()) + Counter(ALL=len(caps))
    for run in runs:
        got = adjusted(caps, load(ref), load(run))
        print(run, " ".join(f"{k}:{got[k]}/{n[k]}" for k in sorted(n)))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        ref = {"a": {"robot": "Hi.", "pass": True}, "b": {"robot": "No.", "pass": False}}
        run = {"a": {"robot": "Hi.", "pass": False}, "b": {"robot": "Yes.", "pass": True}}
        assert adjusted({"a": "x", "b": "y"}, ref, run) == Counter(x=1, y=1, ALL=2)
        print("selftest ok")
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3:])
