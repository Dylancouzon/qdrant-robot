"""Grade conversation replays with their actual preceding dialogue, using the existing judge.

    python -m bench.conversation RESULT.jsonl eval/dev/conversation.jsonl
"""
import json
import sys
import tempfile
from pathlib import Path

from eval.judge import main as judge
from eval.run import replay_rows


def contextual_cases(sessions: list[dict], rows: list[dict]) -> list[dict]:
    by_id = {row["id"]: row for row in rows}
    cases = []
    for session in sessions:
        history, steps = [], []
        for step in session["steps"]:
            if "say" not in step:
                continue
            row = by_id[step["id"]]
            rubric = (step["rubric"] + "\nJudge follow-ups against the actual preceding "
                      "conversation. Earlier replies provide dialogue context, not proof of "
                      "what is visible now.\nPreceding conversation: " + json.dumps(history))
            steps.append({**step, "rubric": rubric})
            history.append({"visitor": row["heard"], "robot": row["answer"]})
        cases.append({"id": session["id"], "steps": steps})
    return cases


def main(result: Path, cases: Path) -> int:
    rows = replay_rows(result, cases)  # reject incomplete runs before asking the judge
    sessions = [json.loads(line) for line in cases.read_text().splitlines()]
    contextual = contextual_cases(sessions, rows)
    with tempfile.TemporaryDirectory() as tmp:
        prepared = Path(tmp) / "cases.jsonl"
        prepared.write_text("".join(json.dumps(session) + "\n" for session in contextual))
        return judge(result, prepared)


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
