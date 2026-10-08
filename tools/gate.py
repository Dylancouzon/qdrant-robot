#!/usr/bin/env python3
"""Run a Codex gate read-only on this repo, save its verdict in reviews/, and
exit 0 only when the verdict passes (3 = act on findings, 124 = timeout).

    tools/gate.py <design|review|milestone> "<what to judge, with paths>"
    tools/gate.py selftest
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = {"design": "gpt-6-sol", "review": "gpt-6-sol", "milestone": "gpt-6-astra"}
PASSING = {"design": "GO", "review": "PASS", "milestone": "MILESTONE MET"}
TIMEOUT_S = 900


def verdict(response: str) -> str:
    """The text after 'VERDICT:' on the last non-empty line, or ''."""
    lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
    if not lines or not lines[-1].upper().startswith("VERDICT:"):
        return ""
    return lines[-1].split(":", 1)[1].strip().upper()


def run(gate: str, what: str) -> int:
    reviews = ROOT / "reviews"
    reviews.mkdir(exist_ok=True)
    out = reviews / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}-{gate}.md"
    prompt = (ROOT / "gates" / f"{gate}.md").read_text() + f"\nWhat to judge: {what}\n"
    cmd = ["codex", "exec", "--model", MODEL[gate], "-s", "read-only",
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
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    if proc.returncode or not out.exists():
        print(f"codex failed ({proc.returncode}); log: {out}.log", file=sys.stderr)
        return proc.returncode or 1
    response = out.read_text()
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
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
        sys.exit(0)
    if len(sys.argv) != 3 or sys.argv[1] not in MODEL:
        sys.exit(__doc__)
    sys.exit(run(sys.argv[1], sys.argv[2]))
