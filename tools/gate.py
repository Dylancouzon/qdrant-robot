#!/usr/bin/env python3
"""Run a Codex gate read-only on this repo, save its verdict in reviews/, and
exit 0 only when the verdict passes (3 = act on findings, 124 = timeout).

    tools/gate.py <design|review|milestone> [--model <name>] "<what to judge, with paths>"
    tools/gate.py checks      deterministic checks: lint, complexity, dead code, tests, self-checks
    tools/gate.py precommit   git pre-commit hook (git config core.hooksPath tools/githooks)
    tools/gate.py selftest

--model overrides the gate's default model (counsel: design --model gpt-6-astra).
"""
import argparse
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = {"design": "gpt-6-sol", "review": "gpt-6-sol", "milestone": "gpt-6-astra"}
PASSING = {"design": "GO", "review": "PASS", "milestone": "MILESTONE MET"}
TIMEOUT_S = 900
# Bookkeeping the lead edits after a review; excluded from the reviewed code tree.
BOOKKEEPING = ["STATE.md", "DECISIONS.md", "research", "reviews", "bench/results"]
SELFTESTS = ["robot.asr", "robot.audio", "robot.brain", "robot.detect", "robot.memory", "robot.tts"]

def git(*args: str, env: dict | None = None) -> str:
    """git in ROOT. A hook's GIT_DIR and GIT_INDEX_FILE are dropped: in a linked worktree they
    pointed these commands at another index; `env` adds what a call needs."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=ROOT, env={**clean, **(env or {})}, check=True,
                          capture_output=True, text=True).stdout.strip()


def code_tree(source: str) -> str:
    """Tree hash of the code in "worktree", "index", or a revision, minus bookkeeping."""
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        env = {"GIT_INDEX_FILE": str(index)}
        if source == "index":
            shutil.copy(git("rev-parse", "--path-format=absolute", "--git-path", "index"), index)
        else:
            git("read-tree", "HEAD" if source == "worktree" else source, env=env)
        if source == "worktree":
            git("add", "-A", env=env)
        git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *BOOKKEEPING, env=env)
        return git("write-tree", env=env)


def reviewed(tree: str) -> bool:
    """A PASS review stamped with this code tree exists in reviews/."""
    texts = [f.read_text() for f in (ROOT / "reviews").glob("*-review.md")]
    return any(text.startswith(f"<!-- tree: {tree} -->") and verdict(text) == "PASS"
               for text in texts)


def checks() -> int:
    """Deterministic checks every commit to main must pass. Prints the size delta."""
    py = [f for f in git("ls-files", "--cached", "--others", "--exclude-standard",
                         "*.py").splitlines() if not f.startswith("refs/")]
    steps = []
    if py:
        steps += [["uvx", "ruff", "check", *py],  # rules in ruff.toml
                  ["uvx", "vulture", "--min-confidence", "80", *py]]
    tests = [f for f in py if Path(f).name.startswith("test_")]
    if tests:
        steps.append(["uv", "run", "--no-project", "--with", "pytest", "pytest", "-q", *tests])
    # Module self-checks that run without models or devices (the Mac venv has the packages).
    steps += [[str(ROOT / ".venv/bin/python"), "-m", m] for m in SELFTESTS]
    steps += [[sys.executable, str(ROOT / t), "selftest"] for t in ("tools/jetson.py",
                                                                    "tools/gate.py")]
    for cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            print(f"FAILED: {' '.join(cmd[:3])}\n{r.stdout[-3000:]}{r.stderr[-1000:]}")
            return 1
    print(git("diff", "--shortstat", "HEAD") or "no tracked changes")
    return 0


def precommit() -> int:
    """git pre-commit hook: block failing checks; remind (never block) about review.

    Checks read the working tree (light by design, D17): stage everything you commit.
    """
    staged = code_tree("index")
    if staged == code_tree("HEAD"):
        return 0  # bookkeeping only
    if not reviewed(staged):
        print("Reminder: no PASS review matches this code. Run `tools/gate.py review` "
              "before calling the task done (CLAUDE.md, Gates).", file=sys.stderr)
    return checks()


def verdict(response: str) -> str:
    """The text after 'VERDICT:' on the last non-empty line, or ''."""
    lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
    if not lines or not lines[-1].upper().startswith("VERDICT:"):
        return ""
    return lines[-1].split(":", 1)[1].strip().upper()


def interrupted(_signum, _frame):
    raise KeyboardInterrupt  # so SIGTERM also runs the cleanup in run()


def run(gate: str, what: str, model: str) -> int:
    reviews = ROOT / "reviews"
    reviews.mkdir(exist_ok=True)
    out = reviews / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}-{gate}.md"
    prompt = (ROOT / "gates" / f"{gate}.md").read_text() + f"\nWhat to judge: {what}\n"
    cmd = ["codex", "exec", "--model", model, "-s", "read-only",
           "--skip-git-repo-check", "-C", str(ROOT), "-o", str(out), prompt]
    with open(f"{out}.log", "w") as log:
        # stdin closed: codex exec otherwise waits for input forever.
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=log, start_new_session=True)
        try:
            proc.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            print(f"timeout after {TIMEOUT_S} s; log: {out}.log", file=sys.stderr)
            return 124
        finally:
            # Covers timeout and Ctrl-C: never leave a Codex process group behind.
            # The launcher may have exited while its children still run.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    if proc.returncode or not out.exists():
        print(f"codex failed ({proc.returncode}); log: {out}.log", file=sys.stderr)
        return proc.returncode or 1
    response = out.read_text()
    out.write_text(f"<!-- tree: {code_tree('worktree')} -->\n{response}")
    print(response)
    print(f"\nsaved: {out.relative_to(ROOT)}")
    return 0 if verdict(response) == PASSING[gate] else 3


def selftest() -> None:
    assert verdict("findings\n\nVERDICT: PASS\n") == "PASS"
    assert verdict("VERDICT: go with changes") == "GO WITH CHANGES"
    assert verdict("VERDICT: GO\nmore text") == ""
    assert verdict("") == ""
    assert verdict("VERDICT: GO WITH CHANGES") != PASSING["design"]
    assert verdict("x\nVERDICT: MILESTONE MET") == PASSING["milestone"]
    assert verdict("<!-- tree: abc -->\nfindings\nVERDICT: PASS") == "PASS"
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
        sys.exit(0)
    if sys.argv[1:] == ["checks"]:
        sys.exit(checks())
    if sys.argv[1:] == ["precommit"]:
        sys.exit(precommit())
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("gate", choices=MODEL)
    parser.add_argument("what", help="what to judge, with paths and evidence")
    parser.add_argument("--model", help="override the gate's default model")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(run(args.gate, args.what, args.model or MODEL[args.gate]))
