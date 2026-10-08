#!/usr/bin/env python3
"""Judge a replay on the Mac: a Codex model grades each spoken answer against its fixture
rubric (meaning, not keywords). Writes <result>.judged.jsonl and exits non-zero on any FAIL.

    python3 eval/judge.py bench/results/<date>-replay-<id>.jsonl [eval/dev/sessions.jsonl]
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "bench/judge-cache.jsonl"  # verdicts by hash of judge, rubric, and answer
VOTES = 3
MODEL = "gpt-6-sol"  # luna disagreed with itself on correct answers between runs
PROMPT = """You grade a small robot's spoken answers at a conference booth. For each item you get
what the visitor said (as transcribed), the robot's answer, and a rubric written by the test
author, who knows what the camera showed. PASS when the answer meets the rubric and states
nothing false about the scene, the past, or Qdrant. A short answer that meets the rubric passes.
FAIL when it misses the rubric, invents objects or memories, or contradicts the rubric.
Reply with only a JSON array, one object per item in order: {"id": ..., "pass": true|false,
"why": "<at most 12 words>"}.

Items:
"""


def key(item: dict, model: str = MODEL, prompt: str = PROMPT) -> str:
    """The verdict's identity: a new judge model or prompt judges afresh."""
    parts = [model, prompt, item["rubric"], item["visitor"], item["robot"]]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:16]


def judge(items: list[dict]) -> list[dict]:
    """One judge pass over the items, in order."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "verdict.txt"
        subprocess.run(["codex", "exec", "--model", MODEL, "-s", "read-only",
                        "--skip-git-repo-check", "-o", str(out),
                        PROMPT + json.dumps(items, indent=1)],
                       stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=600)
        text = out.read_text()
    verdicts = json.loads(text[text.index("["):text.rindex("]") + 1])
    assert [v["id"] for v in verdicts] == [i["id"] for i in items], "judge skipped items"
    return verdicts


def vote(passes: list[list[dict]]) -> list[dict]:
    """Majority of the passes per item, with the reason of a pass on the winning side."""
    out = []
    for vs in zip(*passes, strict=True):
        ok = sum(v["pass"] for v in vs) * 2 > len(vs)
        out.append({**next(v for v in vs if v["pass"] == ok), "votes": [v["pass"] for v in vs]})
    return out


def main(result: Path, cases: Path) -> int:
    rubric = {st["id"]: st["rubric"] for line in cases.read_text().splitlines()
              for st in json.loads(line)["steps"] if "say" in st}
    rows = [r for r in map(json.loads, result.read_text().splitlines()) if "id" in r]
    items = [{"id": r["id"], "visitor": r["heard"], "robot": r["answer"],
              "rubric": rubric[r["id"]]} for r in rows]
    # An answer already judged under the same rubric keeps its verdict: the judge alone flipped
    # 5 of 60 identical answers between two runs (D46). New answers get a majority of VOTES.
    cache = {c["key"]: c for c in map(json.loads, CACHE.read_text().splitlines())
             } if CACHE.exists() else {}
    new = list({key(i): i for i in items if key(i) not in cache}.values())  # once per answer
    if new:
        with ThreadPoolExecutor(VOTES) as pool:
            fresh = vote(list(pool.map(lambda _: judge(new), range(VOTES))))
        with CACHE.open("a") as f:
            for i, v in zip(new, fresh, strict=True):
                cache[key(i)] = {"key": key(i), **{k: v[k] for k in ("pass", "why", "votes")}}
                f.write(json.dumps(cache[key(i)]) + "\n")
    verdicts = [{"id": i["id"], **{k: cache[key(i)][k] for k in ("pass", "why", "votes")}}
                for i in items]
    judged = result.with_suffix(".judged.jsonl")
    pairs = list(zip(items, verdicts, strict=True))
    judged.write_text("".join(json.dumps({**i, **v}) + "\n" for i, v in pairs))
    for i, v in pairs:
        if not v["pass"]:
            print(f"FAIL {i['id']}: {v['why']}\n     [{i['visitor']}] {i['robot']}")
    passed = sum(v["pass"] for v in verdicts)
    print(f"judged {passed}/{len(verdicts)} pass ({MODEL}, {len(new)} new, majority of "
          f"{VOTES}); saved {judged}")
    return 0 if passed == len(verdicts) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2
                                          else "eval/dev/sessions.jsonl")))

