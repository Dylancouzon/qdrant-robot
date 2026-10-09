"""Enforcement checks for tools/gate.py, run against a throwaway git repository."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import gate


# Like gate.git: a hook's GIT_* variables must not reach these test commands.
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def sh(repo: Path, *args: str) -> str:
    return subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True,
                          env=CLEAN_ENV).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    sh(tmp_path, "git", "init", "-q", "-b", "main")
    sh(tmp_path, "git", "config", "user.email", "t@t")
    sh(tmp_path, "git", "config", "user.name", "t")
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "STATE.md").write_text("state\n")
    (tmp_path / "reviews").mkdir()
    sh(tmp_path, "git", "add", "-A")
    sh(tmp_path, "git", "commit", "-q", "-m", "init")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "checks", lambda: 0)  # checks are tested in CI itself
    return tmp_path


def stamp(repo: Path, tree: str, verdict: str = "PASS") -> None:
    (repo / "reviews" / f"{verdict}-review.md").write_text(
        f"<!-- tree: {tree} -->\nfindings\nVERDICT: {verdict}\n")


def test_bookkeeping_is_outside_the_code_tree(repo):
    (repo / "STATE.md").write_text("changed\n")
    assert gate.code_tree("worktree") == gate.code_tree("HEAD")


def test_untracked_code_changes_the_tree(repo):
    (repo / "new.py").write_text("y = 2\n")
    assert gate.code_tree("worktree") != gate.code_tree("HEAD")


def test_precommit_reminds_but_blocks_only_failing_checks(repo, monkeypatch, capsys):
    (repo / "app.py").write_text("x = 2\n")
    sh(repo, "git", "add", "-A")
    assert gate.precommit() == 0
    assert "Reminder" in capsys.readouterr().err
    stamp(repo, gate.code_tree("worktree"))
    assert gate.precommit() == 0
    assert "Reminder" not in capsys.readouterr().err
    monkeypatch.setattr(gate, "checks", lambda: 1)
    assert gate.precommit() == 1


def fake_codex(repo, monkeypatch, output="VERDICT: PASS", change=False):
    (repo / "gates").mkdir()
    (repo / "gates/review.md").write_text("Read-only test review.")
    script = repo / "codex"
    script.write_text(f"#!{sys.executable}\n"
                      "import pathlib, sys\n"
                      "out = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
                      f"out.write_text({output!r})\n"
                      + ("pathlib.Path('app.py').write_text('x = 3\\n')\n" if change else ""))
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{repo}:{os.environ['PATH']}")


def test_review_stamps_only_the_unchanged_tree(repo, monkeypatch):
    fake_codex(repo, monkeypatch)
    tree = gate.code_tree("worktree")
    assert gate.run("review", "test", "test-model") == 0
    assert gate.reviewed(tree)


def test_changed_tree_cannot_receive_a_pass_stamp(repo, monkeypatch):
    fake_codex(repo, monkeypatch, change=True)
    assert gate.run("review", "test", "test-model") == 3
    assert not gate.reviewed(gate.code_tree("worktree"))
    assert all(not p.read_text().startswith("<!-- tree:")
               for p in (repo / "reviews").glob("*-review.md"))


def test_nonpassing_verdict_remains_a_failure(repo, monkeypatch):
    fake_codex(repo, monkeypatch, output="VERDICT: FIX")
    assert gate.run("review", "test", "test-model") == 3
    assert not gate.reviewed(gate.code_tree("worktree"))


def test_check_timeout_kills_children(repo, monkeypatch):
    """A launcher and its delayed writer must both stop at the timeout."""
    monkeypatch.setattr(gate, "CHECK_TIMEOUT_S", 0.2)
    marker = repo / "survived"
    child = f"import time, pathlib; time.sleep(.5); pathlib.Path({str(marker)!r}).touch()"
    launch = (f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', "
              f"{child!r}]); time.sleep(10)")
    started = time.monotonic()
    assert gate.check_step([sys.executable, "-c", launch]) == 124
    assert time.monotonic() - started < 2
    time.sleep(0.5)
    assert not marker.exists()


def test_check_error_keeps_exit_failure(repo):
    assert gate.check_step([sys.executable, "-c", "raise SystemExit(7)"]) == 1


def test_gate_timeout_has_no_tree_stamp(repo, monkeypatch):
    fake_codex(repo, monkeypatch)
    script = repo / "codex"
    script.write_text(script.read_text() + "import time; time.sleep(10)\n")
    monkeypatch.setattr(gate, "TIMEOUT_S", 0.2)
    assert gate.run("review", "test", "test-model") == 124
    assert not gate.reviewed(gate.code_tree("worktree"))
