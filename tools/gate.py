#!/usr/bin/env python3
"""Run a Codex gate read-only on this repo, save its verdict in reviews/, and
exit 0 only when the verdict passes (3 = act on findings, 124 = timeout).

    tools/gate.py <design|review|milestone> [--model <name>] [--effort <level>] "<what, paths>"
    tools/gate.py checks      deterministic checks: lint, complexity, dead code, tests, self-checks
    tools/gate.py precommit   git pre-commit hook (git config core.hooksPath tools/githooks)
    tools/gate.py selftest

--model overrides the gate's default model (counsel: design --model gpt-6-astra).
"""
from __future__ import annotations

import argparse
import contextlib
import os
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = {"design": "gpt-6.1-sol", "review": "gpt-6.1-sol", "milestone": "gpt-6-astra"}
PASSING = {"design": "GO", "review": "PASS", "milestone": "MILESTONE MET"}
TIMEOUT_S = 900
CHECK_TIMEOUT_S = 300  # the suite takes 95-120 s on an idle Mac, more under load
# Bookkeeping the lead edits after a review; excluded from the reviewed code tree.
BOOKKEEPING = ["STATE.md", "DECISIONS.md", "research", "reviews", "bench/results"]
SELFTESTS = ["robot.asr", "robot.audio", "robot.brain", "robot.detect", "robot.memory",
             "robot.things", "robot.settings", "robot.tts"]

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


def checks(*, static_only: bool = False) -> int:
    """Run fast static commit checks, or full release validation. Print the size delta."""
    # git lists untracked files first; keep test order stable when files become tracked.
    py = sorted(f for f in git("ls-files", "--cached", "--others", "--exclude-standard",
                              "*.py").splitlines() if not f.startswith("refs/"))
    steps = []
    if py:
        steps += [["uvx", "ruff", "check", *py],  # rules in ruff.toml
                  ["uvx", "vulture", "--min-confidence", "80", *py]]
    if not static_only:
        tests = [f for f in py if Path(f).name.startswith("test_")]
        if tests:
            steps.append(["uv", "run", "--no-project", "--with", "pytest", "pytest", "-q", *tests])
        steps += [["npm", "--prefix", "tools/ui", "ci", "--ignore-scripts",
                   "--no-audit", "--no-fund"],
                  ["npm", "--prefix", "tools/ui", "test"]]
        # One interpreter shares expensive dependency imports across all existing assertions.
        steps += [[str(ROOT / ".venv/bin/python"), str(ROOT / "tools/gate.py"), "modules"]]
        steps += [[sys.executable, str(ROOT / t), "selftest"] for t in ("tools/jetson.py",
                                                                        "tools/gate.py")]
    started = time.monotonic()
    for cmd in steps:
        code = check_step(cmd)
        if code:
            return code
    print(f"checks passed in {time.monotonic() - started:.2f}s")
    print(git("diff", "--shortstat", "HEAD") or "no tracked changes")
    return 0


def stop(proc: subprocess.Popen) -> None:
    """Clean up the full command group even when the launcher has already exited."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def check_step(cmd: list[str]) -> int:
    label = " ".join(cmd[:4])
    print(f"checking: {label} (limit {CHECK_TIMEOUT_S}s)", flush=True)
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=CHECK_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        stop(proc)
        stdout, stderr = proc.communicate()
        print(f"TIMEOUT: {label}\n{stdout[-3000:]}{stderr[-1000:]}", flush=True)
        return 124
    finally:
        stop(proc)
    elapsed = time.monotonic() - started
    if proc.returncode:
        print(f"FAILED ({elapsed:.2f}s): {label}\n{stdout[-3000:]}{stderr[-1000:]}")
        return 1
    print(f"passed ({elapsed:.2f}s): {label}", flush=True)
    return 0


def module_checks() -> None:
    # Script invocation places tools/ on sys.path, while module assertions import robot/.
    sys.path.insert(0, str(ROOT))
    for module in SELFTESTS:
        started = time.monotonic()
        runpy.run_module(module, run_name="__main__")
        print(f"{module}: {time.monotonic() - started:.2f}s", flush=True)


def precommit() -> int:
    """git pre-commit hook: block failing checks; remind (never block) about review.

    Static checks read the working tree: stage everything you commit. Run task tests before
    review; full release checks remain available through `tools/gate.py checks`.
    """
    staged = code_tree("index")
    if staged == code_tree("HEAD"):
        return 0  # bookkeeping only
    if not reviewed(staged):
        print("Reminder: no PASS review matches this code. Run `tools/gate.py review` "
              "before calling the task done (CLAUDE.md, Gates).", file=sys.stderr)
    return checks(static_only=True)


def verdict(response: str) -> str:
    """The text after 'VERDICT:' on the last non-empty line, or ''."""
    lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
    if not lines or not lines[-1].upper().startswith("VERDICT:"):
        return ""
    return lines[-1].split(":", 1)[1].strip().upper()


def interrupted(_signum, _frame):
    raise KeyboardInterrupt  # so SIGTERM also runs the cleanup in run()


def run(gate: str, what: str, model: str, effort: str | None = None) -> int:
    tree = code_tree("worktree")
    reviews = ROOT / "reviews"
    reviews.mkdir(exist_ok=True)
    out = reviews / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}-{gate}.md"
    prompt = (ROOT / "gates" / f"{gate}.md").read_text() + f"\nWhat to judge: {what}\n"
    cmd = ["codex", "exec", "--model", model, "-s", "read-only",
           *(["-c", f"model_reasoning_effort={effort}"] if effort else []),
           "--skip-git-repo-check", "-C", str(ROOT), "-o", str(out), prompt]
    started = time.monotonic()
    print(f"{gate}: {model}, tree={tree}, limit={TIMEOUT_S}s; log: {out}.log", flush=True)
    with open(f"{out}.log", "w") as log:
        # stdin closed: codex exec otherwise waits for input forever.
        proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=log, start_new_session=True)
        try:
            proc.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            print(f"timeout after {TIMEOUT_S} s; log: {out}.log", file=sys.stderr)
            return 124
        finally:
            # Covers timeout and Ctrl-C: never leave a Codex process group behind.
            # The launcher may have exited while its children still run.
            stop(proc)
    if proc.returncode or not out.exists():
        print(f"codex failed ({proc.returncode}); log: {out}.log", file=sys.stderr)
        return proc.returncode or 1
    response = out.read_text()
    print(response)
    if code_tree("worktree") != tree:
        print("code changed during the gate; verdict has no tree stamp", file=sys.stderr)
        return 3
    out.write_text(f"<!-- tree: {tree} -->\n{response}")
    print(f"\nsaved: {out.relative_to(ROOT)} ({time.monotonic() - started:.2f}s)")
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
    signal.signal(signal.SIGTERM, interrupted)
    if sys.argv[1:] == ["modules"]:
        module_checks()
        sys.exit(0)
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
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh"],
                        help="Codex reasoning effort (default: ~/.codex/config.toml)")
    args = parser.parse_args()
    sys.exit(run(args.gate, args.what, args.model or MODEL[args.gate], args.effort))
