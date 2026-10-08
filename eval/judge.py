#!/usr/bin/env python3
"""Judge a replay on the Mac: a Codex model grades each spoken answer against its fixture
rubric (meaning, not keywords). Writes <result>.judged.jsonl and exits non-zero on any FAIL.

    python3 eval/judge.py bench/results/<date>-replay-<id>.jsonl [eval/dev/sessions.jsonl]
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

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


def main(result: Path, cases: Path) -> int:
    rubric = {st["id"]: st["rubric"] for line in cases.read_text().splitlines()
              for st in json.loads(line)["steps"] if "say" in st}
    rows = [r for r in map(json.loads, result.read_text().splitlines()) if "id" in r]
    items = [{"id": r["id"], "visitor": r["heard"], "robot": r["answer"],
              "rubric": rubric[r["id"]]} for r in rows]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "verdict.txt"
        prompt = PROMPT + json.dumps(items, indent=1)
        subprocess.run(["codex", "exec", "--model", MODEL, "-s", "read-only",
                        "--skip-git-repo-check", "-o", str(out), prompt],
                       stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=600)
        text = out.read_text()
    verdicts = json.loads(text[text.index("["):text.rindex("]") + 1])
    assert [v["id"] for v in verdicts] == [i["id"] for i in items], "judge skipped items"
    judged = result.with_suffix(".judged.jsonl")
    pairs = list(zip(items, verdicts, strict=True))
    judged.write_text("".join(json.dumps({**i, **v}) + "\n" for i, v in pairs))
    for i, v in pairs:
        if not v["pass"]:
            print(f"FAIL {i['id']}: {v['why']}\n     [{i['visitor']}] {i['robot']}")
    passed = sum(v["pass"] for v in verdicts)
    print(f"judged {passed}/{len(verdicts)} pass ({MODEL}); saved {judged}")
    return 0 if passed == len(verdicts) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2
                                          else "eval/dev/sessions.jsonl")))
